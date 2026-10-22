#!/usr/bin/env python3
"""Point Casks/cove.rb at the Cove release this tap should install.

Selection:
  * the latest stable (non-prerelease) release, when one exists
  * otherwise the newest published release, including a prerelease

The checksum comes from the published .sha256 asset. If that asset is
missing or unusable, the zip is downloaded and hashed locally.
The script only rewrites version and sha256. It does not commit.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = "foyoodo/Cove"
CASK_PATH = Path(__file__).resolve().parent.parent / "Casks" / "cove.rb"
API = "https://api.github.com"
USER_AGENT = "foyoodo-homebrew-tap"

# Do not use \s here. It matches newlines and would delete the blank line
# brew style requires between the sha256 stanza and the url stanza.
VERSION_RE = re.compile(r'^(  version ")([^"]+)(")[ \t]*$', re.M)
SHA_RE = re.compile(r'^(  sha256 ")([0-9a-fA-F]{64})(")[ \t]*$', re.M)
SHA256_RE = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{64})(?![0-9a-f])")


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


def list_releases() -> list[dict]:
    releases: list[dict] = []
    url = f"{API}/repos/{REPO}/releases?per_page=100"
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


def select_release(latest: dict | None, releases: list[dict]) -> tuple[dict, str]:
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
        raise SystemExit("foyoodo/Cove has no published releases")
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


def checksum_for(release: dict, version: str) -> tuple[str, str]:
    zip_name = f"Cove-{version}-darwin-arm64.zip"
    sha_name = zip_name + ".sha256"
    zip_asset = asset_named(release, zip_name)
    if not zip_asset or not zip_asset.get("browser_download_url"):
        raise SystemExit(f"release {release.get('tag_name')} has no {zip_name}")
    sha_asset = asset_named(release, sha_name)
    if sha_asset and sha_asset.get("browser_download_url"):
        parsed = download_sha256(sha_asset["browser_download_url"])
        if parsed:
            return parsed, "sha256 asset"
        print(f"{sha_name} was unusable; hashing the zip", file=sys.stderr)
    return compute_sha256(zip_asset["browser_download_url"]), "computed"


def read_cask(text: str) -> tuple[str, str]:
    version = VERSION_RE.search(text)
    sha = SHA_RE.search(text)
    if not version or not sha:
        raise SystemExit(f"could not parse version and sha256 in {CASK_PATH}")
    return version.group(2), sha.group(2).lower()


def write_cask(text: str, version: str, sha256: str) -> str:
    def repl_version(match: re.Match[str]) -> str:
        return f"{match.group(1)}{version}{match.group(3)}"

    def repl_sha(match: re.Match[str]) -> str:
        return f"{match.group(1)}{sha256}{match.group(3)}"

    updated, version_count = VERSION_RE.subn(repl_version, text, count=1)
    updated, sha_count = SHA_RE.subn(repl_sha, updated, count=1)
    if version_count != 1 or sha_count != 1:
        raise SystemExit(
            f"refusing to edit cask: version replacements={version_count}, "
            f"sha256 replacements={sha_count}"
        )
    return updated


def set_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def main() -> int:
    latest, _headers = get_json(f"{API}/repos/{REPO}/releases/latest")
    if latest is not None and not isinstance(latest, dict):
        raise SystemExit(f"unexpected latest-release payload: {latest!r}")
    release, channel = select_release(latest, list_releases())
    version = version_from_tag(release["tag_name"])
    sha256, sha_source = checksum_for(release, version)

    text = CASK_PATH.read_text(encoding="utf-8")
    current_version, current_sha = read_cask(text)
    changed = current_version != version or current_sha != sha256
    print(
        f"target {version} ({channel}, checksum {sha_source})\n"
        f"cask   {current_version} ({current_sha})\n"
        f"{'update' if changed else 'unchanged'}"
    )
    if changed:
        CASK_PATH.write_text(write_cask(text, version, sha256), encoding="utf-8")
    set_output("version", version)
    set_output("channel", channel)
    set_output("changed", "true" if changed else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
