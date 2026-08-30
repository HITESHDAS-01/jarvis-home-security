import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO
from core.logger import get_logger

logger = get_logger("detector")


class Detector:
    def __init__(self, model_name="yolov8n.pt", confidence=0.5, classes=None):
        self.model = None
        self.confidence = confidence
        self.classes = classes or ["person", "car", "motorcycle", "truck"]
        self.class_name_to_id = {}
        self.target_class_ids = []
        self._load_model(model_name)

    def _load_model(self, model_name):
        try:
            self.model = YOLO(model_name)
            self._map_class_names()
            logger.info(f"YOLO model loaded: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise

    def _map_class_names(self):
        self.class_name_to_id = {}
        for idx, name in self.model.names.items():
            self.class_name_to_id[name] = idx

        self.target_class_ids = []
        for cls_name in self.classes:
            if cls_name in self.class_name_to_id:
                self.target_class_ids.append(self.class_name_to_id[cls_name])

        logger.info(f"Target classes: {self.classes} (IDs: {self.target_class_ids})")

    def detect(self, frame):
        if frame is None:
            return []

        try:
            results = self.model(frame, conf=self.confidence, classes=self.target_class_ids, verbose=False)

            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        cls_name = self.model.names[cls_id]

                        detections.append({
                            "bbox": [x1, y1, x2, y2],
                            "confidence": conf,
                            "class_id": cls_id,
                            "class_name": cls_name,
                            "center": [(x1 + x2) // 2, (y1 + y2) // 2],
                        })

            return detections
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def detect_and_annotate(self, frame):
        detections = self.detect(frame)
        annotated = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            label = f"{det['class_name']} {det['confidence']:.2f}"

            color = (0, 0, 255) if det["class_name"] == "person" else (255, 0, 0)

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return annotated, detections

    def is_point_in_zone(self, point, zone_coordinates):
        pts = np.array(zone_coordinates, np.int32)
        result = cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), False)
        return result >= 0

    def check_zone_violations(self, detections, zones):
        violations = []
        for det in detections:
            if det["class_name"] != "person":
                continue

            center = det["center"]
            for zone in zones:
                if self.is_point_in_zone(center, zone.get("coordinates", [])):
                    violations.append({
                        "detection": det,
                        "zone": zone.get("name", "unknown"),
                        "zone_type": zone.get("type", "unknown"),
                    })

        return violations
