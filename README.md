# Telegram → MinIO Photo Uploader & AI‑Powered Random Picker Service

This Python service does two things:

1. **Telegram Bot**: Receives photos via Telegram, uploads them to a configured MinIO bucket, and replies with a presigned URL.
2. **HTTP API** (`/random`): Exposes a REST endpoint that returns a random, unused photo URL and AI‑generated caption, marking it as used.
3. **Reset Command** (`/reset`): Clears the used record so photos can be reused.

---

## Features

* Secure uploads from a single authorized Telegram chat (cropped to 3:2).
* Presigned URLs for direct access to uploaded images.
* AI‑generated captions (single‑sentence) using Google Gemini `generateContent` with inline image data.
* `/random` command on Telegram and `GET /random` HTTP API returning JSON `{url, caption}`.
* `/reset` command to clear the used‑photo history (`used.txt`).
* Persistent `used.txt` tracking to avoid repeats across sessions.
* Background Flask server on port `8000` with CORS support.
* Detailed logging for easy debugging.

---

## Prerequisites

* Python 3.8+ installed
* MinIO or any S3‑compatible endpoint accessible
* Telegram Bot Token from [@BotFather](https://t.me/BotFather)

---

## Installation

1. **Clone the repo** (or copy `main.py` and related files) into a folder, e.g. `/opt/teleMinio`:

   ```bash
   git clone <your-repo-url> /opt/teleMinio
   cd /opt/teleMinio
   ```

2. **Create a Python virtual environment**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   pip install python-dotenv python-telegram-bot minio flask flask-cors pillow
   ```

4. **Create a `.env` file** in the project root with:

   ```ini
   TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
   MINIO_ENDPOINT=your.minio.server:9000
   MINIO_ACCESS_KEY=your_access_key
   MINIO_SECRET_KEY=your_secret_key
   MINIO_BUCKET=photos
   ALLOWED_CHAT_ID=123456789   # your Telegram user/chat ID
   ```

5. **Ensure `used.txt` exists** (the service will also create it if missing):

   ```bash
   touch used.txt
   ```

---

## Running the Service

### Manually

```bash
source venv/bin/activate
python main.py
```

* Bot will start polling for Telegram messages.
* Flask HTTP server will be available at `http://0.0.0.0:8000/random`.

### As a systemd Service

1. Copy `telegram-minio-uploader.service` to `/etc/systemd/system/`:

   ```ini
   [Unit]
   Description=Telegram MinIO Uploader Service
   After=network.target

   [Service]
   Type=simple
   User=your_user
   WorkingDirectory=/opt/teleMinio
   EnvironmentFile=/opt/teleMinio/.env
   ExecStart=/opt/teleMinio/venv/bin/python /opt/teleMinio/main.py
   Restart=on-failure
   RestartSec=10s

   [Install]
   WantedBy=multi-user.target
   ```
2. Reload, enable, and start:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-minio-uploader
   sudo systemctl start telegram-minio-uploader
   sudo journalctl -u telegram-minio-uploader -f
   ```

---

## Obsidian Templater Integration

1. **User Script**: Save `randomS3.js` (or `randomMinio.js`) under your vault’s user scripts folder (e.g., `templates/templater-scripts/`).
2. **Templater Settings**: Point **Script files folder location** to that folder and click **Reload scripts**.
3. **Daily Note Template**: Example `daily-note.md`:

   ```md
   # <% tp.date.now("YYYY-MM-DD") %>

   **Picture of the Day**  
   <%*  
     const raw = await tp.system.run('curl -s http://localhost:8000/random');
     const j   = JSON.parse(raw);
     tR     = `![Daily Photo](${j.url})  \n> ${j.caption}`;
   %>

   ## Goals today
   - [ ] …
   ```
4. **Create a new Daily Note**: Your note will include a random, unused photo URL served by your local service.

---

## API Reference

### `GET /random`

Returns a JSON object with a random unused photo URL:

```json
{ "url": "https://your.minio.server:9000/photos/<object-key>?<signed-params>" }
```

* **404** if no photos or all used.
* **500** on server error.

---

## License

This project is provided under the MIT License. Feel free to modify and use it in your own setup.
