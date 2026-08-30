# JARVIS Home Security System

AI-powered home security assistant that monitors CCTV cameras, detects important activity, and communicates through Telegram.

## Features

- Multi-camera support (RTSP, HTTP, MJPEG, ONVIF, WiFi, LAN, USB)
- YOLOv8 object detection (person, car, motorcycle, truck)
- Automatic event recording and snapshots
- Telegram alerts with images
- Natural language chat through Telegram
- Security modes (Home, Away, Sleep)
- Camera zones and security rules
- Auto-reconnect on camera disconnect
- Event deduplication
- Disk space monitoring
- Local recording (no cloud required)

## Quick Start

### Windows

1. Double-click `setup.bat` to run setup wizard
2. Follow the prompts to configure cameras and Telegram
3. Double-click `run.bat` to start JARVIS

### Linux/Mac

```bash
chmod +x setup.sh run.sh
./setup.sh
./run.sh
```

### Docker

```bash
docker-compose up -d
```

## Manual Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Settings

Edit `config/settings.yaml`:

```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"

llm:
  provider: "gemini"  # gemini, openai, ollama
  gemini:
    api_key: "YOUR_API_KEY"
```

### 3. Configure Cameras

Edit `config/cameras.yaml`:

```yaml
cameras:
  - name: "Front Gate"
    connection_mode: "rtsp"
    ip: "192.168.1.100"
    port: "554"
    username: "admin"
    password: "password"
```

### 4. Run

```bash
python main.py
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/status` | System status |
| `/mode <home\|away\|sleep>` | Change security mode |
| `/events` | Recent events |
| `/cameras` | Camera status |
| `/snapshot <camera>` | Get camera snapshot |
| `/clip <camera>` | Get last event clip |
| `/history <hours>` | Event history |
| `/summary` | Daily summary |
| `/zones` | List security zones |
| `/mute <minutes>` | Mute alerts |

## Connection Modes

| Mode | Description |
|------|-------------|
| `rtsp` | RTSP stream (Hikvision, Dahua, etc.) |
| `http` | HTTP stream |
| `mjpeg` | MJPEG stream |
| `onvif` | ONVIF protocol |
| `wifi` | WiFi camera (Tapo, Ezviz) |
| `lan` | LAN direct IP |
| `usb` | USB camera (laptop webcam) |
| `file` | Video file (testing) |

## Configuration Files

- `config/settings.yaml` - General settings, LLM, Telegram
- `config/cameras.yaml` - Camera configurations
- `config/zones.yaml` - Security zones and rules

## Logs

- `logs/jarvis.log` - All logs (rotated daily)
- `logs/errors.log` - Errors only
- `logs/security.log` - Security events

## Windows Service

To install as a Windows service:

```bash
pip install pywin32
python service.py install
python service.py start
```

## Docker Deployment

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Directory Structure

```
jarvis-home/
├── main.py              # Entry point
├── setup_wizard.py      # Setup wizard
├── service.py           # Windows service
├── requirements.txt     # Dependencies
├── Dockerfile           # Docker image
├── docker-compose.yml   # Docker compose
├── run.bat              # Windows run script
├── run.sh               # Linux run script
├── config/
│   ├── settings.yaml    # General settings
│   ├── cameras.yaml     # Camera configs
│   └── zones.yaml       # Security zones
├── core/
│   ├── camera_manager.py    # Camera handling
│   ├── detector.py          # YOLO detection
│   ├── event_engine.py      # Event processing
│   ├── recorder.py          # Video recording
│   ├── storage.py           # SQLite database
│   ├── zone_manager.py      # Zone management
│   ├── logger.py            # Logging system
│   ├── config_validator.py  # Config validation
│   └── disk_monitor.py      # Disk monitoring
├── bot/
│   └── telegram_bot.py  # Telegram interface
├── llm/
│   └── chat_engine.py   # LLM integration
└── data/
    ├── recordings/      # Video recordings
    ├── snapshots/       # Event snapshots
    └── events.db        # Event database
```

## License

Private - All rights reserved.
