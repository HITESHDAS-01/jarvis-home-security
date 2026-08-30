import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


class JarvisLogger:
    _instance = None
    _loggers = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self._setup_root_logger()

    def _setup_root_logger(self):
        root = logging.getLogger("jarvis")
        root.setLevel(logging.DEBUG)

        if root.handlers:
            return

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_format)

        file_handler = RotatingFileHandler(
            self.log_dir / "jarvis.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=7,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)

        error_handler = RotatingFileHandler(
            self.log_dir / "errors.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=30,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_format)

        root.addHandler(console_handler)
        root.addHandler(file_handler)
        root.addHandler(error_handler)

    def get_logger(self, name):
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(f"jarvis.{name}")
        return self._loggers[name]


def get_logger(name):
    return JarvisLogger().get_logger(name)


class SecurityLogger:
    def __init__(self):
        self.logger = get_logger("security")
        self.security_log = self._setup_security_log()

    def _setup_security_log(self):
        handler = RotatingFileHandler(
            Path("logs") / "security.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=30,
            encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))

        sec_logger = logging.getLogger("jarvis.security.events")
        sec_logger.setLevel(logging.INFO)
        sec_logger.addHandler(handler)
        return sec_logger

    def log_event(self, event_type, camera, severity, description, zone=None):
        msg = f"[{event_type}] Camera: {camera} | Severity: {severity} | {description}"
        if zone:
            msg += f" | Zone: {zone}"

        if severity == "high":
            self.security_log.error(msg)
        elif severity == "medium":
            self.security_log.warning(msg)
        else:
            self.security_log.info(msg)

    def log_alert_sent(self, event_type, camera, channel="telegram"):
        self.security_log.info(f"Alert sent via {channel}: {event_type} at {camera}")

    def log_camera_offline(self, camera):
        self.security_log.warning(f"Camera offline: {camera}")

    def log_camera_online(self, camera):
        self.security_log.info(f"Camera online: {camera}")

    def log_mode_change(self, old_mode, new_mode, user="system"):
        self.security_log.info(f"Mode changed: {old_mode} -> {new_mode} (by {user})")

    def log_config_change(self, change, user="system"):
        self.security_log.info(f"Config changed: {change} (by {user})")

    def log_intrusion(self, camera, zone, time_of_day):
        self.security_log.error(f"INTRUSION: {camera} | Zone: {zone} | Time: {time_of_day}")
