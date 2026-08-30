import unittest

from llm.chat_engine import LLMEngine


class LLMEnginePromptTests(unittest.TestCase):
    def make_engine(self):
        engine = LLMEngine.__new__(LLMEngine)
        engine.config = {}
        return engine

    def test_chat_prompt_preserves_roman_hinglish(self):
        prompt = self.make_engine()._build_prompt("kya ho raha hai me")

        self.assertIn("Roman Hinglish", prompt)
        self.assertIn("not Hindi script", prompt)

    def test_image_prompt_preserves_roman_hinglish(self):
        prompt = self.make_engine()._build_image_prompt("kya ho raha hai me")

        self.assertIn("Roman Hinglish", prompt)
        self.assertIn("not Hindi script", prompt)


if __name__ == "__main__":
    unittest.main()
