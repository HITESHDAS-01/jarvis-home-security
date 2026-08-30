import tempfile
import unittest
from pathlib import Path

import yaml

from core.camera_manager import CameraManager


class CameraManagerConfigTests(unittest.TestCase):
    def test_reload_cameras_uses_original_config_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "cameras.yaml"
            config_path.write_text(
                yaml.dump({"cameras": [{"name": "Old", "connection_mode": "http", "ip": "1.1.1.1", "port": "8080"}]}),
                encoding="utf-8",
            )

            manager = CameraManager(str(config_path))
            config_path.write_text(
                yaml.dump({"cameras": [{"name": "New", "connection_mode": "http", "ip": "2.2.2.2", "port": "8080"}]}),
                encoding="utf-8",
            )

            manager.reload_cameras()

            self.assertNotIn("Old", manager.cameras)
            self.assertIn("New", manager.cameras)

    def test_http_camera_accepts_embedded_port(self):
        manager = CameraManager.__new__(CameraManager)
        manager.config_path = "config/cameras.yaml"

        scheme, host, port = manager._split_host_port({"ip": "192.168.31.183:8080", "port": ""})

        self.assertEqual(scheme, "http")
        self.assertEqual(host, "192.168.31.183")
        self.assertEqual(port, "8080")

    def test_http_snapshot_candidates_include_ip_webcam_endpoint(self):
        manager = CameraManager.__new__(CameraManager)
        manager.config_path = "config/cameras.yaml"

        urls = manager._http_snapshot_candidates({"ip": "192.168.31.183", "port": "8080"})

        self.assertIn("http://192.168.31.183:8080/shot.jpg", urls)


if __name__ == "__main__":
    unittest.main()
