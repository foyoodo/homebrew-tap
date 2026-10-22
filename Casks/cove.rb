cask "cove" do
  version "0.7.0-rc.3"
  sha256 "90e6b847d7acfca0c3dd2253f3a9bb9efd04b7f2b66909c81b83f24ecfefed0b"
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

  # The app is unsigned. Homebrew quarantines the download, which makes
  # Gatekeeper refuse to launch it. Clear that attribute after the .app
  # is in place.
  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-dr", "com.apple.quarantine", "#{appdir}/Cove.app"]
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
  EOS
end
