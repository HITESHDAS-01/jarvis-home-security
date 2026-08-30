import unittest

from bot.telegram_bot import JarvisBot


class FakeCameraManager:
    def __init__(self):
        self.callback = None
        self.cameras = {"phone cam": {"config": {}}}

    def register_health_callback(self, callback):
        self.callback = callback

    def get_snapshot(self, camera_name):
        if camera_name == "phone cam":
            return "data/snapshots/phone_cam/test.jpg"
        return None

    def get_camera_status(self):
        return {"phone cam": {"connected": True}}


class FakeStorage:
    def get_recent_events(self, hours=2, limit=5):
        return []


class FakeLLMEngine:
    def __init__(self):
        self.image_questions = []
        self.questions = []

    def answer_image_question(self, question, image_path, context=None):
        self.image_questions.append((question, image_path, context))
        return "I can see a live camera snapshot."

    def answer_question(self, question, events=None, camera_status=None):
        self.questions.append((question, events, camera_status))
        return "I understood your message."

    def chat(self, prompt):
        return '{"action":"chat","message":"hello"}'


class MultilingualVisualLLM(FakeLLMEngine):
    def chat(self, prompt):
        return '{"action":"visual","camera":"phone cam"}'


class MultilingualStatusLLM(FakeLLMEngine):
    def chat(self, prompt):
        return '{"action":"status"}'


class TelegramBotConfigTests(unittest.TestCase):
    def test_placeholder_telegram_config_is_not_configured(self):
        camera_manager = FakeCameraManager()
        bot = JarvisBot(
            {
                "telegram": {
                    "bot_token": "YOUR_BOT_TOKEN_HERE",
                    "chat_id": "YOUR_CHAT_ID_HERE",
                }
            },
            camera_manager,
            event_engine=None,
            storage=None,
            llm_engine=None,
            zone_manager=None,
        )

        self.assertFalse(bot._telegram_configured())
        camera_manager.callback("phone cam", "online", "offline")

    def test_natural_language_matches_configured_camera_name(self):
        bot = JarvisBot(
            {"telegram": {}, "security": {"mode": "home"}},
            FakeCameraManager(),
            event_engine=None,
            storage=None,
            llm_engine=None,
            zone_manager=None,
        )

        self.assertEqual(bot._match_camera_name("phone cam ka snapshot bhejo"), "phone cam")

    def test_camera_question_uses_visual_snapshot_analysis(self):
        llm = FakeLLMEngine()
        bot = JarvisBot(
            {"telegram": {}, "security": {"mode": "home"}},
            FakeCameraManager(),
            event_engine=None,
            storage=FakeStorage(),
            llm_engine=llm,
            zone_manager=None,
        )

        response = bot._execute_intent_sync("visual", {}, "what is in the cam")

        self.assertIn("live camera snapshot", response)
        self.assertEqual(llm.image_questions[0][1], "data/snapshots/phone_cam/test.jpg")

    def test_visual_question_detected_before_generic_status(self):
        intent, _ = JarvisBot(
            {"telegram": {}, "security": {"mode": "home"}},
            FakeCameraManager(),
            event_engine=None,
            storage=FakeStorage(),
            llm_engine=FakeLLMEngine(),
            zone_manager=None,
        ).intent_parser.parse("whats going on in camera")

        self.assertEqual(intent, "visual")

    def test_hinglish_visual_question_is_understood(self):
        parser = JarvisBot(
            {"telegram": {}, "security": {"mode": "home"}},
            FakeCameraManager(),
            event_engine=None,
            storage=FakeStorage(),
            llm_engine=FakeLLMEngine(),
            zone_manager=None,
        ).intent_parser

        intent, params = parser.parse("phone cam me kya dikh raha hai", camera_names=["phone cam"])

        self.assertEqual(intent, "visual")
        self.assertEqual(params["camera"], "phone cam")

    def test_camera_typo_still_matches_snapshot(self):
        parser = JarvisBot(
            {"telegram": {}, "security": {"mode": "home"}},
            FakeCameraManager(),
            event_engine=None,
            storage=FakeStorage(),
            llm_engine=FakeLLMEngine(),
            zone_manager=None,
        ).intent_parser

        intent, params = parser.parse("camra ka foto bhejo", camera_names=["phone cam"])

        self.assertEqual(intent, "snapshot")

    def test_today_event_request_maps_to_history_window(self):
        parser = JarvisBot(
            {"telegram": {}, "security": {"mode": "home"}},
            FakeCameraManager(),
            event_engine=None,
            storage=FakeStorage(),
            llm_engine=FakeLLMEngine(),
            zone_manager=None,
        ).intent_parser

        intent, params = parser.parse("aaj kya hua ghar pe")

        self.assertEqual(intent, "events")
        self.assertEqual(params["hours"], 24)

    def test_free_form_message_uses_chat_fallback(self):
        llm = FakeLLMEngine()
        bot = JarvisBot(
            {"telegram": {}, "security": {"mode": "home"}},
            FakeCameraManager(),
            event_engine=None,
            storage=FakeStorage(),
            llm_engine=llm,
            zone_manager=None,
        )

        response = bot._execute_intent_sync("chat", {}, "hello jarvis")

        self.assertEqual(response, "I understood your message.")
        self.assertEqual(llm.questions[0][0], "hello jarvis")

    def test_multilingual_visual_request_uses_llm_router(self):
        parser = JarvisBot(
            {"telegram": {}, "security": {"mode": "home"}},
            FakeCameraManager(),
            event_engine=None,
            storage=FakeStorage(),
            llm_engine=MultilingualVisualLLM(),
            zone_manager=None,
        ).intent_parser

        intent, params = parser.parse("Que hay en la camara?", llm_engine=MultilingualVisualLLM(), camera_names=["phone cam"])

        self.assertEqual(intent, "visual")
        self.assertEqual(params["camera"], "phone cam")

    def test_non_english_status_request_uses_llm_router(self):
        parser = JarvisBot(
            {"telegram": {}, "security": {"mode": "home"}},
            FakeCameraManager(),
            event_engine=None,
            storage=FakeStorage(),
            llm_engine=MultilingualStatusLLM(),
            zone_manager=None,
        ).intent_parser

        intent, _ = parser.parse("Estado del sistema?", llm_engine=MultilingualStatusLLM())

        self.assertEqual(intent, "status")


if __name__ == "__main__":
    unittest.main()
