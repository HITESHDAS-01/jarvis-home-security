import unittest

from web.app import WebDashboard


class FakeCameraManager:
    def get_camera_status(self):
        return {}


class FakeStorage:
    def get_recent_events(self, hours=2, limit=20):
        return []

    def get_database_stats(self):
        return {}


class FakeZoneManager:
    zones = {}
    rules = []


class WebDashboardTests(unittest.TestCase):
    def make_dashboard(self):
        config = {
            "security": {"mode": "home"},
            "detection": {"classes_to_detect": ["person"]},
            "telegram": {"bot_token": "YOUR_BOT_TOKEN_HERE", "chat_id": "YOUR_CHAT_ID_HERE"},
            "llm": {"provider": "gemini", "gemini": {"api_key": "YOUR_GEMINI_API_KEY"}},
            "recording": {"base_path": "data/recordings"},
            "database": {"path": "data/events.db"},
        }
        return WebDashboard(FakeCameraManager(), None, FakeStorage(), FakeZoneManager(), config)

    def test_restart_route_exists(self):
        dashboard = self.make_dashboard()
        rules = {rule.rule for rule in dashboard.app.url_map.iter_rules()}

        self.assertIn("/api/restart", rules)

    def test_legacy_target_classes_maps_to_runtime_key(self):
        dashboard = self.make_dashboard()
        dashboard._save_config = lambda: None
        client = dashboard.app.test_client()
        with client.session_transaction() as session:
            session["authenticated"] = True

        response = client.post("/api/settings", json={"detection": {"target_classes": ["car"]}})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(dashboard.config["detection"]["classes_to_detect"], ["car"])
        self.assertNotIn("target_classes", dashboard.config["detection"])


if __name__ == "__main__":
    unittest.main()
