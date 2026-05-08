# 6ure™ App Source Code

This folder contains the standalone 6ure™ App desktop source code only.

- `files_app.py`: desktop entrypoint
- `server.py`: local upload API and session logic
- `index.html`: dedicated 6ure™ App interface
- `assets`: app icons and brand images
- `build-macos-arm64.sh`: Apple Silicon macOS build script
- `discord-presence.json`: optional Discord Rich Presence settings

Runtime data is stored in:

```text
%LOCALAPPDATA%\6ure Leak Upld. User Data
~/Library/Application Support/6ure Leak Upld. User Data
```

That folder keeps credentials, the last editor/folder values, and recent upload history until the user logs out.

Run from source:

```powershell
python .\files_app.py
```

Build:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Auto update releases:

1. Set `APP_VERSION` in `server.py`.
2. Set `manifestUrl` in `update-config.json` to the HTTPS URL where `latest.json` will be hosted.
3. Open `release-manager.html` in your browser to generate `latest.json` from:
   - the new version number
   - release notes
   - the Discord package download link
   - a local setup exe/zip file, used to calculate SHA-256
4. Upload `latest.json` to the stable HTTPS manifest URL from step 2.

Every installed app reads the same manifest URL. For each new release you only replace that `latest.json` content.

If you prefer the portable zip release flow, build a release package and manifest:

```powershell
powershell -ExecutionPolicy Bypass -File .\create-release.ps1 -BaseUrl "https://your-domain.example/updates"
```

Upload both files from `releases` to that HTTPS folder:

```text
latest.json
6ure-files-<version>-win64.zip
```

The manifest format is:

```json
{
  "version": "1.0.1",
  "notes": "Optional release notes",
  "windows": {
    "url": "https://your-domain.example/updates/6ure-files-1.0.1-win64.zip",
    "sha256": "64 lowercase hex chars",
    "sizeBytes": 12345678,
    "packageType": "zip"
  }
}
```

For a setup exe hosted on Discord, use:

```json
{
  "version": "1.0.1",
  "notes": "Optional release notes",
  "windows": {
    "url": "https://cdn.discordapp.com/attachments/.../6ure-files-setup.exe?...",
    "sha256": "64 lowercase hex chars",
    "sizeBytes": 12345678,
    "packageType": "installer",
    "installerArgs": "/VERYSILENT /NORESTART",
    "successExitCodes": [0, 3010]
  }
}
```

The packaged app checks this manifest on startup and exposes an `Update` button. Install downloads the package, verifies
SHA-256, closes the app, then either runs the setup installer or replaces the application folder from a zip.

Discord Rich Presence:

1. Create a Discord Developer application and copy its Application ID.
2. Put that value in `discord-presence.json` as `clientId`, or set `REYLI_DISCORD_CLIENT_ID`.
3. Set `largeImage` to a Rich Presence asset key uploaded for that Discord app, or to an HTTPS image URL.

When configured, the app connects to the local Discord client and updates presence messages for sign-in, cloud browsing,
protected-list review, update checks, and upload progress. If `clientId` is empty, the feature stays visible in the UI as
needing setup but does not attempt to publish a Discord activity.

Important: Discord attachment CDN URLs can include expiring query parameters. Use Discord for the package only if you
are comfortable refreshing the package URL in `latest.json` for each release. The manifest URL itself should be a stable
HTTPS URL.

Discord updater bot:

The optional updater bot lives in:

```text
Developer Files/Updater Bot
```

Run it on your cloud server and point `update-config.json` to `https://your-update-server/latest.json`. Use `/release`
with a setup exe attachment or a Discord CDN package URL; the modal asks for version and release notes, then the bot
stores the package and updates the manifest.

Build for Apple Silicon macOS:

Run this on an Apple Silicon Mac from a native terminal, not Rosetta. PyInstaller
builds need to be created on the target operating system.

```bash
cd "Developer Files/Source Code"
chmod +x ./build-macos-arm64.sh
./build-macos-arm64.sh
```

Outputs:

```text
dist/6ure™ App.app
dist/6ure™ App Apple Silicon.dmg
```

Optional signing values can be supplied with environment variables:

```bash
CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" ./build-macos-arm64.sh
```
