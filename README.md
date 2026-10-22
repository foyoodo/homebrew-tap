# foyoodo/tap

Homebrew tap for the macOS app [Cove](https://github.com/foyoodo/Cove).

Cove ships an Apple Silicon (`arm64`) build only. It is not code-signed or notarized. Its `LSMinimumSystemVersion` is macOS 12 (Monterey).

## Install

```sh
brew tap foyoodo/tap && brew install --cask cove
```

## Upgrade

```sh
brew upgrade --cask cove
```

`Casks/cove.rb` is maintained by this repository's auto-update. When a stable release exists, the cask tracks the latest stable release. Until then, it tracks the newest published release, including a prerelease.

## Uninstall

```sh
brew uninstall --cask cove
```

To also remove chats, caches, logs, and preferences:

```sh
brew uninstall --cask --zap cove
```

`--zap` removes these paths:

- `~/Library/Application Support/Cove` (chats and window state)
- `~/Library/Caches/Cove`
- `~/Library/Logs/Cove`
- `~/Library/Preferences/dev.cove.chat.plist`
- `~/Library/Saved Application State/dev.cove.chat.savedState`

API keys stay in the macOS login keychain under the service name `dev.cove.chat`. `--zap` does not delete keychain items. To remove the keys, open Keychain Access and delete the generic passwords for that service.

To stop using this tap:

```sh
brew untap foyoodo/tap
```

## Auto-update

[`.github/workflows/update-cask.yml`](.github/workflows/update-cask.yml) runs every hour, and it can also be started by hand from the Actions tab (`workflow_dispatch`).

The workflow uses this repository's own `GITHUB_TOKEN` to read releases from [`foyoodo/Cove`](https://github.com/foyoodo/Cove). No extra PAT or secret is required. Its `contents: write` permission is used only to push a commit back to `main` when something changed.

Selection rules:

- If a non-prerelease stable release exists, use the latest stable release (GitHub's `releases/latest`). Prereleases published after that are ignored.
- If no stable release exists yet, use the newest published release. A version with a hyphen (for example `0.7.0-rc.3`) is a prerelease.

When the target version or `sha256` differs from the cask, the workflow updates `version` and `sha256` in `Casks/cove.rb` and commits to `main`. It prefers the published `Cove-<version>-darwin-arm64.zip.sha256` asset. If that file is missing or cannot be parsed, it downloads the zip and computes the checksum. When neither the version nor the checksum changed, it does not commit.

## Gatekeeper

Cove is unsigned and not notarized. An app downloaded in a browser carries a quarantine attribute, and Gatekeeper refuses to open it. After this cask places `Cove.app` in the Applications folder, it runs:

```sh
xattr -dr com.apple.quarantine /Applications/Cove.app
```

Installing with the Homebrew commands above therefore opens without that block. macOS may still say the developer cannot be verified. That is expected for an unsigned app. If the app is installed in `~/Applications`, run the same command on that path.
