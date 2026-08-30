import cv2
import time
import threading
import yaml
import os
import re
import socket
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from core.logger import get_logger

logger = get_logger("camera")


class CameraManager:
    MAX_RECONNECT_ATTEMPTS = 5
    RECONNECT_BASE_DELAY = 5
    WATCHDOG_INTERVAL = 10
    HTTP_CONNECT_TIMEOUT = 2
    HTTP_READ_TIMEOUT = 3

    def __init__(self, config_path="config/cameras.yaml"):
        self.cameras = {}
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self._initialize_cameras()
        self._watchdog_running = False
        self._watchdog_thread = None
        self._health_callbacks = []
        self._running = False

    def _load_config(self, config_path=None):
        config_path = config_path or self.config_path
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            return {"cameras": []}
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in config: {e}")
            return {"cameras": []}

    def _initialize_cameras(self):
        for cam_config in self.config.get("cameras", []):
            name = cam_config.get("name", "Unknown")
            self.cameras[name] = {
                "config": cam_config,
                "stream": None,
                "is_connected": False,
                "last_frame": None,
                "last_frame_time": None,
                "reconnect_attempts": 0,
                "last_status": "unknown",
                "connected_since": None,
            }

    def reload_cameras(self):
        old_cameras = set(self.cameras.keys())
        self.config = self._load_config()
        new_cameras = {c.get("name") for c in self.config.get("cameras", [])}
        for name in old_cameras - new_cameras:
            if name in self.cameras:
                self.disconnect(name)
                del self.cameras[name]
                logger.info(f"Removed camera from memory: {name}")
        for cam_config in self.config.get("cameras", []):
            name = cam_config.get("name", "Unknown")
            if name not in self.cameras:
                self.cameras[name] = {
                    "config": cam_config,
                    "stream": None,
                    "is_connected": False,
                    "last_frame": None,
                    "last_frame_time": None,
                    "reconnect_attempts": 0,
                    "last_status": "unknown",
                    "connected_since": None,
                }
                logger.info(f"Added camera to memory: {name}")
            else:
                self.cameras[name]["config"] = cam_config
        logger.info(f"Cameras reloaded: {len(self.cameras)} cameras in memory")

    def register_health_callback(self, callback):
        self._health_callbacks.append(callback)

    def _fire_health_event(self, camera_name, status, old_status=None):
        for cb in self._health_callbacks:
            try:
                cb(camera_name, status, old_status)
            except Exception as e:
                logger.error(f"Health callback error: {e}")

    def _build_stream_url(self, cam_config):
        mode = cam_config.get("connection_mode", "rtsp")
        ip = cam_config.get("ip", "")
        port = cam_config.get("port", "")
        username = cam_config.get("username", "")
        password = cam_config.get("password", "")
        channel = cam_config.get("channel", 1)
        stream = cam_config.get("stream", 0)

        if ":" in ip:
            ip_parts = ip.rsplit(":", 1)
            ip = ip_parts[0]
            if not port:
                port = ip_parts[1]

        url_map = {
            "rtsp": lambda: cam_config.get("rtsp_url") or self._build_rtsp_url(ip, port, username, password, channel, stream),
            "http": lambda: cam_config.get("http_url") or f"http://{self._auth(username, password)}{ip}:{port}/video",
            "mjpeg": lambda: cam_config.get("mjpeg_url") or f"http://{ip}:{port}/video",
            "onvif": lambda: cam_config.get("onvif_url") or f"rtsp://{self._auth(username, password)}{ip}:{port}/onvif1",
            "wifi": lambda: cam_config.get("wifi_url") or f"rtsp://{self._auth(username, password)}{ip}:{port}/stream{stream}",
            "lan": lambda: cam_config.get("lan_url") or f"rtsp://{self._auth(username, password)}{ip}:{cam_config.get('rtsp_port', '554')}/stream{stream}",
            "usb": lambda: str(cam_config.get("device_id", 0)),
            "file": lambda: cam_config.get("file_path", ""),
        }

        builder = url_map.get(mode)
        return builder() if builder else cam_config.get("rtsp_url", "")

    def _build_rtsp_url(self, ip, port, username, password, channel, stream):
        auth = self._auth(username, password)
        return f"rtsp://{auth}{ip}:{port}/cam/realmonitor?channel={channel}&stream={stream}"

    def _auth(self, username, password):
        if username and password:
            return f"{username}:{password}@"
        return ""

    def _split_host_port(self, cam_config):
        raw_ip = str(cam_config.get("ip", "") or "").strip()
        raw_port = str(cam_config.get("port", "") or "").strip()

        if raw_ip.startswith(("http://", "https://", "rtsp://")):
            parsed = urlparse(raw_ip)
            host = parsed.hostname or raw_ip
            port = raw_port or (str(parsed.port) if parsed.port else "")
            scheme = parsed.scheme or "http"
            return scheme, host, port

        if ":" in raw_ip and raw_ip.count(":") == 1:
            host, embedded_port = raw_ip.rsplit(":", 1)
            if embedded_port.isdigit():
                raw_ip = host
                raw_port = raw_port or embedded_port

        return "http", raw_ip, raw_port

    def _http_auth(self, cam_config):
        username = cam_config.get("username", "")
        password = cam_config.get("password", "")
        return (username, password) if username and password else None

    def _http_snapshot_candidates(self, cam_config):
        explicit = [
            cam_config.get("snapshot_url"),
            cam_config.get("still_url"),
            cam_config.get("http_url"),
        ]
        urls = [u for u in explicit if u]

        scheme, ip, port = self._split_host_port(cam_config)
        if ip:
            base = f"{scheme}://{ip}"
            if port:
                base = f"{base}:{port}"
            urls.extend([
                f"{base}/shot.jpg",
                f"{base}/photo.jpg",
                f"{base}/capture",
                f"{base}/jpg/image.jpg",
            ])

        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)
        return unique_urls

    def _decode_http_image(self, content):
        from PIL import Image
        import io
        import numpy as np

        img = Image.open(io.BytesIO(content))
        return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)

    def get_http_frame(self, cam_config, timeout=8):
        import requests as req

        last_error = "No HTTP snapshot URLs available"
        auth = self._http_auth(cam_config)

        for url in self._http_snapshot_candidates(cam_config):
            try:
                logger.debug(f"Trying HTTP camera snapshot: {url}")
                resp = req.get(url, timeout=timeout, auth=auth)
                if resp.status_code != 200:
                    last_error = f"{url} returned HTTP {resp.status_code}"
                    continue

                content_type = resp.headers.get("content-type", "").lower()
                if "multipart" in content_type:
                    last_error = f"{url} is an MJPEG stream, not a snapshot"
                    continue

                frame = self._decode_http_image(resp.content)
                return True, frame, url, None
            except Exception as e:
                last_error = f"{url}: {e}"

        return False, None, None, last_error

    def test_camera_config(self, cam_config, timeout=8):
        mode = cam_config.get("connection_mode", "rtsp")
        if mode in ("http", "mjpeg"):
            ok, frame, url, error = self.get_http_frame(cam_config, timeout=timeout)
            if ok:
                h, w = frame.shape[:2]
                return True, f"Connected! Frame: {w}x{h} via {url}", frame
            return False, error or "Could not read HTTP camera snapshot", None

        stream_url = self._build_stream_url(cam_config)
        try:
            cap = cv2.VideoCapture(stream_url)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)
            if cam_config.get("connection_mode") in ["usb", "file"]:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            ret, frame = cap.read() if cap.isOpened() else (False, None)
            cap.release()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                return True, f"Connected! Frame: {w}x{h}", frame
            return False, "Could not read frame. Check URL/credentials.", None
        except Exception as e:
            logger.error(f"Camera test failed: {e}")
            return False, str(e), None

    def connect(self, camera_name):
        if camera_name not in self.cameras:
            logger.error(f"Unknown camera: {camera_name}")
            return False

        cam = self.cameras[camera_name]
        cam_config = cam["config"]
        stream_url = self._build_stream_url(cam_config)
        mode = cam_config.get("connection_mode", "rtsp")

        try:
            if mode in ("http", "mjpeg"):
                ok, test_frame, snapshot_url, error = self.get_http_frame(cam_config, timeout=self.HTTP_CONNECT_TIMEOUT)
                if ok:
                    old_status = cam["last_status"]
                    cam["is_connected"] = True
                    cam["last_frame"] = test_frame
                    cam["last_frame_time"] = datetime.now()
                    cam["reconnect_attempts"] = 0
                    cam["last_status"] = "online"
                    cam["connected_since"] = datetime.now()
                    cam["_http_mode"] = True
                    cam["_http_snapshot_url"] = snapshot_url
                    logger.info(f"Connected: {camera_name} ({mode})")
                    if old_status != "online":
                        self._fire_health_event(camera_name, "online", old_status)
                    reader = cam.get("_http_reader_thread")
                    if reader is None or not reader.is_alive():
                        reader = threading.Thread(target=self._http_frame_reader, args=(camera_name,), daemon=True)
                        cam["_http_reader_thread"] = reader
                        reader.start()
                    return True
                else:
                    logger.warning(f"Failed to connect {camera_name}: {error}")
                    return False
            else:
                cap = cv2.VideoCapture(stream_url)
                if mode in ["usb", "file"]:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if cap.isOpened():
                    ret, test_frame = cap.read()
                    if ret:
                        old_status = cam["last_status"]
                        cam["stream"] = cap
                        cam["is_connected"] = True
                        cam["last_frame"] = test_frame
                        cam["last_frame_time"] = datetime.now()
                        cam["reconnect_attempts"] = 0
                        cam["last_status"] = "online"
                        cam["connected_since"] = datetime.now()
                        cam["_http_mode"] = False
                        logger.info(f"Connected: {camera_name} ({mode})")
                        if old_status != "online":
                            self._fire_health_event(camera_name, "online", old_status)
                        return True
                    else:
                        cap.release()
                        logger.warning(f"Connected but no frame: {camera_name}")
                        return False
                else:
                    cap.release()
                    logger.warning(f"Failed to connect: {camera_name}")
                    return False
        except Exception as e:
            logger.error(f"Error connecting {camera_name}: {e}")
            return False

    def _http_frame_reader(self, camera_name):
        import time as _time
        cam = self.cameras.get(camera_name)
        if not cam:
            return
        cam_config = cam["config"]
        shot_url = cam.get("_http_snapshot_url")
        logger.info(f"HTTP frame reader started: {camera_name} -> {shot_url}")
        while cam["is_connected"] and self._running:
            try:
                if shot_url:
                    ok, frame, _, error = self.get_http_frame(
                        {**cam_config, "snapshot_url": shot_url},
                        timeout=self.HTTP_READ_TIMEOUT,
                    )
                else:
                    ok, frame, shot_url, error = self.get_http_frame(cam_config, timeout=self.HTTP_READ_TIMEOUT)
                    cam["_http_snapshot_url"] = shot_url
                if ok:
                    cam["last_frame"] = frame
                    cam["last_frame_time"] = datetime.now()
                    cam["last_status"] = "online"
                else:
                    logger.warning(f"HTTP frame read failed: {camera_name}: {error}")
                    cam["last_status"] = "error"
            except Exception as e:
                logger.error(f"HTTP frame reader error: {camera_name}: {e}")
                cam["last_status"] = "error"
                cam["is_connected"] = False
                self._fire_health_event(camera_name, "offline", "online")
                break
            _time.sleep(1)

    def connect_all(self):
        self._running = True
        logger.info(f"Connecting {len(self.cameras)} cameras...")
        threads = []
        for name in self.cameras:
            t = threading.Thread(target=self.connect, args=(name,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=15)

        online = sum(1 for c in self.cameras.values() if c["is_connected"])
        logger.info(f"Cameras connected: {online}/{len(self.cameras)}")

    def get_frame(self, camera_name):
        if camera_name not in self.cameras:
            return None

        cam = self.cameras[camera_name]
        if not cam["is_connected"]:
            return None

        if cam.get("_http_mode"):
            return cam.get("last_frame")

        if cam["stream"] is None:
            return None

        try:
            ret, frame = cam["stream"].read()
            if ret:
                cam["last_frame"] = frame
                cam["last_frame_time"] = datetime.now()
                return frame
            else:
                self._handle_disconnect(camera_name)
                return None
        except Exception as e:
            logger.error(f"Error reading frame from {camera_name}: {e}")
            self._handle_disconnect(camera_name)
            return None

    def _handle_disconnect(self, camera_name):
        cam = self.cameras.get(camera_name)
        if not cam:
            return

        if cam["is_connected"]:
            old_status = cam["last_status"]
            cam["is_connected"] = False
            cam["last_status"] = "offline"
            cam["stream"] = None
            logger.warning(f"Disconnected: {camera_name}")
            self._fire_health_event(camera_name, "offline", old_status)

    def get_latest_frame(self, camera_name):
        if camera_name in self.cameras:
            return self.cameras[camera_name].get("last_frame")
        return None

    def get_all_frames(self):
        frames = {}
        for name in self.cameras:
            frame = self.get_frame(name)
            if frame is not None:
                frames[name] = frame
        return frames

    def get_snapshot(self, camera_name):
        frame = self.get_frame(camera_name)
        if frame is None:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\s-]', '', camera_name).replace(' ', '_')
        filename = f"{safe_name}_{timestamp}.jpg"
        snapshot_dir = Path("data/snapshots")
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        filepath = snapshot_dir / filename

        try:
            cv2.imwrite(str(filepath), frame)
            return str(filepath)
        except Exception as e:
            logger.error(f"Error saving snapshot for {camera_name}: {e}")
            return None

    def disconnect(self, camera_name):
        if camera_name in self.cameras:
            cam = self.cameras[camera_name]
            if cam.get("_http_mode"):
                resp = cam.get("_http_stream")
                if resp:
                    try:
                        resp.close()
                    except Exception:
                        pass
                cam["_http_stream"] = None
            if cam["stream"] is not None:
                try:
                    cam["stream"].release()
                except Exception:
                    pass
                cam["stream"] = None
            cam["is_connected"] = False
            cam["last_status"] = "disconnected"
            logger.info(f"Disconnected: {camera_name}")

    def disconnect_all(self):
        self._running = False
        for name in self.cameras:
            self.disconnect(name)

    def get_camera_status(self):
        status = {}
        for name, cam in self.cameras.items():
            status[name] = {
                "connected": cam["is_connected"],
                "status": cam["last_status"],
                "connection_mode": cam["config"].get("connection_mode", "rtsp"),
                "ip": cam["config"].get("ip", "N/A"),
                "last_frame_time": str(cam["last_frame_time"]) if cam["last_frame_time"] else None,
                "connected_since": str(cam["connected_since"]) if cam["connected_since"] else None,
                "reconnect_attempts": cam["reconnect_attempts"],
            }
        return status

    def _reconnect_with_backoff(self, camera_name):
        cam = self.cameras.get(camera_name)
        if not cam:
            return

        if cam["reconnect_attempts"] >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error(f"Max reconnect attempts reached for {camera_name}")
            return

        delay = self.RECONNECT_BASE_DELAY * (2 ** cam["reconnect_attempts"])
        delay = min(delay, 120)
        cam["reconnect_attempts"] += 1

        logger.info(f"Reconnecting {camera_name} in {delay}s (attempt {cam['reconnect_attempts']}/{self.MAX_RECONNECT_ATTEMPTS})")
        time.sleep(delay)

        if self.connect(camera_name):
            logger.info(f"Reconnected: {camera_name}")

    def start_watchdog(self):
        if self._watchdog_running:
            return

        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        logger.info("Camera watchdog started")

    def stop_watchdog(self):
        self._watchdog_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5)
        logger.info("Camera watchdog stopped")

    def _watchdog_loop(self):
        while self._watchdog_running:
            for name, cam in self.cameras.items():
                if not cam["is_connected"]:
                    if cam["reconnect_attempts"] < self.MAX_RECONNECT_ATTEMPTS:
                        threading.Thread(
                            target=self._reconnect_with_backoff,
                            args=(name,),
                            daemon=True
                        ).start()

                else:
                    if cam["last_frame_time"]:
                        elapsed = (datetime.now() - cam["last_frame_time"]).total_seconds()
                        if elapsed > 30:
                            logger.warning(f"No frames from {name} for {elapsed:.0f}s")
                            self._handle_disconnect(name)

            time.sleep(self.WATCHDOG_INTERVAL)

    def reconnect(self, camera_name):
        self.disconnect(camera_name)
        cam = self.cameras.get(camera_name)
        if cam:
            cam["reconnect_attempts"] = 0
        time.sleep(2)
        return self.connect(camera_name)

    def reconnect_all(self):
        self.disconnect_all()
        for cam in self.cameras.values():
            cam["reconnect_attempts"] = 0
        time.sleep(2)
        self.connect_all()

    def scan_lan_cameras(self, subnet=None, ports=None):
        if ports is None:
            ports = [554, 80, 8080, 8000, 37777, 8899]

        if subnet is None:
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                subnet = ".".join(local_ip.split(".")[:-1])
            except Exception as e:
                logger.error(f"Cannot determine subnet: {e}")
                return []

        logger.info(f"Scanning subnet: {subnet}.0/24")
        found_cameras = []

        def scan_ip(ip):
            for port in ports:
                sock = None
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    result = sock.connect_ex((ip, port))
                    if result == 0:
                        found_cameras.append({"ip": ip, "port": port})
                        logger.debug(f"Found device: {ip}:{port}")
                except Exception:
                    pass
                finally:
                    if sock:
                        try:
                            sock.close()
                        except Exception:
                            pass

        threads = []
        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            t = threading.Thread(target=scan_ip, args=(ip,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=3)

        logger.info(f"Scan complete: found {len(found_cameras)} devices")
        return found_cameras

    def test_camera_url(self, url, timeout=5):
        try:
            cap = cv2.VideoCapture(url)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                return ret, frame.shape if ret else None
            cap.release()
            return False, None
        except Exception as e:
            logger.error(f"Test failed for {url}: {e}")
            return False, str(e)

    def add_camera(self, name, connection_mode, ip=None, port=None, username=None,
                   password=None, rtsp_url=None, zones=None, recording_config=None):
        cam_config = {"name": name, "connection_mode": connection_mode}

        if ip: cam_config["ip"] = ip
        if port: cam_config["port"] = str(port)
        if username: cam_config["username"] = username
        if password: cam_config["password"] = password
        if rtsp_url: cam_config["rtsp_url"] = rtsp_url

        cam_config["zones"] = zones or []
        cam_config["recording"] = recording_config or {
            "enabled": True, "mode": "hybrid", "quality": "low", "retention_days": 7,
        }

        self.cameras[name] = {
            "config": cam_config,
            "stream": None,
            "is_connected": False,
            "last_frame": None,
            "last_frame_time": None,
            "reconnect_attempts": 0,
            "last_status": "unknown",
            "connected_since": None,
        }

        self.config["cameras"].append(cam_config)
        self._save_config()
        logger.info(f"Added camera: {name} ({connection_mode})")
        return True

    def remove_camera(self, name):
        if name in self.cameras:
            self.disconnect(name)
            del self.cameras[name]
            self.config["cameras"] = [c for c in self.config["cameras"] if c.get("name") != name]
            self._save_config()
            logger.info(f"Removed camera: {name}")
            return True
        return False

    def _save_config(self):
        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def list_connection_modes(self):
        return {
            "rtsp": "RTSP stream (most IP cameras)",
            "http": "HTTP stream",
            "mjpeg": "MJPEG stream",
            "onvif": "ONVIF protocol",
            "wifi": "WiFi camera (RTSP)",
            "lan": "LAN camera (direct IP)",
            "usb": "USB camera (local)",
            "file": "Video file (for testing)",
        }
