cask "audiotag" do
  arch arm: "arm64", intel: "universal"

  version "0.0.0"
  sha256 :no_check

  url "https://github.com/foyoodo/AudioTag/releases/download/v#{version}/AudioTag-#{arch}.zip"
  name "AudioTag"
  desc "Audio metadata editor powered by TagLib"
  homepage "https://github.com/foyoodo/AudioTag"

  livecheck do
    url :url
    strategy :github_latest
  end

  depends_on macos: :sonoma

  app "AudioTag.app"

  # Unsigned builds stay quarantined, so Gatekeeper refuses to open them.
  postflight_steps do
    on_macos do
      run "/usr/bin/xattr",
          args: ["-dr", "com.apple.quarantine", "{{appdir}}/AudioTag.app"]
    end
  end

  uninstall quit: "com.foyoodo.AudioTag"

  zap trash: [
    "~/Library/Containers/com.foyoodo.AudioTag",
    "~/Library/Preferences/com.foyoodo.AudioTag.plist",
    "~/Library/Saved Application State/com.foyoodo.AudioTag.savedState",
  ]

  caveats <<~EOS
    AudioTag is not code-signed or notarized. Apple Silicon installs the
    arm64 build; Intel installs the universal (arm64 + x86_64) build.
    This cask removes the quarantine attribute so Gatekeeper does not block
    the app. macOS may still say the developer cannot be verified.
    Homebrew no longer supports --no-quarantine. If the app is installed
    in ~/Applications, run:
      xattr -dr com.apple.quarantine ~/Applications/AudioTag.app
  EOS
end
