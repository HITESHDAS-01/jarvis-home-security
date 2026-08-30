import yaml
import os
import sys
from pathlib import Path


def setup_wizard():
    print("=" * 50)
    print("JARVIS Home - Setup Wizard")
    print("=" * 50)
    print()

    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)

    settings_path = config_dir / "settings.yaml"
    cameras_path = config_dir / "cameras.yaml"

    if settings_path.exists():
        overwrite = input("Settings file exists. Overwrite? (y/n): ").lower()
        if overwrite != "y":
            print("Keeping existing settings.")
            return

    print("\n--- Telegram Setup ---")
    print("1. Open Telegram and search for @BotFather")
    print("2. Send /newbot and follow instructions")
    print("3. Copy the bot token")
    bot_token = input("\nEnter bot token: ").strip()

    print("\n4. Send any message to your bot")
    print("5. Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates")
    print("6. Find chat.id in the response")
    chat_id = input("Enter chat ID: ").strip()

    print("\n--- LLM Setup ---")
    print("Choose LLM provider:")
    print("1. Gemini (Free)")
    print("2. OpenAI (Paid)")
    print("3. Ollama (Local, Free)")
    llm_choice = input("Enter choice (1/2/3): ").strip()

    llm_config = {}
    if llm_choice == "1":
        api_key = input("Enter Gemini API key: ").strip()
        llm_config = {
            "provider": "gemini",
            "gemini": {"model": "gemini-1.5-flash", "api_key": api_key},
            "openai": {"model": "gpt-4o-mini", "api_key": ""},
            "ollama": {"model": "llama3.1", "base_url": "http://localhost:11434"},
        }
    elif llm_choice == "2":
        api_key = input("Enter OpenAI API key: ").strip()
        llm_config = {
            "provider": "openai",
            "gemini": {"model": "gemini-1.5-flash", "api_key": ""},
            "openai": {"model": "gpt-4o-mini", "api_key": api_key},
            "ollama": {"model": "llama3.1", "base_url": "http://localhost:11434"},
        }
    else:
        llm_config = {
            "provider": "ollama",
            "gemini": {"model": "gemini-1.5-flash", "api_key": ""},
            "openai": {"model": "gpt-4o-mini", "api_key": ""},
            "ollama": {"model": "llama3.1", "base_url": "http://localhost:11434"},
        }

    print("\n--- Camera Setup ---")
    print("Add your cameras (enter empty name to finish):")
    cameras = []

    while True:
        name = input("\nCamera name (or empty to finish): ").strip()
        if not name:
            break

        print("Connection modes: rtsp, http, mjpeg, onvif, wifi, lan, usb")
        mode = input("Connection mode: ").strip() or "rtsp"

        cam_config = {"name": name, "connection_mode": mode}

        if mode in ["usb"]:
            device_id = int(input("Device ID (0 for default): ").strip() or "0")
            cam_config["device_id"] = device_id
        elif mode in ["file"]:
            file_path = input("Video file path: ").strip()
            cam_config["file_path"] = file_path
        else:
            ip = input("Camera IP: ").strip()
            port = input("Port (default 554): ").strip() or "554"
            username = input("Username: ").strip()
            password = input("Password: ").strip()

            cam_config["ip"] = ip
            cam_config["port"] = port
            cam_config["username"] = username
            cam_config["password"] = password

        cam_config["zones"] = []
        cam_config["recording"] = {
            "enabled": True,
            "mode": "hybrid",
            "quality": "low",
            "retention_days": 7,
        }

        cameras.append(cam_config)
        print(f"Added: {name}")

    settings = {
        "jarvis": {"name": "JARVIS", "personality": "calm_reliable"},
        "security": {
            "mode": "home",
            "alert_threshold": "medium",
            "night_hours": {"start": "22:00", "end": "06:00"},
        },
        "detection": {
            "model": "yolov8n.pt",
            "confidence_threshold": 0.5,
            "classes_to_detect": ["person", "car", "motorcycle", "truck"],
            "frame_interval": 30,
        },
        "recording": {
            "base_path": "data/recordings",
            "snapshot_path": "data/snapshots",
            "max_clip_duration": 30,
            "pre_event_buffer": 5,
        },
        "telegram": {"bot_token": bot_token, "chat_id": chat_id},
        "llm": llm_config,
        "database": {"path": "data/events.db"},
    }

    with open(settings_path, "w") as f:
        yaml.dump(settings, f, default_flow_style=False)
    print(f"\nSettings saved to: {settings_path}")

    cameras_config = {"cameras": cameras}
    with open(cameras_path, "w") as f:
        yaml.dump(cameras_config, f, default_flow_style=False)
    print(f"Cameras saved to: {cameras_path}")

    print("\n" + "=" * 50)
    print("Setup complete!")
    print("Run: python main.py")
    print("=" * 50)


if __name__ == "__main__":
    setup_wizard()
