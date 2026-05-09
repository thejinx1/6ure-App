# 6ure App GitHub Pages Update Server

This folder is the GitHub Pages update server.

## Easy Release Panel

For normal use, run the local release panel:

```powershell
.\start-release-panel.ps1
```

It opens:

```text
http://127.0.0.1:8765/
```

The panel can:

- connect the app to `https://thejinx1.github.io/6ure-App/latest.json`
- run the PyInstaller build
- calculate SHA-256 for your setup EXE or ZIP
- create/update the GitHub Release
- upload the setup file as a release asset
- commit the new `latest.json` file to the Pages repo

The GitHub token is not stored. Use a token with repo access for:

```text
Contents: read/write
Releases: read/write
```

Use this repo pattern:

```text
Repo name: 6ure-App
Pages URL: https://thejinx1.github.io/6ure-App/
Manifest:  https://thejinx1.github.io/6ure-App/latest.json
```

## Why GitHub Releases for setup EXE files?

Keep `latest.json` on GitHub Pages, but upload setup EXE files to GitHub Releases. GitHub Pages has site/repo/bandwidth
limits, while GitHub's docs recommend Releases for distributing large binaries.

## First Setup

1. Use the public GitHub repo named `6ure-App`.
2. Upload this folder's files to that repo:
   - `.nojekyll`
   - `index.html`
   - `latest.json`
   - `README.md`
   - `make-latest.ps1`
   - `set-app-update-config.ps1`
3. In GitHub repo settings, enable Pages:
   - Source: `Deploy from a branch`
   - Branch: `main`
   - Folder: `/root`
4. Update the app config before building your setup:

```powershell
.\set-app-update-config.ps1 -Owner "thejinx1" -Repo "6ure-App"
```

This writes:

```json
{
  "manifestUrl": "https://thejinx1.github.io/6ure-App/latest.json",
  "githubReleasesUrl": "https://github.com/thejinx1/6ure-App/releases",
  "channel": "stable",
  "allowInsecure": false
}
```

## Publishing A New Version

Recommended method:

1. Run `.\start-release-panel.ps1`.
2. Fill GitHub owner/repo/token.
3. Click `App Config Bagla`.
4. Enter version and release notes.
5. Select the setup EXE.
6. Click `GitHub'a Publish Et`.

Manual method:

1. Build your setup EXE.
2. Create a GitHub Release with tag `v1.0.1`.
3. Upload the setup EXE as a release asset.
4. Generate a new `latest.json`:

```powershell
.\make-latest.ps1 `
  -Owner "thejinx1" `
  -Repo "6ure-App" `
  -Version "1.0.1" `
  -PackagePath "C:\path\to\6ure-files-setup-1.0.1.exe" `
  -Notes "Added updater system"
```

5. Commit and push the updated `latest.json`.

Installed apps will read the new version from:

```text
https://thejinx1.github.io/6ure-App/latest.json
```

## Installer Args

Default installer args for the generated NSIS setup are:

```text
/S
```

Use `/S` for NSIS. If you switch to Inno Setup later, use `/VERYSILENT /NORESTART`. If it is MSI, use
`/quiet /norestart`.
