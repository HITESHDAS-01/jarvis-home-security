import cv2
import os
import time
import threading
from datetime import datetime
from pathlib import Path
from core.logger import get_logger

logger = get_logger("recorder")


class Recorder:
    def __init__(self, base_path="data/recordings", max_clip_duration=30):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.max_clip_duration = max_clip_duration
        self.active_writers = {}
        self.recording_threads = {}

    def start_continuous_recording(self, camera_name, camera_manager, fps=15, quality="low"):
        if camera_name in self.recording_threads:
            logger.warning(f"Already recording: {camera_name}")
            return

        quality_settings = {
            "low": {"width": 640, "height": 480, "fps": 15},
            "medium": {"width": 1280, "height": 720, "fps": 20},
            "high": {"width": 1920, "height": 1080, "fps": 25},
        }

        settings = quality_settings.get(quality, quality_settings["low"])

        def record_loop():
            try:
                camera_dir = self.base_path / camera_name.replace(" ", "_")
                camera_dir.mkdir(parents=True, exist_ok=True)

                filename = camera_dir / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.mp4"
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = None
                last_date = datetime.now().strftime("%Y-%m-%d")

                while camera_name in self.recording_threads:
                    try:
                        frame = camera_manager.get_frame(camera_name)
                        if frame is None:
                            time.sleep(0.1)
                            continue

                        current_date = datetime.now().strftime("%Y-%m-%d")
                        current_minute = datetime.now().strftime("%M")

                        if writer is None:
                            h, w = frame.shape[:2]
                            w = min(w, settings["width"])
                            h = min(h, settings["height"])
                            writer = cv2.VideoWriter(str(filename), fourcc, settings["fps"], (w, h))

                        resized = cv2.resize(frame, (settings["width"], settings["height"]))
                        writer.write(resized)

                        if current_minute == "00" or current_date != last_date:
                            if writer is not None:
                                writer.release()
                            if current_date != last_date:
                                last_date = current_date
                                camera_dir = self.base_path / camera_name.replace(" ", "_") / current_date
                                camera_dir.mkdir(parents=True, exist_ok=True)
                            else:
                                camera_dir = self.base_path / camera_name.replace(" ", "_") / current_date
                                camera_dir.mkdir(parents=True, exist_ok=True)
                            filename = camera_dir / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.mp4"
                            writer = cv2.VideoWriter(str(filename), fourcc, settings["fps"],
                                                    (settings["width"], settings["height"]))
                    except Exception as e:
                        logger.error(f"Recording error for {camera_name}: {e}")
                        time.sleep(1)

                if writer is not None:
                    writer.release()

                logger.info(f"Recording stopped: {camera_name}")
            except Exception as e:
                logger.error(f"Recording loop failed for {camera_name}: {e}")

        thread = threading.Thread(target=record_loop, daemon=True)
        self.recording_threads[camera_name] = thread
        thread.start()
        logger.info(f"Started continuous recording: {camera_name}")

    def stop_continuous_recording(self, camera_name):
        if camera_name in self.recording_threads:
            del self.recording_threads[camera_name]
            logger.info(f"Stopped continuous recording: {camera_name}")

    def save_event_clip(self, camera_name, camera_manager, duration=10, pre_event_buffer=5):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clip_dir = self.base_path / camera_name.replace(" ", "_") / "events"
            clip_dir.mkdir(parents=True, exist_ok=True)

            filename = clip_dir / f"event_{timestamp}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")

            frames = []
            start_time = time.time()

            while time.time() - start_time < duration:
                frame = camera_manager.get_frame(camera_name)
                if frame is not None:
                    frames.append(frame)
                time.sleep(1 / 15)

            if not frames:
                logger.warning(f"No frames captured for clip: {camera_name}")
                return None

            h, w = frames[0].shape[:2]
            w = min(w, 640)
            h = min(h, 480)
            writer = cv2.VideoWriter(str(filename), fourcc, 15, (w, h))

            for frame in frames:
                resized = cv2.resize(frame, (w, h))
                writer.write(resized)

            writer.release()
            logger.info(f"Saved event clip: {filename}")
            return str(filename)
        except Exception as e:
            logger.error(f"Failed to save clip for {camera_name}: {e}")
            return None

    def save_snapshot(self, frame, camera_name, event_type="event"):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_dir = Path("data/snapshots") / camera_name.replace(" ", "_")
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            filename = snapshot_dir / f"{event_type}_{timestamp}.jpg"
            cv2.imwrite(str(filename), frame)
            return str(filename)
        except Exception as e:
            logger.error(f"Failed to save snapshot for {camera_name}: {e}")
            return None

    def cleanup_old_recordings(self, retention_days=7):
        try:
            cutoff_time = time.time() - (retention_days * 86400)

            for camera_dir in self.base_path.iterdir():
                if not camera_dir.is_dir():
                    continue

                for date_dir in camera_dir.iterdir():
                    if not date_dir.is_dir():
                        continue

                    try:
                        dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                        if dir_date.timestamp() < cutoff_time:
                            import shutil
                            shutil.rmtree(date_dir)
                            logger.info(f"Cleaned up: {date_dir}")
                    except ValueError:
                        continue
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
