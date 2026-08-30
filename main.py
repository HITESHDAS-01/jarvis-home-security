import yaml
import signal
import sys
import time
import asyncio
import threading
from pathlib import Path

from core.camera_manager import CameraManager
from core.detector import Detector
from core.storage import EventStorage
from core.recorder import Recorder
from core.event_engine import EventEngine
from core.zone_manager import ZoneManager
from core.config_validator import validate_startup
from core.logger import get_logger, JarvisLogger
from llm.chat_engine import LLMEngine
from bot.telegram_bot import JarvisBot
from web.app import WebDashboard

logger = get_logger("main")


class JarvisHome:
    def __init__(self):
        self.camera_manager = None
        self.detector = None
        self.storage = None
        self.recorder = None
        self.event_engine = None
        self.zone_manager = None
        self.llm_engine = None
        self.jarvis_bot = None
        self.web_dashboard = None
        self.config = None
        self._shutdown_event = threading.Event()
        self._detection_thread = None
        self._alert_loop = None
        self._alert_thread = None

    def load_config(self):
        try:
            with open("config/settings.yaml", "r") as f:
                self.config = yaml.safe_load(f)
            logger.info("Configuration loaded")
            return True
        except FileNotFoundError:
            logger.error("Settings file not found: config/settings.yaml")
            return False
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in settings: {e}")
            return False

    def initialize_components(self):
        logger.info("Initializing components...")

        try:
            self.camera_manager = CameraManager("config/cameras.yaml")
            logger.info("Camera manager loaded")
        except Exception as e:
            logger.error(f"Failed to load camera manager: {e}")
            return False

        try:
            self.detector = Detector(
                model_name=self.config.get("detection", {}).get("model", "yolov8n.pt"),
                confidence=self.config.get("detection", {}).get("confidence_threshold", 0.5),
                classes=self.config.get("detection", {}).get("classes_to_detect", ["person"]),
            )
            logger.info("Detector loaded")
        except Exception as e:
            logger.error(f"Failed to load detector: {e}")
            return False

        try:
            self.storage = EventStorage(self.config.get("database", {}).get("path", "data/events.db"))
            logger.info("Storage loaded")
        except Exception as e:
            logger.error(f"Failed to load storage: {e}")
            return False

        try:
            self.recorder = Recorder(
                base_path=self.config.get("recording", {}).get("base_path", "data/recordings"),
                max_clip_duration=self.config.get("recording", {}).get("max_clip_duration", 30),
            )
            logger.info("Recorder loaded")
        except Exception as e:
            logger.error(f"Failed to load recorder: {e}")
            return False

        try:
            self.event_engine = EventEngine(self.camera_manager, self.detector, self.storage, self.recorder, self.config)
            logger.info("Event engine loaded")
        except Exception as e:
            logger.error(f"Failed to load event engine: {e}")
            return False

        try:
            self.zone_manager = ZoneManager("config/zones.yaml")
            logger.info("Zone manager loaded")
        except Exception as e:
            logger.error(f"Failed to load zone manager: {e}")
            return False

        try:
            self.llm_engine = LLMEngine(self.config)
            logger.info("LLM engine loaded")
        except Exception as e:
            logger.error(f"Failed to load LLM engine: {e}")
            return False

        try:
            self.jarvis_bot = JarvisBot(
                self.config, self.camera_manager, self.event_engine,
                self.storage, self.llm_engine, self.zone_manager
            )
            logger.info("Telegram bot loaded")
        except Exception as e:
            logger.error(f"Failed to load Telegram bot: {e}")
            return False

        try:
            self.web_dashboard = WebDashboard(
                self.camera_manager, self.event_engine,
                self.storage, self.zone_manager, self.config
            )
            self.web_dashboard.set_llm_engine(self.llm_engine)
            self.web_dashboard.set_telegram_bot(self.jarvis_bot)
            self.jarvis_bot.set_web_dashboard(self.web_dashboard)
            logger.info("Web dashboard loaded")
        except Exception as e:
            logger.error(f"Failed to load web dashboard: {e}")
            return False

        return True

    def start_cameras(self):
        logger.info("Connecting cameras...")
        self.camera_manager.connect_all()
        time.sleep(3)

        status = self.camera_manager.get_camera_status()
        online = sum(1 for s in status.values() if s["connected"])
        total = len(status)
        logger.info(f"Cameras: {online}/{total} online")

        for name, s in status.items():
            state = "ONLINE" if s["connected"] else "OFFLINE"
            logger.info(f"  {name}: {state}")

    def start_event_processing(self):
        logger.info("Starting event engine...")
        self.event_engine.start()

        self.start_alert_loop()

        self.event_engine.register_callback(
            lambda event: asyncio.run_coroutine_threadsafe(
                self.jarvis_bot.send_alert(event), self._alert_loop
            )
        )

        if self.web_dashboard:
            self.event_engine.register_callback(
                lambda event: self.web_dashboard.emit_event(event)
            )

        logger.info("Starting detection loop...")
        self._detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._detection_thread.start()

    def start_alert_loop(self):
        if self._alert_loop and self._alert_loop.is_running():
            return

        self._alert_loop = asyncio.new_event_loop()
        self._alert_thread = threading.Thread(target=self._run_alert_loop, daemon=True)
        self._alert_thread.start()

        self.jarvis_bot.set_main_loop(self._alert_loop)

    def _run_alert_loop(self):
        asyncio.set_event_loop(self._alert_loop)
        self._alert_loop.run_forever()

    def _detection_loop(self):
        logger.info("Detection loop started")
        while not self._shutdown_event.is_set():
            try:
                for name in self.camera_manager.cameras:
                    if self._shutdown_event.is_set():
                        break
                    frame = self.camera_manager.get_frame(name)
                    if frame is not None:
                        self.event_engine.process_frame(name, frame)
            except Exception as e:
                logger.error(f"Detection loop error: {e}")

            self._shutdown_event.wait(timeout=1)

    def start_recording(self):
        logger.info("Starting continuous recording...")
        for name, cam in self.camera_manager.cameras.items():
            rec_config = cam["config"].get("recording", {})
            if rec_config.get("enabled", True):
                try:
                    self.recorder.start_continuous_recording(
                        name, self.camera_manager,
                        quality=rec_config.get("quality", "low")
                    )
                except Exception as e:
                    logger.error(f"Failed to start recording for {name}: {e}")

    def start_watchdog(self):
        logger.info("Starting camera watchdog...")
        self.camera_manager.start_watchdog()

    def start_telegram(self):
        telegram_app = self.jarvis_bot.run()
        if telegram_app:
            logger.info("Starting Telegram bot...")
            telegram_app.run_polling(drop_pending_updates=True)
        else:
            logger.warning("Running without Telegram bot...")
            self._wait_for_shutdown()

    def start_web_server(self):
        if self.web_dashboard:
            web_config = self.config.get("web", {})
            host = web_config.get("host", "0.0.0.0")
            port = web_config.get("port", 8080)
            logger.info(f"Starting web dashboard on http://{host}:{port}")
            thread = threading.Thread(
                target=self.web_dashboard.run,
                args=(host, port),
                daemon=True
            )
            thread.start()
            return True
        return False

    def _wait_for_shutdown(self):
        while not self._shutdown_event.is_set():
            self._shutdown_event.wait(timeout=1)

    def shutdown(self):
        logger.info("Shutting down JARVIS...")
        self._shutdown_event.set()

        if self.event_engine:
            self.event_engine.stop()

        if self.recorder and self.camera_manager:
            for name in self.camera_manager.cameras:
                self.recorder.stop_continuous_recording(name)

        if self.camera_manager:
            self.camera_manager.stop_watchdog()
            self.camera_manager.disconnect_all()

        logger.info("JARVIS stopped.")

    def run(self):
        JarvisLogger()
        logger.info("=" * 50)
        logger.info("JARVIS Home Security System")
        logger.info("=" * 50)

        if not validate_startup():
            logger.error("Configuration validation failed. Please fix errors.")
            return

        if not self.load_config():
            return

        if not self.initialize_components():
            return

        self.start_alert_loop()
        self.start_cameras()
        self.start_event_processing()
        self.start_recording()
        self.start_watchdog()
        self.start_web_server()

        def signal_handler(sig, frame):
            logger.info(f"Signal {sig} received")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)

        try:
            self.start_telegram()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()


def main():
    jarvis = JarvisHome()
    jarvis.run()


if __name__ == "__main__":
    main()
