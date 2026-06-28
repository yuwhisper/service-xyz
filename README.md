# Service XYZ

API management console (FastAPI + Vue 3 CDN, zero build).

## Local development

```bash
pip install -r requirements.txt
cp config.json.example config.json   # edit with your DB credentials
cp .env.example .env                 # optional overrides
python scripts/setup.py
python server/main.py
```

Open http://localhost:3000 — default login: `admin` / `admin123`

## Production deploy

Server path: `/opt/service-zyx`, port **8800**.

```bash
bash /opt/service-zyx/deploy/deploy.sh
```

**Note:** The server may not reach GitHub directly. If `git pull` fails, push from your machine and re-upload via SFTP, or configure a Git proxy/mirror on the server.

GitHub Actions auto-deploy (optional): add repository secrets `SSH_HOST`, `SSH_USER`, `SSH_KEY`, then push to `main` triggers [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml).

## Access

| Entry | Purpose |
|-------|---------|
| `https://121.43.75.44:8443/` | Admin UI (SPA) |
| `https://www.ywzhaoran.xyz/service/zyx/*` | API |

## API prefix

All routes under `/service/zyx/` — see `CLAUDE.md` for full list.
