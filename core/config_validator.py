import yaml
import re
from pathlib import Path
from core.logger import get_logger

logger = get_logger("config_validator")


class ConfigValidator:
    VALID_CONNECTION_MODES = ["rtsp", "http", "mjpeg", "onvif", "wifi", "lan", "usb", "file"]
    VALID_SEVERITY = ["low", "medium", "high", "critical"]
    VALID_SECURITY_MODES = ["home", "away", "sleep"]
    VALID_RECORDING_MODES = ["continuous", "motion_only", "hybrid"]
    VALID_QUALITY = ["low", "medium", "high"]

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_all(self, settings_path="config/settings.yaml",
                     cameras_path="config/cameras.yaml",
                     zones_path="config/zones.yaml"):
        self.errors = []
        self.warnings = []

        self._validate_settings(settings_path)
        self._validate_cameras(cameras_path)
        self._validate_zones(zones_path)

        if self.errors:
            for error in self.errors:
                logger.error(f"CONFIG ERROR: {error}")

        if self.warnings:
            for warning in self.warnings:
                logger.warning(f"CONFIG WARNING: {warning}")

        return len(self.errors) == 0

    def _validate_settings(self, path):
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            self.errors.append(f"Settings file not found: {path}")
            return
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in settings: {e}")
            return

        if not config:
            self.errors.append("Settings file is empty")
            return

        security = config.get("security", {})
        mode = security.get("mode", "home")
        if mode not in self.VALID_SECURITY_MODES:
            self.errors.append(f"Invalid security mode: {mode}. Must be one of: {self.VALID_SECURITY_MODES}")

        detection = config.get("detection", {})
        confidence = detection.get("confidence_threshold", 0.5)
        if not 0 <= confidence <= 1:
            self.errors.append(f"Invalid confidence threshold: {confidence}. Must be 0-1")

        telegram = config.get("telegram", {})
        token = telegram.get("bot_token", "")
        if token and token != "YOUR_BOT_TOKEN_HERE":
            if not re.match(r"^\d+:[A-Za-z0-9_-]+$", token):
                self.warnings.append("Telegram bot token format looks invalid")

        llm = config.get("llm", {})
        provider = llm.get("provider", "gemini")
        if provider not in ["gemini", "openai", "ollama"]:
            self.errors.append(f"Invalid LLM provider: {provider}")

        if provider == "gemini":
            api_key = llm.get("gemini", {}).get("api_key", "")
            if not api_key or api_key == "YOUR_GEMINI_API_KEY":
                self.warnings.append("Gemini API key not configured")
        elif provider == "openai":
            api_key = llm.get("openai", {}).get("api_key", "")
            if not api_key or api_key == "YOUR_OPENAI_API_KEY":
                self.warnings.append("OpenAI API key not configured")

        db = config.get("database", {})
        db_path = db.get("path", "data/events.db")
        db_dir = Path(db_path).parent
        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            except Exception as e:
                self.errors.append(f"Cannot create database directory: {e}")

    def _validate_cameras(self, path):
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            self.errors.append(f"Cameras file not found: {path}")
            return
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in cameras: {e}")
            return

        cameras = config.get("cameras", [])
        if not cameras:
            self.warnings.append("No cameras configured")
            return

        names_seen = set()
        for i, cam in enumerate(cameras):
            name = cam.get("name", f"Camera_{i}")

            if not name:
                self.errors.append(f"Camera {i}: missing name")
                continue

            if name in names_seen:
                self.errors.append(f"Duplicate camera name: {name}")
            names_seen.add(name)

            mode = cam.get("connection_mode", "rtsp")
            if mode not in self.VALID_CONNECTION_MODES:
                self.errors.append(f"Camera '{name}': invalid connection_mode: {mode}")
                continue

            if mode in ["rtsp", "http", "mjpeg", "onvif", "wifi", "lan"]:
                ip = cam.get("ip", "")
                rtsp_url = cam.get("rtsp_url", "")
                http_url = cam.get("http_url", "")
                mjpeg_url = cam.get("mjpeg_url", "")
                onvif_url = cam.get("onvif_url", "")
                wifi_url = cam.get("wifi_url", "")
                lan_url = cam.get("lan_url", "")

                has_direct_url = any([rtsp_url, http_url, mjpeg_url, onvif_url, wifi_url, lan_url])
                has_ip = bool(ip)

                if not has_direct_url and not has_ip:
                    self.errors.append(f"Camera '{name}': needs either ip or direct URL")

                if ip and not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                    self.warnings.append(f"Camera '{name}': IP format looks invalid: {ip}")

            elif mode == "usb":
                device_id = cam.get("device_id", 0)
                if not isinstance(device_id, int) or device_id < 0:
                    self.errors.append(f"Camera '{name}': invalid device_id: {device_id}")

            elif mode == "file":
                file_path = cam.get("file_path", "")
                if not file_path:
                    self.errors.append(f"Camera '{name}': missing file_path")
                elif not Path(file_path).exists():
                    self.warnings.append(f"Camera '{name}': file not found: {file_path}")

            recording = cam.get("recording", {})
            rec_mode = recording.get("mode", "hybrid")
            if rec_mode not in self.VALID_RECORDING_MODES:
                self.errors.append(f"Camera '{name}': invalid recording mode: {rec_mode}")

            quality = recording.get("quality", "low")
            if quality not in self.VALID_QUALITY:
                self.errors.append(f"Camera '{name}': invalid quality: {quality}")

    def _validate_zones(self, path):
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            self.warnings.append(f"Zones file not found: {path}")
            return
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in zones: {e}")
            return

        zones = config.get("zones", {})
        rules = config.get("security_rules", [])

        for zone_name, zone_data in zones.items():
            camera = zone_data.get("camera", "")
            areas = zone_data.get("areas", [])

            for area in areas:
                coords = area.get("coordinates", [])
                if len(coords) < 3:
                    self.warnings.append(f"Zone '{zone_name}': area '{area.get('name')}' needs at least 3 points")

        for rule in rules:
            trigger = rule.get("trigger", "")
            if not trigger:
                self.errors.append("Security rule missing trigger")

            severity = rule.get("severity", "medium")
            if severity not in self.VALID_SEVERITY:
                self.errors.append(f"Rule '{rule.get('name')}': invalid severity: {severity}")

    def get_report(self):
        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


def validate_startup():
    validator = ConfigValidator()
    is_valid = validator.validate_all()

    report = validator.get_report()

    if report["error_count"] > 0:
        logger.error(f"Configuration validation FAILED with {report['error_count']} errors")
        for error in report["errors"]:
            logger.error(f"  - {error}")
    else:
        logger.info("Configuration validation passed")

    if report["warning_count"] > 0:
        logger.warning(f"Configuration has {report['warning_count']} warnings")
        for warning in report["warnings"]:
            logger.warning(f"  - {warning}")

    return is_valid
