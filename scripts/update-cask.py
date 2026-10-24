#!/usr/bin/env python3
"""Point casks in this tap at the upstream GitHub releases they should install.

Casks:
  * cove     — foyoodo/Cove, arm64 zip (checksum from a .sha256 asset when present)
  * audiotag — foyoodo/AudioTag, arm64 zip on Apple Silicon and universal zip on Intel

Selection for each repo:
  * the latest stable (non-prerelease) release, when one exists
  * otherwise the newest published release, including a prerelease

The script only rewrites version and sha256. It does not commit.
A missing AudioTag release is skipped so Cove updates still run.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

API = "https://api.github.com"
USER_AGENT = "foyoodo-homebrew-tap"
ROOT = Path(__file__).resolve().parent.parent

# Do not use \s here. It matches newlines and would delete the blank line
# brew style requires between the sha256 stanza and the url stanza.
VERSION_RE = re.compile(r'^(  version ")([^"]+)(")[ \t]*$', re.M)
# Single hash, :no_check, or arm/intel pair. Does not consume the following blank line.
SHA256_STANZA_RE = re.compile(
    r"^  sha256 .*(?:\n         intel: .*)?[ \t]*\n",
    re.M,
)
SHA256_RE = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{64})(?![0-9a-f])")


@dataclass(frozen=True)
class CaskSpec:
    token: str
    repo: str
    # Zip asset names. {version} is the tag without the leading v.
    arm_zip: str | None
    intel_zip: str | None
    # If True, prefer an asset named "<zip>.sha256" before hashing the zip.
    sha256_asset: bool
    # If False, missing releases or assets skip this cask instead of failing the job.
    required: bool

    @property
    def path(self) -> Path:
        return ROOT / "Casks" / f"{self.token}.rb"


CASKS = [
    CaskSpec(
        token="cove",
        repo="foyoodo/Cove",
        arm_zip="Cove-{version}-darwin-arm64.zip",
        intel_zip=None,
        sha256_asset=True,
        required=True,
    ),
    CaskSpec(
        token="audiotag",
        repo="foyoodo/AudioTag",
        arm_zip="AudioTag-arm64.zip",
        intel_zip="AudioTag-universal.zip",
        sha256_asset=False,
        required=False,
    ),
]


def token() -> str | None:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or None


def request(url: str, accept: str = "application/vnd.github+json") -> tuple[bytes, object]:
    headers = {
        "Accept": accept,
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if (auth := token()) and url.startswith(API):
        headers["Authorization"] = f"Bearer {auth}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read(), resp.headers
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return b"", err.headers
        detail = err.read().decode("utf-8", "replace")
        raise SystemExit(f"GET {url} failed: HTTP {err.code}: {detail}") from err


def get_json(url: str):
    body, headers = request(url)
    if not body:
        return None, headers
    return json.loads(body), headers


def list_releases(repo: str) -> list[dict]:
    releases: list[dict] = []
    url = f"{API}/repos/{repo}/releases?per_page=100"
    while url:
        page, headers = get_json(url)
        if not page:
            break
        if not isinstance(page, list):
            raise SystemExit(f"unexpected releases payload: {page!r}")
        releases.extend(page)
        url = next_link(headers.get("Link") if headers else None)
    return releases


def next_link(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(","):
        section, _, rel = part.partition(";")
        if 'rel="next"' in rel:
            return section.strip().lstrip("<").rstrip(">")
    return None


def select_release(latest: dict | None, releases: list[dict]) -> tuple[dict, str] | None:
    """Return (release, channel) where channel is 'stable' or 'prerelease'."""
    if (
        isinstance(latest, dict)
        and not latest.get("draft")
        and not latest.get("prerelease")
        and latest.get("tag_name")
    ):
        return latest, "stable"

    published = [release for release in releases if not release.get("draft")]
    if not published:
        return None
    published.sort(key=lambda release: release.get("published_at") or "", reverse=True)
    chosen = published[0]
    channel = "prerelease" if chosen.get("prerelease") else "stable"
    return chosen, channel


def version_from_tag(tag: str) -> str:
    if not tag.startswith("v") or len(tag) == 1:
        raise SystemExit(f"release tag {tag!r} does not start with v")
    return tag[1:]


def asset_named(release: dict, name: str) -> dict | None:
    for asset in release.get("assets") or []:
        if asset.get("name") == name:
            return asset
    return None


def parse_sha256(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = SHA256_RE.search(stripped)
        if match:
            return match.group(1).lower()
    return None


def download_sha256(url: str) -> str | None:
    body, _headers = request(url, accept="application/octet-stream")
    if not body:
        return None
    return parse_sha256(body.decode("utf-8", "replace"))


def compute_sha256(url: str) -> str:
    digest = hashlib.sha256()
    headers = {"Accept": "application/octet-stream", "User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as resp:
        while chunk := resp.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def checksum_for_zip(release: dict, zip_name: str, use_sha256_asset: bool) -> tuple[str, str]:
    zip_asset = asset_named(release, zip_name)
    if not zip_asset or not zip_asset.get("browser_download_url"):
        raise FileNotFoundError(f"release {release.get('tag_name')} has no {zip_name}")
    if use_sha256_asset:
        sha_name = zip_name + ".sha256"
        sha_asset = asset_named(release, sha_name)
        if sha_asset and sha_asset.get("browser_download_url"):
            parsed = download_sha256(sha_asset["browser_download_url"])
            if parsed:
                return parsed, "sha256 asset"
            print(f"{sha_name} was unusable; hashing the zip", file=sys.stderr)
    return compute_sha256(zip_asset["browser_download_url"]), "computed"


def format_sha256_stanza(checksums: str | dict[str, str]) -> str:
    if isinstance(checksums, str):
        if checksums == ":no_check":
            return "  sha256 :no_check\n"
        return f'  sha256 "{checksums}"\n'
    return (
        f'  sha256 arm:   "{checksums["arm"]}",\n'
        f'         intel: "{checksums["intel"]}"\n'
    )


def read_cask(text: str, path: Path) -> tuple[str, str]:
    version = VERSION_RE.search(text)
    sha = SHA256_STANZA_RE.search(text)
    if not version or not sha:
        raise SystemExit(f"could not parse version and sha256 in {path}")
    return version.group(2), sha.group(0)


def write_cask(text: str, version: str, checksums: str | dict[str, str], path: Path) -> str:
    def repl_version(match: re.Match[str]) -> str:
        return f"{match.group(1)}{version}{match.group(3)}"

    updated, version_count = VERSION_RE.subn(repl_version, text, count=1)
    updated, sha_count = SHA256_STANZA_RE.subn(format_sha256_stanza(checksums), updated, count=1)
    if version_count != 1 or sha_count != 1:
        raise SystemExit(
            f"refusing to edit {path}: version replacements={version_count}, "
            f"sha256 replacements={sha_count}"
        )
    return updated


def set_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def update_cask(spec: CaskSpec) -> tuple[bool, str | None]:
    """Return (changed, version). version is None when this cask was skipped."""
    latest, _headers = get_json(f"{API}/repos/{spec.repo}/releases/latest")
    if latest is not None and not isinstance(latest, dict):
        raise SystemExit(f"unexpected latest-release payload for {spec.repo}: {latest!r}")
    selected = select_release(latest, list_releases(spec.repo))
    if selected is None:
        message = f"{spec.repo} has no published releases"
        if spec.required:
            raise SystemExit(message)
        print(f"{spec.token}: skip ({message})")
        return False, None

    release, channel = selected
    version = version_from_tag(release["tag_name"])

    checksums: str | dict[str, str]
    sha_source: str
    try:
        if spec.arm_zip and spec.intel_zip:
            arm_name = spec.arm_zip.format(version=version)
            intel_name = spec.intel_zip.format(version=version)
            arm_sha, arm_source = checksum_for_zip(release, arm_name, spec.sha256_asset)
            intel_sha, intel_source = checksum_for_zip(release, intel_name, spec.sha256_asset)
            checksums = {"arm": arm_sha, "intel": intel_sha}
            sha_source = f"arm {arm_source}, intel {intel_source}"
        elif spec.arm_zip:
            zip_name = spec.arm_zip.format(version=version)
            checksums, sha_source = checksum_for_zip(release, zip_name, spec.sha256_asset)
        else:
            raise SystemExit(f"{spec.token}: no zip assets configured")
    except FileNotFoundError as err:
        if spec.required:
            raise SystemExit(str(err)) from err
        print(f"{spec.token}: skip ({err})")
        return False, None

    text = spec.path.read_text(encoding="utf-8")
    current_version, current_sha_stanza = read_cask(text, spec.path)
    new_sha_stanza = format_sha256_stanza(checksums)
    changed = current_version != version or current_sha_stanza != new_sha_stanza
    print(
        f"{spec.token}: target {version} ({channel}, checksum {sha_source})\n"
        f"{spec.token}: cask   {current_version} ({current_sha_stanza.strip()})\n"
        f"{spec.token}: {'update' if changed else 'unchanged'}"
    )
    if changed:
        spec.path.write_text(write_cask(text, version, checksums, spec.path), encoding="utf-8")
    return changed, version


def main() -> int:
    changed_parts: list[str] = []
    any_changed = False
    for spec in CASKS:
        if not spec.path.is_file():
            message = f"missing {spec.path}"
            if spec.required:
                raise SystemExit(message)
            print(f"{spec.token}: skip ({message})")
            continue
        changed, version = update_cask(spec)
        if changed and version:
            any_changed = True
            changed_parts.append(f"{spec.token} cask to {version}")

    commit_message = f"Update {' and '.join(changed_parts)}" if changed_parts else ""
    print("changed" if any_changed else "unchanged")
    set_output("changed", "true" if any_changed else "false")
    set_output("commit_message", commit_message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
