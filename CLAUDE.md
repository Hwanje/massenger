# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VaultChat Advanced is a real-time End-to-End Encrypted secure messenger. The project is minimal in structure — a single Python backend (`main.py`), a single-page frontend (`index.html`), and a SQLite database auto-created at runtime.

## Running the Server

```bash
# Install dependencies
pip install -r requirements.txt

# Run server (recommended)
uvicorn main:socket_app --host 0.0.0.0 --port 8000 --reload

# Or directly
python main.py
```

The server serves `index.html` as the frontend on port 8000. There are no build steps — the frontend is plain HTML/CSS/JS with CDN-loaded libraries.

## Environment Setup

Create a `.env` file:

```env
ADMIN_ID=admin
ADMIN_PW=your_secure_password
ADMIN_2FA_SECRET=your_base32_secret   # generate with: python -c "import pyotp; print(pyotp.random_base32())"
SECRET_KEY=your_random_secret_key
ADMIN_IP_WHITELIST=192.168.1.1,10.0.0.0/24  # optional
RATE_LIMIT_WINDOW=60
RATE_LIMIT_MAX_REQUESTS=100
```

## Architecture

### Backend (`main.py`)

FastAPI + python-socketio ASGI app mounted together as `socket_app`. Key globals:

- `user_sessions` (dict) — in-memory map of `sid → {nickname, room, ip}` for connected socket clients
- `admin_tokens` (dict) — in-memory map of `token → {admin_id, ip, expires}`
- `rooms_otp_cache` (dict) — in-memory map of `room_id → otp_secret` to avoid repeated DB hits

The SQLite database (`vaultchat.db`) is auto-initialized on startup via `init_database()` with 7 tables: `users`, `rooms`, `messages`, `admin_logs`, `sessions`, `ip_whitelist`, `rate_limits`.

**Communication pattern:** Most user-facing operations happen over Socket.IO events. REST endpoints are only used for admin login (`POST /api/admin/login`) and authenticated admin data fetches (`GET /api/admin/stats`, `GET /api/admin/logs`).

**Room access flow:** Room creator receives a TOTP secret (`pyotp`, 60-second interval). To join, users enter the current 6-digit OTP. After joining, they set a nickname via a `set_nickname` event before they can send messages.

**Admin auth flow:** `POST /api/admin/login` checks password (SHA-256 + SECRET_KEY salt), verifies 2FA TOTP, checks IP whitelist, then issues a JWT (24h expiry). Admin then authenticates the Socket.IO connection via `admin_auth` event passing the JWT.

### Frontend (`index.html`)

Single-file SPA — HTML, CSS, and JS all in one file (~800 lines). No build tooling.

Libraries loaded from CDN:
- Socket.IO client 4.7.2
- Crypto-JS 4.2.0 (AES-256 E2E encryption)

Three UI sections toggled via CSS display:
1. `#authSection` — room create/join with OTP input
2. `#chatSection` — chat UI with file upload
3. `#adminPanel` — admin dashboard with stats, room/user management, audit logs

The frontend connects to the same origin as the page is served from (no separate API URL config needed in dev).

### Secondary client (`app.py`)

An alternative Flet-based GUI client (63 lines). Not the primary interface — the main frontend is `index.html`.

## Key Constraints

- **No framework for frontend** — vanilla JS only; do not add npm/bundler tooling
- **SQLite only** — no ORM; all DB access uses raw `sqlite3` with context managers
- **File size limit** — messages capped at 5000 chars; file transfers capped at 5MB
- **Nickname rules** — 2–20 chars, alphanumeric + underscore/dash only
- **Rate limiting** — 100 requests per 60s per IP, enforced in `check_rate_limit()`
