import os
import re
import json
import asyncio
import yaml
import psutil
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update, Bot
from telegram.error import TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from core.logger import get_logger, SecurityLogger

logger = get_logger("telegram")
security_log = SecurityLogger()


class IntentParser:
    ALLOWED_ACTIONS = {
        "visual", "snapshot", "status", "mode", "events", "cameras", "zones",
        "disk", "restart", "addcam", "delcam", "recpath", "setting", "mute",
        "help", "chat", "addzone", "editzone", "delzone",
    }

    INTENTS = {
        "visual": {
            "keywords": [
                "what is in", "whats in", "what's in", "what do you see",
                "what can you see", "whats going on", "what's going on",
                "camera me", "cam me", "camera mein", "cam mein",
                "kya dikh", "kya dik", "dekh ke bata", "camera dekh",
                "kya chal raha", "kya ho raha", "abhi kya hai", "live bata",
                "feed me", "feed mein", "screen pe", "screen par",
            ],
            "params": ["camera"],
        },
        "snapshot": {"keywords": ["snapshot", "photo", "foto", "picture", "pic", "image", "dikhao", "dikha", "capture", "bhejo"], "params": ["camera"]},
        "status": {"keywords": ["status", "haal", "health", "system kaisa", "sab thik", "all ok", "situation"], "params": []},
        "mode": {"keywords": ["mode", "set mode", "change mode", "security mode", "home mode", "away mode", "sleep mode"], "params": ["mode"]},
        "events": {"keywords": ["events", "alerts", "kya hua", "what happened", "history", "activity", "aaj kya", "kal kya"], "params": ["hours"]},
        "cameras": {"keywords": ["cameras", "camera list", "sab camera", "camera status", "kaunse camera"], "params": []},
        "zones": {"keywords": ["zones", "zone list", "security zones", "area list", "zones bata"], "params": []},
        "disk": {"keywords": ["disk", "storage", "space", "jagah", "kitna bacha", "memory", "recording space"], "params": []},
        "restart": {"keywords": ["restart", "reboot", "start over", "dobara chalu", "restart karo"], "params": []},
        "addcam": {"keywords": ["add camera", "naya camera", "camera add", "new camera", "camera jodo"], "params": ["name", "ip"]},
        "delcam": {"keywords": ["delete camera", "camera delete", "camera hatao", "remove camera", "camera nikalo"], "params": ["camera"]},
        "recpath": {"keywords": ["recording path", "save path", "path change", "path set", "recording kaha"], "params": ["path"]},
        "setting": {"keywords": ["setting", "config", "change setting", "threshold", "confidence"], "params": ["key", "value"]},
        "mute": {"keywords": ["mute", "silence", "chup", "alert off", "notifications off", "disturb mat"], "params": ["minutes"]},
        "addzone": {"keywords": ["add zone", "naya zone", "zone add", "new zone", "zone banao"], "params": ["zone", "camera"]},
        "editzone": {"keywords": ["edit zone", "zone edit", "zone change", "zone update"], "params": ["zone"]},
        "delzone": {"keywords": ["delete zone", "zone delete", "zone hatao", "remove zone", "zone nikalo"], "params": ["zone"]},
        "help": {"keywords": ["help", "commands", "kya kar sakta hai", "options", "madad"], "params": []},
    }

    def parse(self, text, llm_engine=None, camera_names=None):
        text_lower = self._normalize_text(text)

        for intent, config in self.INTENTS.items():
            for keyword in config["keywords"]:
                if self._contains_keyword(text_lower, keyword):
                    return intent, self._extract_params(intent, text, text_lower, camera_names)

        if llm_engine:
            return self._llm_parse(text, llm_engine)
        return "chat", {"message": text}

    def _normalize_text(self, text):
        text = (text or "").lower().strip()
        replacements = {
            "what's": "whats",
            "cámara": "camera",
            "camara": "camera",
            "caméra": "camera",
            "kamera": "camera",
            "camra": "camera",
            "camrea": "camera",
            "camer": "camera",
            "fone": "phone",
            "fotograph": "photo",
            "picuture": "picture",
            "stats": "status",
            "sttaus": "status",
            "alrt": "alert",
            "alrts": "alerts",
            "vedio": "video",
            "vidio": "video",
        }
        for old, new in replacements.items():
            text = re.sub(rf"\b{re.escape(old)}\b", new, text)
        text = re.sub(r"[^\w:/.\s-]", " ", text, flags=re.UNICODE)
        return re.sub(r"\s+", " ", text).strip()

    def _contains_keyword(self, text, keyword):
        keyword = self._normalize_text(keyword)
        if keyword in text:
            return True
        return self._fuzzy_contains(text, keyword)

    def _fuzzy_contains(self, text, keyword):
        words = text.split()
        target = keyword.split()
        if not words or len(target) <= 1 or len(keyword) < 5:
            return False

        window = len(target)
        for i in range(0, max(1, len(words) - window + 1)):
            phrase = " ".join(words[i:i + window])
            if SequenceMatcher(None, phrase, keyword).ratio() >= 0.9:
                return True
        return False

    def _extract_params(self, intent, original_text, normalized_text, camera_names=None):
        params = {}

        if intent in ["visual", "snapshot", "delcam"]:
            camera = self._extract_camera_name(normalized_text, camera_names)
            if camera:
                params["camera"] = camera

        if intent == "mode":
            for mode in ["home", "away", "sleep"]:
                if mode in normalized_text:
                    params["mode"] = mode
                    break

        elif intent == "events":
            hours = self._extract_hours(normalized_text)
            if hours:
                params["hours"] = hours

        elif intent == "recpath":
            match = re.search(r'([A-Za-z]:\\[^\s]+|[^\s]+/[^\s]+)', original_text)
            if match:
                params["path"] = match.group(1)

        elif intent == "addcam":
            ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', original_text)
            if ip_match:
                params["ip"] = ip_match.group(1)
            name_match = re.search(r'(?:named?|naam|called?)\s+(\w[\w\s]*?)(?:\s+(?:at|pe|on|ip)|$)', normalized_text)
            if name_match:
                params["name"] = name_match.group(1).strip().title()

        elif intent == "mute":
            num_match = re.search(r'(\d+)', normalized_text)
            if num_match:
                params["minutes"] = int(num_match.group(1))

        return params

    def _extract_camera_name(self, text, camera_names=None):
        names = list(camera_names or [])
        names.extend(["front gate", "main door", "backyard", "driveway", "parking area", "local cam", "phone cam"])

        for name in names:
            normalized_name = self._normalize_text(name)
            if normalized_name and normalized_name in text:
                return name
            if normalized_name and self._fuzzy_contains(text, normalized_name):
                return name
        return ""

    def _extract_hours(self, text):
        if "aaj" in text or "today" in text:
            return 24
        if "kal" in text or "yesterday" in text:
            return 48

        match = re.search(r"(\d+)\s*(h|hr|hrs|hour|hours|ghante|ghanta)", text)
        if match:
            return int(match.group(1))
        return None

    def _llm_parse(self, text, llm_engine):
        prompt = f"""Parse this user message into a JSON action. Return ONLY valid JSON.

User message: "{text}"

The user may write in ANY language or mix languages. Understand intent across Hindi, Hinglish, English, Spanish, French, Arabic, Bengali, Marathi, Tamil, Telugu, Punjabi, Gujarati, Urdu, and other languages. Preserve camera names exactly when possible.

Possible actions:
- visual: {{"action":"visual","camera":"Camera Name"}}
- snapshot: {{"action":"snapshot","camera":"Camera Name"}}
- status: {{"action":"status"}}
- mode: {{"action":"mode","mode":"home/away/sleep"}}
- events: {{"action":"events","hours":2}}
- cameras: {{"action":"cameras"}}
- zones: {{"action":"zones"}}
- disk: {{"action":"disk"}}
- restart: {{"action":"restart"}}
- addcam: {{"action":"addcam","name":"Name","ip":"x.x.x.x","mode":"rtsp/http"}}
- delcam: {{"action":"delcam","camera":"Camera Name"}}
- recpath: {{"action":"recpath","path":"D:\\Recordings"}}
- setting: {{"action":"setting","key":"key","value":"value"}}
- mute: {{"action":"mute","minutes":30}}
- help: {{"action":"help"}}
- chat: {{"action":"chat","message":"original message"}}

Return JSON only:"""
        try:
            response = llm_engine.chat(prompt)
            match = re.search(r'\{.*?\}', response or "", re.DOTALL)
            if match:
                data = json.loads(match.group())
                action = data.pop("action", "chat")
                if action in self.ALLOWED_ACTIONS:
                    return action, data
        except Exception as e:
            logger.error(f"LLM parse error: {e}")
        return "chat", {"message": text}


class JarvisBot:
    PLACEHOLDER_VALUES = {"", "YOUR_BOT_TOKEN_HERE", "YOUR_CHAT_ID_HERE"}

    def __init__(self, config, camera_manager, event_engine, storage, llm_engine, zone_manager):
        self.config = config
        self.camera_manager = camera_manager
        self.event_engine = event_engine
        self.storage = storage
        self.llm_engine = llm_engine
        self.zone_manager = zone_manager
        self.web_dashboard = None

        self.bot_token = config.get("telegram", {}).get("bot_token", "")
        self.chat_id = config.get("telegram", {}).get("chat_id", "")

        self.security_mode = config.get("security", {}).get("mode", "home")
        self.app = None
        self.intent_parser = IntentParser()
        self._main_loop = None

        self.camera_manager.register_health_callback(self._on_camera_health_change)

    def _telegram_configured(self):
        return self.bot_token not in self.PLACEHOLDER_VALUES and self.chat_id not in self.PLACEHOLDER_VALUES

    def set_web_dashboard(self, dashboard):
        self.web_dashboard = dashboard

    def set_main_loop(self, loop):
        self._main_loop = loop

    def _on_camera_health_change(self, camera_name, new_status, old_status):
        if not self._telegram_configured():
            return
        if not self._main_loop:
            logger.warning("Main event loop not set, cannot send camera health alert")
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._send_camera_health_alert(camera_name, new_status, old_status),
                self._main_loop
            )
        except Exception as e:
            logger.error(f"Failed to queue camera health alert: {e}")

    async def _send_camera_health_alert(self, camera_name, new_status, old_status):
        if not self._telegram_configured():
            return
        bot = Bot(token=self.bot_token)
        if new_status == "offline":
            text = f"Camera Offline\n\nCamera: {camera_name}\nStatus: OFFLINE\nTime: {datetime.now().strftime('%I:%M %p')}\n\nAuto-reconnect attempting."
            security_log.log_camera_offline(camera_name)
        elif new_status == "online" and old_status in ["offline", "unknown"]:
            text = f"Camera Online\n\nCamera: {camera_name}\nStatus: ONLINE\nTime: {datetime.now().strftime('%I:%M %p')}\n\nConnection restored."
            security_log.log_camera_online(camera_name)
        else:
            return
        try:
            await bot.send_message(chat_id=self.chat_id, text=text)
            logger.info(f"Camera health alert sent: {camera_name} -> {new_status}")
        except Exception as e:
            logger.error(f"Failed to send camera health alert: {e}")

    def build_app(self):
        self.app = Application.builder().token(self.bot_token).build()

        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("mode", self.cmd_mode))
        self.app.add_handler(CommandHandler("events", self.cmd_events))
        self.app.add_handler(CommandHandler("cameras", self.cmd_cameras))
        self.app.add_handler(CommandHandler("snapshot", self.cmd_snapshot))
        self.app.add_handler(CommandHandler("clip", self.cmd_clip))
        self.app.add_handler(CommandHandler("history", self.cmd_history))
        self.app.add_handler(CommandHandler("summary", self.cmd_summary))
        self.app.add_handler(CommandHandler("zones", self.cmd_zones))
        self.app.add_handler(CommandHandler("addzone", self.cmd_addzone))
        self.app.add_handler(CommandHandler("editzone", self.cmd_editzone))
        self.app.add_handler(CommandHandler("delzone", self.cmd_delzone))
        self.app.add_handler(CommandHandler("mute", self.cmd_mute))
        self.app.add_handler(CommandHandler("addcam", self.cmd_addcam))
        self.app.add_handler(CommandHandler("delcam", self.cmd_delcam))
        self.app.add_handler(CommandHandler("disk", self.cmd_disk))
        self.app.add_handler(CommandHandler("restart", self.cmd_restart))
        self.app.add_handler(CommandHandler("recpath", self.cmd_recpath))
        self.app.add_handler(CommandHandler("setting", self.cmd_setting))

        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        return self.app

    # ==================== COMMAND HANDLERS ====================

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "JARVIS Home Security System\n\n"
            "I'm your AI security assistant with full system control.\n\n"
            "Quick Commands:\n"
            "/status - System status\n"
            "/cameras - Camera list\n"
            "/snapshot <cam> - Get photo\n"
            "/mode <home|away|sleep> - Change mode\n"
            "/events - Recent events\n"
            "/disk - Storage info\n"
            "/restart - Restart system\n\n"
            "Or just tell me what to do!\n"
            "Examples:\n"
            "- \"Front gate ka snapshot bhejo\"\n"
            "- \"Recording path D:\\Recordings karo\"\n"
            "- \"Naya camera add karo\""
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "JARVIS Commands:\n\n"
            "System:\n"
            "/status - System status\n"
            "/disk - Disk space\n"
            "/restart - Restart system\n"
            "/help - This message\n\n"
            "Cameras:\n"
            "/cameras - Camera status\n"
            "/snapshot <cam> - Get photo\n"
            "/clip <cam> - Get last clip\n"
            "/addcam <name> <ip> [mode] - Add camera\n"
            "/delcam <name> - Delete camera\n\n"
            "Security:\n"
            "/mode <home|away|sleep> - Change mode\n"
            "/events [hours] - Recent events\n"
            "/zones - List zones\n"
            "/addzone <name> <camera> - Add zone\n"
            "/editzone <name> <setting> <value> - Edit zone\n"
            "/delzone <name> - Delete zone\n"
            "/mute <minutes> - Mute alerts\n\n"
            "Settings:\n"
            "/recpath <path> - Set recording path\n"
            "/setting <key> <value> - Change setting\n\n"
            "Natural Language:\n"
            "Just type what you want!\n"
            "- \"Front gate ka snapshot bhejo\"\n"
            "- \"Recording path D:\\CCTV karo\"\n"
            "- \"Kya hua hai aaj?\""
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            import psutil
            camera_status = self.camera_manager.get_camera_status()
            recent_events = self.storage.get_recent_events(hours=24, limit=5)
            
            # PC Stats
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage(os.getcwd())
            
            status_text = f"JARVIS Status\n\n"
            status_text += f"Mode: {self.security_mode.upper()}\n\n"
            status_text += f"PC Stats:\n"
            status_text += f"  CPU: {cpu}%\n"
            status_text += f"  RAM: {mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)\n"
            status_text += f"  Disk: {disk.percent}% ({disk.free // (1024**3)}GB free)\n\n"
            
            # Cameras
            online_count = sum(1 for s in camera_status.values() if s["connected"])
            status_text += f"Cameras: {online_count}/{len(camera_status)} online\n"
            for name, status in camera_status.items():
                icon = "ON" if status["connected"] else "OFF"
                status_text += f"  {name}: {icon}\n"
            
            # Recent Events with time
            if recent_events:
                status_text += "\nEvents (24h):\n"
                for e in recent_events:
                    ts = e.get("timestamp", "")
                    try:
                        dt = datetime.fromisoformat(ts)
                        time_str = dt.strftime("%I:%M %p")
                    except:
                        time_str = ts[:16]
                    status_text += f"  {time_str} | {e.get('camera_name')} - {e.get('event_type')}\n"
            else:
                status_text += "\nNo events in 24h.\n"
            
            await update.message.reply_text(status_text)
        except Exception as e:
            logger.error(f"Error in /status: {e}")
            await update.message.reply_text("Error getting status.")

    async def cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if context.args:
                new_mode = context.args[0].lower()
                if new_mode in ["home", "away", "sleep"]:
                    old_mode = self.security_mode
                    self.security_mode = new_mode
                    self.config["security"]["mode"] = new_mode
                    self._save_config()
                    security_log.log_mode_change(old_mode, new_mode, user="telegram")
                    await update.message.reply_text(f"Mode changed: {old_mode.upper()} → {new_mode.upper()}")
                else:
                    await update.message.reply_text("Invalid mode. Use: home, away, or sleep")
            else:
                await update.message.reply_text(f"Current mode: {self.security_mode.upper()}\n\nUsage: /mode <home|away|sleep>")
        except Exception as e:
            logger.error(f"Error in /mode: {e}")
            await update.message.reply_text("Error changing mode.")

    async def cmd_events(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            hours = 2
            if context.args:
                try:
                    hours = int(context.args[0])
                except ValueError:
                    pass
            events = self.storage.get_recent_events(hours=hours, limit=10)
            if not events:
                await update.message.reply_text(f"No events in last {hours}h.")
                return
            events_text = f"Events ({hours}h):\n\n"
            for event in events:
                timestamp = event.get("timestamp", "")
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%I:%M %p")
                except:
                    time_str = timestamp
                events_text += f"[{time_str}] {event.get('camera_name', 'N/A')}\n  {event.get('event_type', 'N/A')} - {event.get('description', 'N/A')}\n\n"
            await update.message.reply_text(events_text)
        except Exception as e:
            logger.error(f"Error in /events: {e}")
            await update.message.reply_text("Error getting events.")

    async def cmd_cameras(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            camera_status = self.camera_manager.get_camera_status()
            status_text = "Cameras:\n\n"
            for name, status in camera_status.items():
                icon = "ONLINE" if status["connected"] else "OFFLINE"
                mode = status.get("connection_mode", "rtsp")
                status_text += f"{name}: {icon} ({mode})\n"
            await update.message.reply_text(status_text)
        except Exception as e:
            logger.error(f"Error in /cameras: {e}")
            await update.message.reply_text("Error getting cameras.")

    async def cmd_snapshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                cameras = list(self.camera_manager.cameras.keys())
                await update.message.reply_text(f"Cameras: {', '.join(cameras)}\n\nUsage: /snapshot <camera>")
                return
            camera_name = " ".join(context.args)
            snapshot_path = self.camera_manager.get_snapshot(camera_name)
            if snapshot_path:
                with open(snapshot_path, "rb") as photo:
                    await update.message.reply_photo(photo=photo, caption=f"Snapshot: {camera_name}")
            else:
                await update.message.reply_text(f"Could not get snapshot: {camera_name}")
        except Exception as e:
            logger.error(f"Error in /snapshot: {e}")
            await update.message.reply_text("Error getting snapshot.")

    async def cmd_clip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("Usage: /clip <camera>")
                return
            camera_name = " ".join(context.args)
            events = self.storage.get_events(camera_name=camera_name, limit=1)
            if not events:
                await update.message.reply_text(f"No events for {camera_name}.")
                return
            event = events[0]
            clip_path = event.get("clip_path")
            snapshot_path = event.get("snapshot_path")
            if clip_path and os.path.exists(clip_path):
                with open(clip_path, "rb") as video:
                    await update.message.reply_video(video=video, caption=f"Clip: {camera_name}")
            elif snapshot_path and os.path.exists(snapshot_path):
                with open(snapshot_path, "rb") as photo:
                    await update.message.reply_photo(photo=photo, caption=f"Latest: {camera_name}")
            else:
                await update.message.reply_text(f"No footage for {camera_name}.")
        except Exception as e:
            logger.error(f"Error in /clip: {e}")
            await update.message.reply_text("Error getting clip.")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            hours = 2
            if context.args:
                try:
                    hours = int(context.args[0])
                except ValueError:
                    pass
            events = self.storage.get_recent_events(hours=hours, limit=20)
            if not events:
                await update.message.reply_text(f"No events in last {hours}h.")
                return
            history_text = f"History ({hours}h):\n\n"
            for event in events:
                timestamp = event.get("timestamp", "")
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%I:%M %p")
                except:
                    time_str = timestamp
                history_text += f"[{time_str}] {event.get('camera_name')} - {event.get('event_type')}\n"
            await update.message.reply_text(history_text)
        except Exception as e:
            logger.error(f"Error in /history: {e}")
            await update.message.reply_text("Error getting history.")

    async def cmd_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            events = self.storage.get_recent_events(hours=24, limit=100)
            camera_status = self.camera_manager.get_camera_status()
            online = sum(1 for s in camera_status.values() if s["connected"])
            summary = f"Daily Summary\n\n"
            summary += f"Mode: {self.security_mode.upper()}\n"
            summary += f"Cameras: {online}/{len(camera_status)} online\n"
            summary += f"Events: {len(events)} in 24h\n"
            if events:
                types = {}
                for e in events:
                    t = e.get("event_type", "unknown")
                    types[t] = types.get(t, 0) + 1
                summary += "\nEvent Types:\n"
                for t, c in sorted(types.items(), key=lambda x: -x[1]):
                    summary += f"  {t}: {c}\n"
            await update.message.reply_text(summary)
        except Exception as e:
            logger.error(f"Error in /summary: {e}")
            await update.message.reply_text("Error getting summary.")

    async def cmd_zones(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            zones = self.zone_manager.zones
            if not zones:
                await update.message.reply_text("No zones configured.")
                return
            zones_text = "Zones:\n\n"
            for zone_name, zone_data in zones.items():
                camera = zone_data.get("camera", "N/A")
                areas = zone_data.get("areas", [])
                zones_text += f"{zone_name} ({camera}):\n"
                for area in areas:
                    zones_text += f"  - {area.get('name', 'N/A')} ({area.get('type', 'N/A')})\n"
                zones_text += "\n"
            await update.message.reply_text(zones_text)
        except Exception as e:
            logger.error(f"Error in /zones: {e}")
            await update.message.reply_text("Error getting zones.")

    async def cmd_addzone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 2:
                await update.message.reply_text(
                    "Usage: /addzone <zone_name> <camera_name>\n"
                    "Example: /addzone front_entry Front Gate"
                )
                return
            zone_name = context.args[0].replace(" ", "_").lower()
            camera_name = " ".join(context.args[1:])
            cameras = list(self.camera_manager.cameras.keys())
            matched_camera = None
            for cam in cameras:
                if cam.lower() == camera_name.lower():
                    matched_camera = cam
                    break
            if not matched_camera:
                await update.message.reply_text(
                    f"Camera not found: {camera_name}\n\n"
                    f"Available cameras:\n{', '.join(cameras)}"
                )
                return
            if zone_name in self.zone_manager.zones:
                await update.message.reply_text(f"Zone '{zone_name}' already exists. Use /editzone to modify.")
                return
            areas = [{
                "name": f"{zone_name}_area",
                "type": "restricted",
                "alert_on_entry": True,
                "alert_hours": "24h",
                "description": f"Zone for {matched_camera}",
            }]
            self.zone_manager.add_zone(zone_name, matched_camera, areas)
            security_log.log_config_change(f"Zone added: {zone_name} on {matched_camera}", user="telegram")
            await update.message.reply_text(
                f"Zone added!\n\n"
                f"Name: {zone_name}\n"
                f"Camera: {matched_camera}\n"
                f"Type: restricted\n"
                f"Alert: 24h\n\n"
                f"Restart to apply."
            )
        except Exception as e:
            logger.error(f"Error in /addzone: {e}")
            await update.message.reply_text("Error adding zone.")

    async def cmd_editzone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 2:
                zones = list(self.zone_manager.zones.keys())
                await update.message.reply_text(
                    "Usage: /editzone <zone_name> <setting> <value>\n\n"
                    f"Zones: {', '.join(zones) if zones else 'None'}\n\n"
                    "Settings:\n"
                    "  type <restricted|monitoring>\n"
                    "  alert <on|off>\n"
                    "  hours <24h|night|day>\n"
                    "  camera <camera_name>\n\n"
                    "Example:\n"
                    "  /editzone front_gate type monitoring\n"
                    "  /editzone front_gate alert off"
                )
                return
            zone_name = context.args[0].replace(" ", "_").lower()
            if zone_name not in self.zone_manager.zones:
                await update.message.reply_text(f"Zone not found: {zone_name}")
                return
            setting = context.args[1].lower()
            value = " ".join(context.args[2:]) if len(context.args) > 2 else ""
            zone = self.zone_manager.zones[zone_name]
            areas = zone.get("areas", [])
            if not areas:
                await update.message.reply_text("Zone has no areas configured.")
                return
            area = areas[0]
            if setting == "type":
                if value not in ["restricted", "monitoring"]:
                    await update.message.reply_text("Type must be: restricted or monitoring")
                    return
                area["type"] = value
            elif setting == "alert":
                if value not in ["on", "off"]:
                    await update.message.reply_text("Alert must be: on or off")
                    return
                area["alert_on_entry"] = value == "on"
            elif setting == "hours":
                if value not in ["24h", "night", "day"]:
                    await update.message.reply_text("Hours must be: 24h, night, or day")
                    return
                area["alert_hours"] = value
            elif setting == "camera":
                cameras = list(self.camera_manager.cameras.keys())
                matched = None
                for cam in cameras:
                    if cam.lower() == value.lower():
                        matched = cam
                        break
                if not matched:
                    await update.message.reply_text(f"Camera not found: {value}\nAvailable: {', '.join(cameras)}")
                    return
                zone["camera"] = matched
            else:
                await update.message.reply_text("Unknown setting. Use: type, alert, hours, camera")
                return
            self.zone_manager.update_zone(zone_name, areas)
            security_log.log_config_change(f"Zone edited: {zone_name} - {setting}={value}", user="telegram")
            await update.message.reply_text(f"Zone updated!\n\n{zone_name}: {setting} = {value}")
        except Exception as e:
            logger.error(f"Error in /editzone: {e}")
            await update.message.reply_text("Error editing zone.")

    async def cmd_delzone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                zones = list(self.zone_manager.zones.keys())
                await update.message.reply_text(
                    f"Usage: /delzone <zone_name>\n\n"
                    f"Zones: {', '.join(zones) if zones else 'None'}"
                )
                return
            zone_name = context.args[0].replace(" ", "_").lower()
            if zone_name not in self.zone_manager.zones:
                await update.message.reply_text(f"Zone not found: {zone_name}")
                return
            self.zone_manager.remove_zone(zone_name)
            security_log.log_config_change(f"Zone deleted: {zone_name}", user="telegram")
            await update.message.reply_text(f"Zone deleted: {zone_name}\n\nRestart to apply.")
        except Exception as e:
            logger.error(f"Error in /delzone: {e}")
            await update.message.reply_text("Error deleting zone.")

    async def cmd_mute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("Usage: /mute <minutes>")
                return
            minutes = int(context.args[0])
            if minutes < 1 or minutes > 1440:
                await update.message.reply_text("Mute: 1-1440 minutes.")
                return
            await update.message.reply_text(f"Alerts muted for {minutes} minutes.")
            logger.info(f"Alerts muted for {minutes} minutes")
        except ValueError:
            await update.message.reply_text("Invalid number. Usage: /mute <minutes>")
        except Exception as e:
            logger.error(f"Error in /mute: {e}")

    async def cmd_addcam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 2:
                await update.message.reply_text("Usage: /addcam <name> <ip> [mode]\nExample: /addcam Front 192.168.1.10 rtsp")
                return
            name = context.args[0]
            ip = context.args[1]
            mode = context.args[2] if len(context.args) > 2 else "rtsp"
            if mode not in ["rtsp", "http", "mjpeg", "onvif", "wifi", "lan", "usb"]:
                await update.message.reply_text("Invalid mode. Use: rtsp, http, mjpeg, onvif, wifi, lan, usb")
                return
            new_cam = {"name": name, "ip": ip, "connection_mode": mode, "enabled": True}
            with open("config/cameras.yaml", "r") as f:
                cfg = yaml.safe_load(f) or {}
            cameras = cfg.get("cameras", [])
            cameras.append(new_cam)
            cfg["cameras"] = cameras
            with open("config/cameras.yaml", "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)
            security_log.log_config_change(f"Camera added: {name}", user="telegram")
            await update.message.reply_text(f"Camera added: {name}\nIP: {ip}\nMode: {mode}\n\nRestart to connect.")
        except Exception as e:
            logger.error(f"Error in /addcam: {e}")
            await update.message.reply_text("Error adding camera.")

    async def cmd_delcam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("Usage: /delcam <camera_name>")
                return
            name = " ".join(context.args)
            with open("config/cameras.yaml", "r") as f:
                cfg = yaml.safe_load(f) or {}
            cameras = cfg.get("cameras", [])
            found = False
            for i, cam in enumerate(cameras):
                if cam.get("name", "").lower() == name.lower():
                    cameras.pop(i)
                    found = True
                    break
            if not found:
                await update.message.reply_text(f"Camera not found: {name}")
                return
            cfg["cameras"] = cameras
            with open("config/cameras.yaml", "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)
            security_log.log_config_change(f"Camera deleted: {name}", user="telegram")
            await update.message.reply_text(f"Camera deleted: {name}\n\nRestart to apply.")
        except Exception as e:
            logger.error(f"Error in /delcam: {e}")
            await update.message.reply_text("Error deleting camera.")

    async def cmd_disk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            import psutil
            usage = psutil.disk_usage(os.getcwd())
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            used_gb = usage.used / (1024**3)
            disk_text = f"Disk Space:\n\n"
            disk_text += f"Used: {used_gb:.1f} GB ({usage.percent}%)\n"
            disk_text += f"Free: {free_gb:.1f} GB\n"
            disk_text += f"Total: {total_gb:.1f} GB\n"
            if free_gb < 5:
                disk_text += "\nWARNING: Low disk space!"
            await update.message.reply_text(disk_text)
        except Exception as e:
            logger.error(f"Error in /disk: {e}")
            await update.message.reply_text("Error getting disk info.")

    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await update.message.reply_text("Restarting JARVIS... Please wait.")
            logger.info("Restart requested via Telegram")
            import subprocess
            import sys
            subprocess.Popen([sys.executable, "main.py"], cwd=os.getcwd())
            import time
            time.sleep(2)
            os._exit(0)
        except Exception as e:
            logger.error(f"Error in /restart: {e}")
            await update.message.reply_text("Error restarting.")

    async def cmd_recpath(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                current = self.config.get("recording", {}).get("base_path", "data/recordings")
                await update.message.reply_text(f"Current path: {current}\n\nUsage: /recpath <new_path>\nExample: /recpath D:\\Recordings")
                return
            new_path = " ".join(context.args)
            self.config["recording"]["base_path"] = new_path
            self._save_config()
            security_log.log_config_change(f"Recording path: {new_path}", user="telegram")
            await update.message.reply_text(f"Recording path set to:\n{new_path}\n\nRestart to apply.")
        except Exception as e:
            logger.error(f"Error in /recpath: {e}")
            await update.message.reply_text("Error setting path.")

    async def cmd_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 2:
                await update.message.reply_text("Usage: /setting <key> <value>\n\nKeys:\n- detection.confidence (0.1-1.0)\n- detection.frame_interval (5-120)\n- recording.max_clip_duration (5-300)\n- recording.retention_days (1-365)\n- security.night_hours.start (HH:MM)\n- security.night_hours.end (HH:MM)")
                return
            key = context.args[0]
            value = " ".join(context.args[1:])
            keys = key.split(".")
            cfg = self.config
            for k in keys[:-1]:
                cfg = cfg.setdefault(k, {})
            try:
                value = float(value)
                if value == int(value):
                    value = int(value)
            except ValueError:
                pass
            cfg[keys[-1]] = value
            self._save_config()
            security_log.log_config_change(f"Setting: {key} = {value}", user="telegram")
            await update.message.reply_text(f"Setting updated:\n{key} = {value}")
        except Exception as e:
            logger.error(f"Error in /setting: {e}")
            await update.message.reply_text("Error updating setting.")

    # ==================== NATURAL LANGUAGE HANDLER ====================

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_message = update.message.text
            if self.web_dashboard:
                self.web_dashboard.add_telegram_message("user", user_message)

            intent, params = self.intent_parser.parse(
                user_message,
                self.llm_engine,
                camera_names=self.camera_manager.cameras.keys(),
            )
            self._last_response_snapshot = None
            response = await self._execute_intent(intent, params, user_message)

            if self.web_dashboard:
                self.web_dashboard.add_telegram_message("bot", response)

            await self._send_user_response(update, response)
        except TimedOut as e:
            logger.warning(f"Telegram reply timed out; response may already be delivered: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text("Sorry, I encountered an error.")

    async def _send_user_response(self, update, response):
        try:
            if self._last_response_snapshot and os.path.exists(self._last_response_snapshot):
                with open(self._last_response_snapshot, "rb") as photo:
                    await update.message.reply_photo(photo=photo, caption=response[:1024])
            else:
                await update.message.reply_text(response)
        except TimedOut:
            raise

    async def _execute_intent(self, intent, params, original_message=""):
        return self._execute_intent_sync(intent, params, original_message)

    def _execute_intent_sync(self, intent, params, original_message=""):
        if intent == "visual":
            return self._answer_visual_question(original_message, params.get("camera", ""))

        if intent == "status":
            camera_status = self.camera_manager.get_camera_status()
            online = sum(1 for s in camera_status.values() if s["connected"])
            return f"Status: {self.security_mode.upper()} mode\nCameras: {online}/{len(camera_status)} online"

        elif intent == "snapshot":
            camera = params.get("camera", "") or self._match_camera_name(original_message)
            if not camera:
                cameras = list(self.camera_manager.cameras.keys())
                return f"Which camera?\n{', '.join(cameras)}"
            snapshot_path = self.camera_manager.get_snapshot(camera)
            if snapshot_path and self.web_dashboard:
                return f"Snapshot saved: {snapshot_path}"
            return f"Could not get snapshot: {camera}"

        elif intent == "mode":
            mode = params.get("mode", "")
            if mode in ["home", "away", "sleep"]:
                old = self.security_mode
                self.security_mode = mode
                self.config["security"]["mode"] = mode
                self._save_config()
                return f"Mode: {old.upper()} → {mode.upper()}"
            return "Usage: mode <home|away|sleep>"

        elif intent == "events":
            hours = params.get("hours", 2)
            events = self.storage.get_recent_events(hours=hours, limit=5)
            if not events:
                return f"No events in {hours}h."
            text = f"Events ({hours}h):\n"
            for e in events:
                text += f"- {e.get('camera_name')}: {e.get('event_type')}\n"
            return text

        elif intent == "cameras":
            camera_status = self.camera_manager.get_camera_status()
            text = "Cameras:\n"
            for name, s in camera_status.items():
                status = "ONLINE" if s["connected"] else "OFFLINE"
                text += f"- {name}: {status}\n"
            return text

        elif intent == "zones":
            zones = self.zone_manager.zones
            if not zones:
                return "No zones configured."
            text = "Zones:\n"
            for name in zones:
                text += f"- {name}\n"
            return text

        elif intent == "addzone":
            zone = params.get("zone", "")
            camera = params.get("camera", "")
            if not zone or not camera:
                return "Need: zone name and camera\nExample: addzone front_entry Front Gate"
            zone_key = zone.replace(" ", "_").lower()
            cameras = list(self.camera_manager.cameras.keys())
            matched = None
            for cam in cameras:
                if cam.lower() == camera.lower():
                    matched = cam
                    break
            if not matched:
                return f"Camera not found: {camera}\nAvailable: {', '.join(cameras)}"
            if zone_key in self.zone_manager.zones:
                return f"Zone '{zone_key}' exists. Use editzone to modify."
            areas = [{"name": f"{zone_key}_area", "type": "restricted", "alert_on_entry": True, "alert_hours": "24h"}]
            self.zone_manager.add_zone(zone_key, matched, areas)
            return f"Zone added: {zone_key} on {matched}\nRestart to apply."

        elif intent == "editzone":
            zone = params.get("zone", "")
            if not zone:
                return "Need: zone name\nExample: editzone front_gate"
            zone_key = zone.replace(" ", "_").lower()
            if zone_key not in self.zone_manager.zones:
                return f"Zone not found: {zone_key}"
            text = f"Zone: {zone_key}\n"
            z = self.zone_manager.zones[zone_key]
            text += f"Camera: {z.get('camera', 'N/A')}\n"
            for a in z.get("areas", []):
                text += f"  Area: {a.get('name')} | Type: {a.get('type')} | Alert: {'on' if a.get('alert_on_entry') else 'off'}\n"
            text += "\nUse /editzone <zone> <setting> <value> to change.\nSettings: type, alert, hours, camera"
            return text

        elif intent == "delzone":
            zone = params.get("zone", "")
            if not zone:
                return "Need: zone name\nExample: delzone front_gate"
            zone_key = zone.replace(" ", "_").lower()
            if zone_key not in self.zone_manager.zones:
                return f"Zone not found: {zone_key}"
            self.zone_manager.remove_zone(zone_key)
            return f"Zone deleted: {zone_key}\nRestart to apply."

        elif intent == "disk":
            import psutil
            usage = psutil.disk_usage(os.getcwd())
            free_gb = usage.free / (1024**3)
            return f"Disk: {usage.percent}% used\nFree: {free_gb:.1f} GB"

        elif intent == "restart":
            return "Restarting... Please wait."

        elif intent == "addcam":
            name = params.get("name", "")
            ip = params.get("ip", "")
            if not name or not ip:
                return "Need: name and IP\nExample: addcam Front 192.168.1.10"
            try:
                new_cam = {"name": name, "ip": ip, "connection_mode": params.get("mode", "rtsp"), "enabled": True}
                with open("config/cameras.yaml", "r") as f:
                    cfg = yaml.safe_load(f) or {}
                cfg.setdefault("cameras", []).append(new_cam)
                with open("config/cameras.yaml", "w") as f:
                    yaml.dump(cfg, f, default_flow_style=False)
                return f"Camera added: {name} ({ip})\nRestart to connect."
            except Exception as e:
                return f"Error: {e}"

        elif intent == "delcam":
            camera = params.get("camera", "") or self._match_camera_name(original_message)
            if not camera:
                return "Which camera to delete?"
            try:
                with open("config/cameras.yaml", "r") as f:
                    cfg = yaml.safe_load(f) or {}
                cameras = cfg.get("cameras", [])
                for i, cam in enumerate(cameras):
                    if cam.get("name", "").lower() == camera.lower():
                        cameras.pop(i)
                        cfg["cameras"] = cameras
                        with open("config/cameras.yaml", "w") as f:
                            yaml.dump(cfg, f, default_flow_style=False)
                        return f"Camera deleted: {camera}\nRestart to apply."
                return f"Camera not found: {camera}"
            except Exception as e:
                return f"Error: {e}"

        elif intent == "recpath":
            path = params.get("path", "")
            if not path:
                current = self.config.get("recording", {}).get("base_path", "data/recordings")
                return f"Current: {current}\nExample: recpath D:\\Recordings"
            self.config["recording"]["base_path"] = path
            self._save_config()
            return f"Recording path: {path}\nRestart to apply."

        elif intent == "setting":
            key = params.get("key", "")
            value = params.get("value", "")
            if not key or not value:
                return "Usage: setting <key> <value>\nExample: setting detection.confidence 0.7"
            try:
                keys = key.split(".")
                cfg = self.config
                for k in keys[:-1]:
                    cfg = cfg.setdefault(k, {})
                try:
                    value = float(value)
                    if value == int(value):
                        value = int(value)
                except ValueError:
                    pass
                cfg[keys[-1]] = value
                self._save_config()
                return f"Updated: {key} = {value}"
            except Exception as e:
                return f"Error: {e}"

        elif intent == "mute":
            minutes = params.get("minutes", 30)
            return f"Alerts muted for {minutes} minutes."

        elif intent == "help":
            return (
                "Commands:\n"
                "/status, /cameras, /snapshot, /mode\n"
                "/events, /zones, /disk, /restart\n"
                "/addcam, /delcam, /recpath, /setting\n"
                "/addzone, /editzone, /delzone\n\n"
                "Or just tell me what to do!"
            )

        elif intent == "chat":
            if self.llm_engine:
                try:
                    events = self.storage.get_recent_events(hours=2, limit=5) if self.storage else []
                    camera_status = self.camera_manager.get_camera_status() if self.camera_manager else {}
                    return self.llm_engine.answer_question(original_message, events, camera_status)
                except Exception as e:
                    logger.error(f"LLM error: {e}")
            return "AI not configured. Use /help for commands."

        return "I didn't understand. Try /help for commands."

    def _match_camera_name(self, message):
        message_lower = (message or "").lower()
        for camera_name in self.camera_manager.cameras:
            if camera_name.lower() in message_lower:
                return camera_name
        return ""

    def _default_camera_name(self):
        if not self.camera_manager.cameras:
            return ""

        try:
            status = self.camera_manager.get_camera_status()
            for name, details in status.items():
                if details.get("connected"):
                    return name
        except Exception:
            pass

        return next(iter(self.camera_manager.cameras.keys()), "")

    def _build_llm_context(self):
        context_parts = [f"Security mode: {self.security_mode.upper()}"]
        try:
            camera_status = self.camera_manager.get_camera_status()
            context_parts.append("Camera status:")
            for name, status in camera_status.items():
                state = "Online" if status.get("connected") else "Offline"
                context_parts.append(f"- {name}: {state}")
        except Exception as e:
            logger.error(f"Could not build camera context: {e}")

        try:
            if self.storage:
                events = self.storage.get_recent_events(hours=2, limit=5)
                if events:
                    context_parts.append("Recent events:")
                    for event in events:
                        context_parts.append(
                            f"- {event.get('timestamp')} | {event.get('camera_name')} | "
                            f"{event.get('event_type')} | {event.get('description')}"
                        )
        except Exception as e:
            logger.error(f"Could not build event context: {e}")

        return "\n".join(context_parts)

    def _answer_visual_question(self, original_message, camera_name=""):
        camera = camera_name or self._match_camera_name(original_message) or self._default_camera_name()
        if not camera:
            return "No camera is configured yet."

        snapshot_path = self.camera_manager.get_snapshot(camera)
        if not snapshot_path:
            return f"I could not capture a live snapshot from {camera}. The camera may be offline or busy."
        self._last_response_snapshot = snapshot_path

        if not self.llm_engine:
            return f"I captured a snapshot from {camera}, but AI vision is not configured."

        context = self._build_llm_context()
        answer = self.llm_engine.answer_image_question(original_message, snapshot_path, context=context)
        return f"{camera}: {answer}"

    # ==================== ALERTS ====================

    async def send_alert(self, event_data):
        if not self._telegram_configured():
            return
        bot = Bot(token=self.bot_token)
        severity = event_data.get("severity", "medium")
        severity_text = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}.get(severity, "")
        alert_text = (
            f"JARVIS Alert\n\n"
            f"{severity_text} {event_data.get('event_type', 'Event').replace('_', ' ').title()}\n\n"
            f"Camera: {event_data.get('camera_name', 'N/A')}\n"
            f"Time: {event_data.get('timestamp', 'N/A')}\n"
            f"Details: {event_data.get('description', 'N/A')}\n"
        )
        if event_data.get("zone"):
            alert_text += f"Zone: {event_data['zone']}\n"
        if self.web_dashboard:
            self.web_dashboard.add_telegram_message("alert", alert_text)
        try:
            snapshot_path = event_data.get("snapshot_path")
            if snapshot_path and os.path.exists(snapshot_path):
                with open(snapshot_path, "rb") as photo:
                    await bot.send_photo(chat_id=self.chat_id, photo=photo, caption=alert_text)
            else:
                await bot.send_message(chat_id=self.chat_id, text=alert_text)
            security_log.log_alert_sent(event_data.get("event_type"), event_data.get("camera_name"))
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    def _save_config(self):
        try:
            with open("config/settings.yaml", "w") as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def run(self):
        if not self._telegram_configured():
            logger.warning("Bot token not configured. Skipping Telegram bot.")
            return None
        self.app = self.build_app()
        logger.info("Telegram bot initialized with full system control")
        return self.app
