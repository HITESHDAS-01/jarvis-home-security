import cv2
import time
import json
import re
import base64
import hmac
import hashlib
import secrets
import threading
import os
import subprocess
import sys
import psutil
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, jsonify, request, Response, session, redirect, url_for, send_file
from flask_socketio import SocketIO
from core.logger import get_logger

logger = get_logger("web")

import yaml

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(get_remote_address, default_limits=["200 per minute"])
except ImportError:
    limiter = None


class SecurityManager:
    def __init__(self):
        self.login_attempts = {}
        self.audit_log = []
        self.block_duration = 300
        self.max_attempts = 5

    def check_brute_force(self, ip):
        if ip in self.login_attempts:
            attempts, last_attempt = self.login_attempts[ip]
            if attempts >= self.max_attempts:
                if (datetime.now() - last_attempt).seconds < self.block_duration:
                    return True
                else:
                    self.login_attempts.pop(ip)
        return False

    def record_login_attempt(self, ip, success):
        if success:
            self.login_attempts.pop(ip, None)
        else:
            attempts, _ = self.login_attempts.get(ip, (0, datetime.now()))
            self.login_attempts[ip] = (attempts + 1, datetime.now())

    def audit(self, action, user="admin", ip=""):
        entry = {"timestamp": datetime.now().isoformat(), "action": action, "user": user, "ip": ip}
        self.audit_log.append(entry)
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-500:]
        logger.info(f"AUDIT: {action} by {user} from {ip}")


class WebDashboard:
    def __init__(self, camera_manager, event_engine, storage, zone_manager, config):
        self.app = Flask(__name__, template_folder="templates", static_folder="static")
        self.app.config["SECRET_KEY"] = secrets.token_hex(32)
        self.app.config["SESSION_COOKIE_HTTPONLY"] = True
        self.app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        self.app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)

        self.socketio = SocketIO(self.app, cors_allowed_origins=["http://localhost:8080", "http://127.0.0.1:8080"], async_mode="threading")

        if limiter:
            limiter.init_app(self.app)
            self.limiter = limiter
        else:
            self.limiter = None

        self.camera_manager = camera_manager
        self.event_engine = event_engine
        self.storage = storage
        self.zone_manager = zone_manager
        self.config = config
        self.llm_engine = None
        self.security = SecurityManager()
        self._load_password()
        self.log_buffer = []
        self.chat_history = []
        self.telegram_history = []
        self.telegram_bot = None
        self._setup_log_handler()

        self._setup_routes()
        self._setup_socketio()
        self._setup_security_headers()

    def _load_password(self):
        self.admin_password_hash = None
        pw_file = Path("config/.admin_password")
        if pw_file.exists():
            self.admin_password_hash = pw_file.read_text().strip()
        else:
            default_pw = "jarvis2024"
            self.admin_password_hash = hashlib.sha256(default_pw.encode()).hexdigest()
            pw_file.write_text(self.admin_password_hash)
            logger.warning("Default password set — CHANGE IT in Settings!")

    def _check_password(self, password):
        return hmac.compare_digest(
            hashlib.sha256(password.encode()).hexdigest(),
            self.admin_password_hash
        )

    def _change_password(self, new_password):
        hashed = hashlib.sha256(new_password.encode()).hexdigest()
        Path("config/.admin_password").write_text(hashed)
        self.admin_password_hash = hashed

    def _setup_log_handler(self):
        import logging
        import queue
        self._log_queue = queue.Queue(maxsize=500)
        class WebLogHandler(logging.Handler):
            def __init__(self, dashboard):
                super().__init__()
                self.dashboard = dashboard
            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.dashboard._log_queue.put_nowait({"time": datetime.now().strftime("%H:%M:%S"), "level": record.levelname, "message": msg, "source": record.name})
                except Exception:
                    pass
        handler = WebLogHandler(self)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        root = logging.getLogger("jarvis")
        root.addHandler(handler)
        def _log_pump():
            import time as _time
            while True:
                try:
                    entry = self._log_queue.get(timeout=1)
                    self.log_buffer.append(entry)
                    if len(self.log_buffer) > 200:
                        self.log_buffer = self.log_buffer[-100:]
                    self.socketio.emit("log_entry", entry)
                except queue.Empty:
                    pass
                except Exception:
                    pass
        import threading
        t = threading.Thread(target=_log_pump, daemon=True)
        t.start()

    def _setup_security_headers(self):
        @self.app.after_request
        def set_headers(response):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; img-src 'self' data:; font-src cdnjs.cloudflare.com"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            return response

    def set_llm_engine(self, llm_engine):
        self.llm_engine = llm_engine

    def _require_auth(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("authenticated"):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Unauthorized", "login_required": True}), 401
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated

    def _setup_routes(self):
        self.app.add_url_rule("/login", "login", self.login, methods=["GET", "POST"])
        self.app.add_url_rule("/logout", "logout", self.logout)
        self.app.add_url_rule("/", "index", self._require_auth(self.index))
        self.app.add_url_rule("/api/status", "api_status", self._require_auth(self.api_status))
        self.app.add_url_rule("/api/cameras", "api_cameras", self._require_auth(self.api_cameras))
        self.app.add_url_rule("/api/cameras/config", "api_cameras_config", self._require_auth(self.api_cameras_config))
        self.app.add_url_rule("/api/cameras/config/save", "api_cameras_config_save", self._require_auth(self.api_cameras_config_save), methods=["POST"])
        self.app.add_url_rule("/api/cameras/config/delete", "api_cameras_config_delete", self._require_auth(self.api_cameras_config_delete), methods=["POST"])
        self.app.add_url_rule("/api/cameras/test", "api_cameras_test", self._require_auth(self.api_cameras_test), methods=["POST"])
        self.app.add_url_rule("/api/events", "api_events", self._require_auth(self.api_events))
        self.app.add_url_rule("/api/camera/<name>/snapshot", "api_snapshot", self._require_auth(self.api_snapshot))
        self.app.add_url_rule("/api/camera/<name>/stream", "api_stream", self._require_auth(self.api_stream))
        self.app.add_url_rule("/api/mode", "api_mode", self._require_auth(self.api_mode), methods=["POST"])
        self.app.add_url_rule("/api/zones", "api_zones", self._require_auth(self.api_zones))
        self.app.add_url_rule("/api/zones/save", "api_zones_save", self._require_auth(self.api_zones_save), methods=["POST"])
        self.app.add_url_rule("/api/zones/update", "api_zones_update", self._require_auth(self.api_zones_update), methods=["POST"])
        self.app.add_url_rule("/api/zones/delete", "api_zones_delete", self._require_auth(self.api_zones_delete), methods=["POST"])
        self.app.add_url_rule("/api/recordings", "api_recordings", self._require_auth(self.api_recordings))
        self.app.add_url_rule("/api/recordings/download", "api_recording_download", self._require_auth(self.api_recording_download))
        self.app.add_url_rule("/api/recording/toggle", "api_recording_toggle", self._require_auth(self.api_recording_toggle), methods=["POST"])
        self.app.add_url_rule("/api/stats", "api_stats", self._require_auth(self.api_stats))
        self.app.add_url_rule("/api/settings", "api_settings_get", self._require_auth(self.api_settings_get))
        self.app.add_url_rule("/api/settings", "api_settings_post", self._require_auth(self.api_settings_post), methods=["POST"])
        self.app.add_url_rule("/api/chat", "api_chat", self._require_auth(self.api_chat), methods=["POST"])
        self.app.add_url_rule("/api/telegram/test", "api_telegram_test", self._require_auth(self.api_telegram_test), methods=["POST"])
        self.app.add_url_rule("/api/llm/test", "api_llm_test", self._require_auth(self.api_llm_test), methods=["POST"])
        self.app.add_url_rule("/api/password", "api_change_password", self._require_auth(self.api_change_password), methods=["POST"])
        self.app.add_url_rule("/api/audit", "api_audit_log", self._require_auth(self.api_audit_log))
        self.app.add_url_rule("/api/logs", "api_logs", self._require_auth(self.api_logs))
        self.app.add_url_rule("/api/chat/history", "api_chat_history", self._require_auth(self.api_chat_history))
        self.app.add_url_rule("/api/telegram/chat/history", "api_telegram_chat_history", self._require_auth(self.api_telegram_chat_history))
        self.app.add_url_rule("/api/telegram/chat/send", "api_telegram_chat_send", self._require_auth(self.api_telegram_chat_send), methods=["POST"])
        self.app.add_url_rule("/api/restart", "api_restart", self._require_auth(self.api_restart), methods=["POST"])

    def _setup_socketio(self):
        @self.socketio.on("connect")
        def handle_connect():
            logger.info("Client connected to WebSocket")

        @self.socketio.on("disconnect")
        def handle_disconnect():
            logger.info("Client disconnected from WebSocket")

    def login(self):
        if request.method == "POST":
            ip = request.remote_addr
            if self.security.check_brute_force(ip):
                return jsonify({"success": False, "error": "Too many attempts. Try again in 5 minutes."}), 429

            data = request.get_json(silent=True) if request.is_json else request.form
            if not data:
                data = request.form
            password = data.get("password", "")

            if self._check_password(password):
                session.permanent = True
                session["authenticated"] = True
                session["login_time"] = datetime.now().isoformat()
                self.security.record_login_attempt(ip, True)
                self.security.audit("LOGIN_SUCCESS", ip=ip)
                if request.is_json:
                    return jsonify({"success": True})
                return redirect(url_for("index"))
            else:
                self.security.record_login_attempt(ip, False)
                self.security.audit("LOGIN_FAILED", ip=ip)
                if request.is_json:
                    return jsonify({"success": False, "error": "Invalid password"})
                return render_template("login.html", error="Invalid password")

        return render_template("login.html")

    def logout(self):
        self.security.audit("LOGOUT", ip=request.remote_addr)
        session.clear()
        return redirect(url_for("login"))

    def index(self):
        return render_template("index.html")

    def api_status(self):
        cs = self.camera_manager.get_camera_status()
        online = sum(1 for s in cs.values() if s["connected"])
        total = len(cs)

        llm_configured = False
        llm_provider = self.config.get("llm", {}).get("provider", "gemini")
        llm_cfg = self.config.get("llm", {}).get(llm_provider, {})
        api_key = llm_cfg.get("api_key", "")
        if api_key and api_key not in ["", "YOUR_GEMINI_API_KEY", "YOUR_OPENAI_API_KEY"]:
            llm_configured = True

        tg_token = self.config.get("telegram", {}).get("bot_token", "")
        tg_configured = bool(tg_token and tg_token not in ["", "YOUR_BOT_TOKEN_HERE"])

        jarvis_status = "online"
        jarvis_message = "All systems operational"
        if not llm_configured:
            jarvis_status = "degraded"
            jarvis_message = "AI not configured"
        if not tg_configured:
            if jarvis_status == "degraded":
                jarvis_status = "limited"
                jarvis_message = "AI & Telegram not configured"
            else:
                jarvis_status = "degraded"
                jarvis_message = "Telegram not configured"

        return jsonify({
            "system": "JARVIS HOME",
            "status": "running",
            "security_mode": self.config.get("security", {}).get("mode", "home"),
            "cameras": {"online": online, "total": total},
            "jarvis": {"status": jarvis_status, "message": jarvis_message, "llm_configured": llm_configured, "telegram_configured": tg_configured},
            "timestamp": datetime.now().isoformat(),
        })

    def api_cameras(self):
        cs = self.camera_manager.get_camera_status()
        return jsonify({"cameras": [{"name": n, "connected": s["connected"], "status": s.get("status", "unknown"), "mode": s.get("connection_mode", "rtsp"), "ip": s.get("ip", "N/A")} for n, s in cs.items()]})

    def api_cameras_config(self):
        try:
            with open("config/cameras.yaml", "r") as f:
                cfg = yaml.safe_load(f) or {}
            return jsonify({"cameras": cfg.get("cameras", [])})
        except Exception as e:
            return jsonify({"cameras": [], "error": str(e)})

    def api_cameras_config_save(self):
        data = request.get_json()
        cam = data.get("camera")
        idx = data.get("index", -1)
        if not cam:
            return jsonify({"success": False, "error": "No camera data"})
        if not cam.get("name", "").strip():
            return jsonify({"success": False, "error": "Camera name required"})
        cam["name"] = re.sub(r'[<>"\']', '', cam["name"].strip())
        if cam.get("ip"):
            cam["ip"] = re.sub(r'[\s<>"\']', '', str(cam["ip"]).strip())
        if cam.get("port"):
            cam["port"] = re.sub(r'\D', '', str(cam["port"]))
        try:
            with open("config/cameras.yaml", "r") as f:
                cfg = yaml.safe_load(f) or {}
            cameras = cfg.get("cameras", [])
            if idx >= 0 and idx < len(cameras):
                cameras[idx] = cam
            else:
                cameras.append(cam)
            cfg["cameras"] = cameras
            with open("config/cameras.yaml", "w") as f:
                yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
            connected = False
            connect_message = "Saved. Camera will connect on the next refresh."
            if self.camera_manager:
                self.camera_manager.reload_cameras()
                self.camera_manager._running = True
                connected = self.camera_manager.connect(cam["name"])
                connect_message = "Saved and connected" if connected else "Saved, but camera did not connect"
                self.emit_camera_status(cam["name"], "online" if connected else "offline")
            self.security.audit(f"CAMERA_SAVE: {cam['name']}", ip=request.remote_addr)
            return jsonify({"success": True, "connected": connected, "message": connect_message})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    def api_cameras_config_delete(self):
        data = request.get_json()
        idx = data.get("index", -1)
        try:
            with open("config/cameras.yaml", "r") as f:
                cfg = yaml.safe_load(f) or {}
            cameras = cfg.get("cameras", [])
            if 0 <= idx < len(cameras):
                removed = cameras.pop(idx)
                cfg["cameras"] = cameras
                with open("config/cameras.yaml", "w") as f:
                    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
                if self.camera_manager:
                    self.camera_manager.reload_cameras()
                self.security.audit(f"CAMERA_DELETE: {removed.get('name')}", ip=request.remote_addr)
                return jsonify({"success": True, "removed": removed.get("name")})
            return jsonify({"success": False, "error": "Invalid index"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    def api_cameras_test(self):
        data = request.get_json()
        cam = data.get("camera")
        idx = data.get("index", -1)
        if not cam:
            return jsonify({"success": False, "error": "No camera data"})
        try:
            tester = self.camera_manager
            ok, message, _ = tester.test_camera_config(cam, timeout=8)
            if ok and self.camera_manager:
                camera_name = cam.get("name")
                if camera_name in self.camera_manager.cameras:
                    self.camera_manager.cameras[camera_name]["config"] = cam
                    self.camera_manager.cameras[camera_name]["reconnect_attempts"] = 0
                    self.camera_manager._running = True
                    connected = self.camera_manager.connect(camera_name)
                    self.emit_camera_status(camera_name, "online" if connected else "offline")
                    if connected:
                        return jsonify({"success": True, "connected": True, "message": message})
            if ok and idx >= 0:
                return jsonify({"success": True, "connected": False, "message": f"{message}. Click Save to connect it to the dashboard."})
            if ok:
                return jsonify({"success": True, "message": message})
            return jsonify({"success": False, "error": message})
        except Exception as e:
            logger.error(f"Camera test failed: {e}")
            return jsonify({"success": False, "error": str(e)})

    def api_events(self):
        hours = request.args.get("hours", 2, type=int)
        limit = request.args.get("limit", 20, type=int)
        hours = min(hours, 168)
        limit = min(limit, 100)
        return jsonify({"events": self.storage.get_recent_events(hours=hours, limit=limit)})

    def api_snapshot(self, name):
        name = re.sub(r'[^\w\s-]', '', name)
        path = self.camera_manager.get_snapshot(name)
        if path:
            with open(path, "rb") as f:
                return jsonify({"success": True, "image": base64.b64encode(f.read()).decode()})
        return jsonify({"success": False})

    def api_stream(self, name):
        name = re.sub(r'[^\w\s-]', '', name)
        def gen():
            while True:
                frame = self.camera_manager.get_frame(name)
                if frame is None:
                    time.sleep(0.1)
                    continue
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
                time.sleep(1/15)
        return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

    def api_mode(self):
        data = request.get_json()
        mode = data.get("mode", "")
        if mode in ["home", "away", "sleep"]:
            self.config["security"]["mode"] = mode
            self._save_config()
            self.security.audit(f"MODE_CHANGE: {mode}", ip=request.remote_addr)
            self.socketio.emit("mode_changed", {"mode": mode})
            return jsonify({"success": True, "mode": mode})
        return jsonify({"success": False, "error": "Invalid mode"})

    def _save_config(self):
        try:
            with open("config/settings.yaml", "w") as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def api_zones(self):
        return jsonify({"zones": self.zone_manager.zones, "rules": self.zone_manager.rules})

    def api_zones_save(self):
        data = request.get_json() or {}
        key = re.sub(r'[^\w-]', '_', data.get("key", "").strip().lower())
        camera = data.get("camera", "").strip()
        area_name = data.get("area_name", "detection_area").strip() or "detection_area"
        zone_type = data.get("type", "restricted")
        alert_on_entry = bool(data.get("alert_on_entry", True))

        if not key:
            return jsonify({"success": False, "error": "Zone key is required"}), 400
        if not camera:
            return jsonify({"success": False, "error": "Camera is required"}), 400

        coordinates = data.get("coordinates") or []
        if coordinates and (not isinstance(coordinates, list) or len(coordinates) < 3):
            return jsonify({"success": False, "error": "Zone polygon needs at least 3 points"}), 400

        self.zone_manager.zones[key] = {
            "camera": camera,
            "areas": [{
                "name": re.sub(r'[^\w\s-]', '', area_name),
                "type": zone_type if zone_type in ["restricted", "monitoring"] else "restricted",
                "alert_on_entry": alert_on_entry,
                "alert_hours": data.get("alert_hours", "24h"),
                "coordinates": coordinates,
                "description": data.get("description", "").strip(),
            }],
        }
        self.zone_manager._save_config()
        self.security.audit(f"ZONE_SAVE: {key}", ip=request.remote_addr)
        return jsonify({"success": True, "zone": self.zone_manager.zones[key]})

    def api_zones_update(self):
        data = request.get_json() or {}
        key = re.sub(r'[^\w-]', '_', data.get("key", "").strip().lower())
        if not key or key not in self.zone_manager.zones:
            return jsonify({"success": False, "error": "Zone not found"}), 404
        zone = self.zone_manager.zones[key]
        zone_type = data.get("type", "")
        if zone_type and zone_type in ["restricted", "monitoring"]:
            for area in zone.get("areas", []):
                area["type"] = zone_type
        if "alert_on_entry" in data:
            for area in zone.get("areas", []):
                area["alert_on_entry"] = bool(data["alert_on_entry"])
        if "alert_hours" in data:
            for area in zone.get("areas", []):
                area["alert_hours"] = data["alert_hours"]
        self.zone_manager._save_config()
        self.security.audit(f"ZONE_UPDATE: {key}", ip=request.remote_addr)
        return jsonify({"success": True, "zone": zone})

    def api_zones_delete(self):
        data = request.get_json() or {}
        key = re.sub(r'[^\w-]', '_', data.get("key", "").strip().lower())
        if not key or key not in self.zone_manager.zones:
            return jsonify({"success": False, "error": "Zone not found"}), 404
        del self.zone_manager.zones[key]
        self.zone_manager._save_config()
        self.security.audit(f"ZONE_DELETE: {key}", ip=request.remote_addr)
        return jsonify({"success": True})

    def _recording_base_path(self):
        base = self.config.get("recording", {}).get("base_path") or "data/recordings"
        return Path(base).resolve()

    def api_recordings(self):
        base = self._recording_base_path()
        base.mkdir(parents=True, exist_ok=True)
        files = []
        for path in sorted(base.rglob("*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
            if not path.is_file() or path.suffix.lower() not in [".mp4", ".avi", ".mov", ".mkv"]:
                continue
            try:
                rel = path.relative_to(base).as_posix()
                stat = path.stat()
                files.append({
                    "name": path.name,
                    "path": rel,
                    "camera": path.parts[-2] if len(path.parts) >= 2 else "",
                    "size_mb": round(stat.st_size / (1024 ** 2), 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "url": f"/api/recordings/download?path={rel}",
                })
            except Exception as e:
                logger.warning(f"Skipping recording {path}: {e}")
        return jsonify({"recordings": files[:200], "base_path": str(base)})

    def api_recording_download(self):
        rel = request.args.get("path", "")
        base = self._recording_base_path()
        target = (base / rel).resolve()
        if base not in target.parents and target != base:
            return jsonify({"error": "Invalid path"}), 400
        if not target.exists() or not target.is_file():
            return jsonify({"error": "Recording not found"}), 404
        return send_file(target, as_attachment=False)

    def api_recording_toggle(self):
        data = request.get_json() or {}
        camera_name = data.get("camera")
        enabled = data.get("enabled")
        recorder = getattr(self.event_engine, "recorder", None)
        if recorder is None:
            return jsonify({"success": False, "error": "Recorder is unavailable"}), 503

        names = [camera_name] if camera_name else list(self.camera_manager.cameras.keys())
        changed = []
        for name in names:
            if name not in self.camera_manager.cameras:
                continue
            is_recording = name in recorder.recording_threads
            should_enable = (not is_recording) if enabled is None else bool(enabled)
            if should_enable and not is_recording:
                cam = self.camera_manager.cameras[name]
                quality = cam.get("config", {}).get("recording", {}).get("quality", "low")
                recorder.start_continuous_recording(name, self.camera_manager, quality=quality)
                changed.append({"camera": name, "recording": True})
            elif not should_enable and is_recording:
                recorder.stop_continuous_recording(name)
                changed.append({"camera": name, "recording": False})

        self.security.audit("RECORDING_TOGGLE", ip=request.remote_addr)
        return jsonify({"success": True, "changed": changed})

    def api_stats(self):
        from core.disk_monitor import DiskMonitor
        monitor = DiskMonitor()
        du = monitor.get_disk_usage()
        ss = monitor.get_storage_stats()
        db = self.storage.get_database_stats()
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        return jsonify({"disk": du, "storage": ss, "database": db, "cpu": {"percent": cpu, "cores": psutil.cpu_count()}, "ram": {"percent": ram.percent, "used": f"{ram.used//(1024**3):.1f} GB", "total": f"{ram.total//(1024**3):.1f} GB"}})

    def api_settings_get(self):
        return jsonify({"settings": self.config})

    def api_settings_post(self):
        data = request.get_json()
        if not data:
            return jsonify({"success": False})
        detection = data.get("detection")
        if isinstance(detection, dict) and "target_classes" in detection and "classes_to_detect" not in detection:
            detection["classes_to_detect"] = detection.pop("target_classes")
        def deep_update(base, up):
            for k, v in up.items():
                if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                    deep_update(base[k], v)
                else:
                    base[k] = v
        deep_update(self.config, data)
        self._save_config()
        self._apply_live_settings(data)
        self.security.audit("SETTINGS_UPDATE", ip=request.remote_addr)
        return jsonify({"success": True})

    def _apply_live_settings(self, data):
        if "telegram" in data and self.telegram_bot:
            tg = self.config.get("telegram", {})
            self.telegram_bot.bot_token = tg.get("bot_token", "")
            self.telegram_bot.chat_id = tg.get("chat_id", "")
        if "llm" in data:
            try:
                from llm.chat_engine import LLMEngine
                self.llm_engine = LLMEngine(self.config)
                if self.telegram_bot:
                    self.telegram_bot.llm_engine = self.llm_engine
            except Exception as e:
                logger.error(f"Failed to reload LLM settings: {e}")

    def api_restart(self):
        self.security.audit("SYSTEM_RESTART_REQUESTED", ip=request.remote_addr)

        def restart():
            time.sleep(1)
            subprocess.Popen([sys.executable, "main.py"], cwd=os.getcwd())
            os._exit(0)

        threading.Thread(target=restart, daemon=True).start()
        return jsonify({"success": True, "message": "Restarting JARVIS"})

    def api_chat(self):
        data = request.get_json()
        msg = data.get("message", "")
        if not msg:
            return jsonify({"response": "Please provide a message, sir."})
        if len(msg) > 500:
            msg = msg[:500]
        self.chat_history.append({"role": "user", "message": msg, "time": datetime.now().isoformat()})
        response = None
        configured = False
        if self.llm_engine:
            try:
                response = self.llm_engine.chat(msg)
                configured = True
            except Exception as e:
                logger.error(f"LLM error: {e}")
        if not response:
            response = "AI not configured, sir. Please go to AI Setup and add your API key to enable intelligent responses."
        self.chat_history.append({"role": "jarvis", "message": response, "time": datetime.now().isoformat()})
        if len(self.chat_history) > 100:
            self.chat_history = self.chat_history[-50:]
        return jsonify({"response": response, "configured": configured})

    def api_telegram_test(self):
        data = request.get_json()
        token = data.get("token", "").strip()
        chat_id = data.get("chat_id", "").strip()
        if not token or not chat_id:
            return jsonify({"success": False, "error": "Token and Chat ID required"})
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
            return jsonify({"success": False, "error": "Invalid token format"})
        if not re.match(r'^-?\d+$', chat_id):
            return jsonify({"success": False, "error": "Invalid chat ID format"})
        try:
            import requests as req
            r = req.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "JARVIS Home Security - Test message!"}, timeout=10)
            self.security.audit("TELEGRAM_TEST", ip=request.remote_addr)
            if r.status_code == 200:
                return jsonify({"success": True})
            return jsonify({"success": False, "error": f"HTTP {r.status_code}"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    def api_llm_test(self):
        data = request.get_json()
        provider = data.get("provider", "gemini")
        api_key = data.get("api_key", "")
        model = data.get("model", "")
        if provider not in ["gemini", "openai", "ollama"]:
            return jsonify({"success": False, "error": "Invalid provider"})
        try:
            if provider == "gemini":
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                m = genai.GenerativeModel(model or "gemini-1.5-flash")
                r = m.generate_content("Say 'JARVIS online' in 5 words or less.")
                self.security.audit("LLM_TEST: gemini", ip=request.remote_addr)
                return jsonify({"success": True, "response": r.text[:200]})
            elif provider == "openai":
                from openai import OpenAI
                c = OpenAI(api_key=api_key)
                r = c.chat.completions.create(model=model or "gpt-4o-mini", messages=[{"role":"user","content":"Say 'JARVIS online'"}], max_tokens=20)
                self.security.audit("LLM_TEST: openai", ip=request.remote_addr)
                return jsonify({"success": True, "response": r.choices[0].message.content[:200]})
            elif provider == "ollama":
                import requests as req
                base = data.get("base_url", "http://localhost:11434")
                r = req.post(f"{base}/api/generate", json={"model": model or "llama3.1", "prompt": "Say JARVIS online", "stream": False}, timeout=30)
                self.security.audit("LLM_TEST: ollama", ip=request.remote_addr)
                if r.status_code == 200:
                    return jsonify({"success": True, "response": r.json().get("response", "")[:200]})
                return jsonify({"success": False, "error": f"Ollama error: {r.status_code}"})
            return jsonify({"success": False, "error": "Unknown provider"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    def api_change_password(self):
        data = request.get_json()
        old_pw = data.get("old_password", "")
        new_pw = data.get("new_password", "")
        if not old_pw or not new_pw:
            return jsonify({"success": False, "error": "Both passwords required"})
        if len(new_pw) < 8:
            return jsonify({"success": False, "error": "Password must be at least 8 characters"})
        if not self._check_password(old_pw):
            self.security.audit("PASSWORD_CHANGE_FAILED", ip=request.remote_addr)
            return jsonify({"success": False, "error": "Current password incorrect"})
        self._change_password(new_pw)
        self.security.audit("PASSWORD_CHANGED", ip=request.remote_addr)
        return jsonify({"success": True})

    def api_audit_log(self):
        return jsonify({"logs": self.security.audit_log[-50:]})

    def api_logs(self):
        limit = request.args.get("limit", 100, type=int)
        limit = min(limit, 200)
        return jsonify({"logs": self.log_buffer[-limit:]})

    def api_chat_history(self):
        return jsonify({"messages": self.chat_history[-50:]})

    def api_telegram_chat_history(self):
        return jsonify({"messages": self.telegram_history[-50:]})

    def api_telegram_chat_send(self):
        data = request.get_json()
        msg = data.get("message", "").strip()
        if not msg:
            return jsonify({"success": False, "error": "Empty message"})
        if len(msg) > 500:
            msg = msg[:500]
        self.telegram_history.append({"role": "user", "message": msg, "time": datetime.now().isoformat()})
        if self.telegram_bot and self.telegram_bot.bot_token and self.telegram_bot.chat_id:
            try:
                import asyncio
                from telegram import Bot
                bot = Bot(token=self.telegram_bot.bot_token)
                async def send():
                    await bot.send_message(chat_id=self.telegram_bot.chat_id, text=msg)
                loop = asyncio.new_event_loop()
                loop.run_until_complete(send())
                loop.close()
                self.security.audit(f"TELEGRAM_SENT: {msg[:50]}", ip=request.remote_addr)
                return jsonify({"success": True})
            except Exception as e:
                logger.error(f"Failed to send Telegram message: {e}")
                return jsonify({"success": False, "error": str(e)})
        return jsonify({"success": False, "error": "Telegram bot not configured"})

    def add_telegram_message(self, role, message):
        self.telegram_history.append({"role": role, "message": message, "time": datetime.now().isoformat()})
        if len(self.telegram_history) > 200:
            self.telegram_history = self.telegram_history[-100:]
        self.socketio.emit("telegram_message", {"role": role, "message": message, "time": datetime.now().isoformat()})

    def set_telegram_bot(self, bot):
        self.telegram_bot = bot

    def emit_event(self, event_data):
        self.socketio.emit("new_event", event_data)

    def emit_camera_status(self, camera_name, status):
        self.socketio.emit("camera_status", {"name": camera_name, "status": status})

    def run(self, host="0.0.0.0", port=8080, debug=False):
        logger.info(f"Starting web dashboard on http://{host}:{port}")
        if debug:
            self.socketio.run(self.app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)
        else:
            from waitress import serve
            serve(self.app, host=host, port=port, threads=8)
