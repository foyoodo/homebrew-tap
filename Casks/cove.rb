cask "cove" do
  version "0.7.0-rc.5"
  sha256 "7ec7c4e35a3ad4cd7963fd9a441b2b7d8a1b9feed7ad40f5dac45c88095021b2"

  url "https://github.com/foyoodo/Cove/releases/download/v#{version}/Cove-#{version}-darwin-arm64.zip"
  name "Cove"
  desc "Native chat client for OpenAI-compatible models"
  homepage "https://github.com/foyoodo/Cove"

  livecheck do
    url :url
    strategy :github_latest
  end

  depends_on arch: :arm64
  depends_on macos: :monterey

  app "Cove.app"

  # Unsigned builds stay quarantined, so Gatekeeper refuses to open them.
  postflight_steps do
    on_macos do
      run "/usr/bin/xattr",
          args: ["-dr", "com.apple.quarantine", "{{appdir}}/Cove.app"]
    end
  end

  uninstall quit: "dev.cove.chat"

  zap trash: [
    "~/Library/Application Support/Cove",
    "~/Library/Caches/Cove",
    "~/Library/Logs/Cove",
    "~/Library/Preferences/dev.cove.chat.plist",
    "~/Library/Saved Application State/dev.cove.chat.savedState",
  ]

  caveats <<~EOS
    Cove is not code-signed or notarized, and it runs only on Apple Silicon.
    This cask removes the quarantine attribute so Gatekeeper does not block
    the app. macOS may still say the developer cannot be verified.
    Homebrew no longer supports --no-quarantine. If the app is installed
    in ~/Applications, run:
      xattr -dr com.apple.quarantine ~/Applications/Cove.app
  EOS
end
