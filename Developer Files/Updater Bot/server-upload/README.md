# 6ure Files Updater Bot

This service has two jobs:

- Discord admin command: `/release`
- Public update endpoints for installed apps:
  - `GET /latest.json`
  - `GET /packages/<file>`

The app should point `update-config.json` to:

```json
{
  "manifestUrl": "http://217.154.173.102:12988/latest.json",
  "channel": "stable",
  "allowInsecure": true
}
```

All installed apps stay connected to that one stable manifest URL.

Current server:

```text
PUBLIC_BASE_URL=http://217.154.173.102:12988
HOST=0.0.0.0
PORT=12988
```

## Setup

```powershell
cd "Developer Files\Updater Bot"
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env`:

- `DISCORD_TOKEN`: bot token
- `DISCORD_GUILD_ID`: your Discord server ID, recommended for instant slash command sync
- `DISCORD_ALLOWED_USER_IDS`: comma-separated Discord user IDs allowed to publish releases
- `PUBLIC_BASE_URL`: public URL for this cloud server

Run:

```powershell
.\.venv\Scripts\python bot_server.py
```

On Linux:

```bash
cd "Developer Files/Updater Bot"
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
./.venv/bin/python bot_server.py
```

## Release Flow

Use one of these:

```text
/release package:<setup.exe>
/release package_url:<https Discord CDN link>
```

The command opens a modal asking for:

- Version
- Release notes

After submit, the service downloads the package, calculates SHA-256, stores the package under `data/packages`, and writes
`data/latest.json`.

Installed apps check `/latest.json`, show `Install Update`, download `/packages/<file>`, verify SHA-256, and run the
installer.

## Notes

Do not put the Discord bot token inside the desktop app. The desktop app only needs the public manifest URL.
