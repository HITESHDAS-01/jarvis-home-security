import time
import threading
from datetime import datetime
from core.detector import Detector
from core.storage import EventStorage
from core.recorder import Recorder
from core.logger import get_logger, SecurityLogger

logger = get_logger("event_engine")
security_log = SecurityLogger()


class EventDeduplicator:
    def __init__(self, cooldown_seconds=60):
        self.cooldown = cooldown_seconds
        self.last_events = {}
        self._lock = threading.Lock()

    def is_duplicate(self, camera_name, event_type, zone=None):
        key = f"{camera_name}:{event_type}:{zone or 'none'}"

        with self._lock:
            now = time.time()
            last_time = self.last_events.get(key, 0)

            if now - last_time < self.cooldown:
                return True

            self.last_events[key] = now
            return False

    def cleanup(self, max_age=300):
        with self._lock:
            now = time.time()
            self.last_events = {
                k: v for k, v in self.last_events.items()
                if now - v < max_age
            }


class EventEngine:
    def __init__(self, camera_manager, detector, storage, recorder, config):
        self.camera_manager = camera_manager
        self.detector = detector
        self.storage = storage
        self.recorder = recorder
        self.config = config
        self.running = False
        self.event_callbacks = []
        self.detection_interval = config.get("detection", {}).get("frame_interval", 5)
        self.frame_count = 0
        self.last_detections = {}
        self.deduplicator = EventDeduplicator(cooldown_seconds=60)
        self._cleanup_thread = None

    def register_callback(self, callback):
        self.event_callbacks.append(callback)

    def _fire_event(self, event_data):
        for callback in self.event_callbacks:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def process_frame(self, camera_name, frame):
        if frame is None:
            return

        try:
            self.frame_count += 1
            if self.frame_count % self.detection_interval != 0:
                return

            detections = self.detector.detect(frame)
            self.last_detections[camera_name] = detections

            if not detections:
                return

            person_count = sum(1 for d in detections if d["class_name"] == "person")

            camera_config = self._get_camera_config(camera_name)
            zones = camera_config.get("zones", []) if camera_config else []

            violations = self.detector.check_zone_violations(detections, zones) if zones else []

            events = []

            for det in detections:
                if det["class_name"] == "person":
                    event = self._create_person_event(camera_name, det, violations)
                    if event:
                        events.append(event)

            if person_count > 2:
                events.append({
                    "camera_name": camera_name,
                    "event_type": "multiple_people",
                    "severity": "medium",
                    "description": f"{person_count} people detected",
                    "detection_data": {"count": person_count, "detections": detections},
                })

            for violation in violations:
                events.append({
                    "camera_name": camera_name,
                    "event_type": "zone_violation",
                    "severity": "high",
                    "zone": violation["zone"],
                    "description": f"Person entered restricted zone: {violation['zone']}",
                    "detection_data": violation["detection"],
                })

            for event in events:
                self._process_event(event, frame)

        except Exception as e:
            logger.error(f"Error processing frame from {camera_name}: {e}")

    def _get_camera_config(self, camera_name):
        if hasattr(self, 'camera_manager') and self.camera_manager:
            cam = self.camera_manager.cameras.get(camera_name, {})
            return cam.get("config", {})
        return None

    def _create_person_event(self, camera_name, detection, violations):
        hour = datetime.now().hour
        night_start = self.config.get("security", {}).get("night_hours", {}).get("start", "22:00")
        night_end = self.config.get("security", {}).get("night_hours", {}).get("end", "06:00")
        try:
            ns_h, ns_m = map(int, night_start.split(":"))
            ne_h, ne_m = map(int, night_end.split(":"))
            is_night = (hour >= ns_h or hour < ne_h)
        except:
            is_night = hour >= 22 or hour < 6
        severity = "high" if is_night else "medium"

        event_in_violation = any(v["detection"] == detection for v in violations)

        if event_in_violation:
            severity = "high"

        description = f"Person detected at {camera_name}"
        if is_night:
            description += " (night)"
        if event_in_violation:
            description += f" [zone: {next((v['zone'] for v in violations if v['detection'] == detection), '')}]"

        return {
            "camera_name": camera_name,
            "event_type": "person_detected",
            "severity": severity,
            "description": description,
            "detection_data": detection,
        }

    def _process_event(self, event, frame):
        camera_name = event["camera_name"]
        event_type = event["event_type"]
        zone = event.get("zone")

        if self.deduplicator.is_duplicate(camera_name, event_type, zone):
            logger.debug(f"Deduplicated: {event_type} at {camera_name}")
            return

        try:
            snapshot_path = self.recorder.save_snapshot(frame, camera_name, event_type)

            event_id = self.storage.create_event(
                camera_name=camera_name,
                event_type=event_type,
                severity=event.get("severity", "medium"),
                zone=zone,
                description=event.get("description"),
                snapshot_path=snapshot_path,
                detection_data=event.get("detection_data"),
            )

            event["id"] = event_id
            event["snapshot_path"] = snapshot_path
            event["timestamp"] = datetime.now().isoformat()

            self._fire_event(event)

            security_log.log_event(
                event_type=event_type,
                camera=camera_name,
                severity=event.get("severity", "medium"),
                description=event.get("description", ""),
                zone=zone,
            )

            logger.info(f"Event: {event_type} at {camera_name} (severity: {event.get('severity', 'medium')})")

        except Exception as e:
            logger.error(f"Error processing event: {e}")

    def get_latest_detections(self, camera_name=None):
        if camera_name:
            return self.last_detections.get(camera_name, [])
        return self.last_detections

    def start(self):
        self.running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("Event engine started")

    def stop(self):
        self.running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        logger.info("Event engine stopped")

    def _cleanup_loop(self):
        while self.running:
            time.sleep(300)
            self.deduplicator.cleanup()
