# Telegram → MinIO Photo Uploader & AI-Powered Random Picker Service

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Architecture](https://img.shields.io/badge/arch-serverless-lightgrey)

## 🌟 Enhanced Features

### Core Functionality
- **Secure Telegram Bot** 
  - Single authorized chat ID restriction
  - 3:2 auto-cropping for uploaded photos
  - Presigned URL generation

- **AI-Powered Service**
  - Google Gemini `generateContent` integration
  - Smart caption caching system
  - Async processing for faster responses

### New Improvements
- **Advanced Image Handling**
  - Dual-mode processing (original storage + optimized AI compression)
  - Automatic retry mechanism (3 attempts)
  - Intelligent size validation (>5MB rejection)

- **Enhanced Tracking System**
  - JSON-based caption storage (`captions.json`)
  - Atomic write operations
  - Automatic file creation if missing

- **Performance Optimizations**
  - Background Flask server (non-blocking)
  - Connection pooling for MinIO
  - Exponential backoff for API failures

## 🛠️ Technical Stack

| Component          | Technology               | Version       |
|--------------------|--------------------------|---------------|
| Backend Framework  | Python                   | 3.8+          |
| Telegram Library   | python-telegram-bot      | v20+          |
| Cloud Storage      | MinIO                    | S3-compatible |
| AI Service         | Google Gemini API        | v1beta        |
| Web Server         | Flask                    | 2.0+          |
| Image Processing   | Pillow                   | 9.0+          |

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8+
- MinIO server (local or cloud)
- Telegram Bot Token
- Google Gemini API Key

### Quick Start
```bash
# Clone and setup
git clone <your-repo-url> /opt/teleMinio
cd /opt/teleMinio
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
nano .env  # Edit with your credentials

# Initialize tracking files
touch used.txt captions.json
```

## ⚙️ Configuration Guide

### Environment Variables
```ini
# Required
TELEGRAM_TOKEN=your_bot_token
MINIO_ENDPOINT=your.minio.server:9000
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
AI_API_KEY=your_gemini_api_key
ALLOWED_CHAT_ID=123456789

# Optional
MINIO_BUCKET=photos          # Default
FLASK_PORT=8000              # Default
MAX_IMAGE_SIZE=5242880       # 5MB in bytes
```

### File Structure
```
teleMinio/
├── app/
│   ├── config.py        # Configuration loader
│   ├── storage.py       # MinIO operations (enhanced)
│   ├── ai_service.py    # Gemini integration (with retry)
│   ├── utils.py         # File management (atomic writes)
│   └── handlers.py      # Telegram handlers (async)
├── main.py              # Entry point
├── requirements.txt     # Dependencies
├── used.txt            # Track used photos
└── captions.json       # AI-generated captions cache
```

## 💻 Usage Examples

### Telegram Commands
| Command   | Description                          | Response Example                     |
|-----------|--------------------------------------|--------------------------------------|
| `/start`  | Show welcome message                 | "Send photos or use /random"        |
| `/random` | Get random photo                    | JSON with URL and AI caption        |
| `/reset`  | Clear usage history                 | "Reset complete"                    |
| (Photo)   | Upload image                       | "Uploaded! URL: ... Caption: ..."   |

### API Endpoints
**GET /random**
```bash
curl -s http://localhost:8000/random | jq
```
```json
{
  "url": "https://minio.example.com/photos/uuid.jpg?signature",
  "caption": "A beautiful sunset over mountains"
}
```

## 🐛 Troubleshooting Guide

| Symptom                      | Solution                          | Verification Command              |
|------------------------------|-----------------------------------|-----------------------------------|
| Upload failures              | Check MinIO connection           | `curl -v $MINIO_ENDPOINT`        |
| Caption generation errors    | Verify Gemini API key             | `curl -H "Content-Type: application/json" -d @test.json "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=$AI_API_KEY"` |
| High memory usage            | Monitor image sizes               | `ls -lh /tmp/teleminio_uploads/`  |
| Telegram auth failures       | Confirm ALLOWED_CHAT_ID           | Check chat ID via @userinfobot    |

## 📜 License & Attribution

MIT License - See [LICENSE](LICENSE) for full text.

**Third-party services:**
- [Google Gemini API](https://ai.google.dev/)
- [MinIO](https://min.io/)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
