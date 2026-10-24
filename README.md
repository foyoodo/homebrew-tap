# foyoodo/tap

```sh
brew install --cask foyoodo/tap/cove
brew install --cask foyoodo/tap/audiotag
```

Homebrew 6+ requires trust. The commands above trust only that cask. To tap and install by short name:

```sh
brew tap foyoodo/tap
brew trust --cask foyoodo/tap/cove && brew install --cask cove
brew trust --cask foyoodo/tap/audiotag && brew install --cask audiotag
```

- `cove` — [Cove](https://github.com/foyoodo/Cove), native chat client (Apple Silicon)
- `audiotag` — [AudioTag](https://github.com/foyoodo/AudioTag), audio metadata editor
