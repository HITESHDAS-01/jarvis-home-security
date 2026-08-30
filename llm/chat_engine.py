import requests
import base64
from datetime import datetime
from pathlib import Path
from core.logger import get_logger

logger = get_logger("llm")


class LLMEngine:
    def __init__(self, config):
        self.config = config.get("llm", {})
        self.provider = self.config.get("provider", "gemini")
        self.gemini_model = None
        self.openai_client = None
        self._init_provider()

    def _init_provider(self):
        try:
            if self.provider == "gemini":
                api_key = self.config.get("gemini", {}).get("api_key")
                if api_key and api_key not in ["", "YOUR_GEMINI_API_KEY"]:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    self.gemini_model = genai.GenerativeModel(
                        self.config.get("gemini", {}).get("model", "gemini-1.5-flash")
                    )
                    logger.info("Gemini LLM initialized")
                else:
                    logger.warning("Gemini API key not configured")

            elif self.provider == "openai":
                api_key = self.config.get("openai", {}).get("api_key")
                if api_key and api_key not in ["", "YOUR_OPENAI_API_KEY"]:
                    from openai import OpenAI
                    self.openai_client = OpenAI(api_key=api_key)
                    logger.info("OpenAI LLM initialized")
                else:
                    logger.warning("OpenAI API key not configured")

            elif self.provider == "ollama":
                self.ollama_url = self.config.get("ollama", {}).get("base_url", "http://localhost:11434")
                self.ollama_model = self.config.get("ollama", {}).get("model", "llama3.1")
                logger.info(f"Ollama LLM configured: {self.ollama_model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM provider {self.provider}: {e}")

    def chat(self, user_message, context=None, system_prompt=None):
        try:
            if self.provider == "gemini":
                return self._chat_gemini(user_message, context, system_prompt)
            elif self.provider == "openai":
                return self._chat_openai(user_message, context, system_prompt)
            elif self.provider == "ollama":
                return self._chat_ollama(user_message, context, system_prompt)
            return "LLM provider not configured."
        except Exception as e:
            logger.error(f"LLM chat error: {e}")
            return "I encountered an error processing your request."

    def _chat_gemini(self, user_message, context=None, system_prompt=None):
        if not self.gemini_model:
            return "Gemini API key not configured."

        prompt = self._build_prompt(user_message, context, system_prompt)
        try:
            response = self.gemini_model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return f"Error: {str(e)}"

    def _chat_openai(self, user_message, context=None, system_prompt=None):
        if not self.openai_client:
            return "OpenAI API key not configured."

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if context:
            messages.append({"role": "system", "content": f"Context: {context}"})

        messages.append({"role": "user", "content": user_message})

        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.get("openai", {}).get("model", "gpt-4o-mini"),
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return f"Error: {str(e)}"

    def _chat_ollama(self, user_message, context=None, system_prompt=None):
        prompt = self._build_prompt(user_message, context, system_prompt)

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.ollama_model, "prompt": prompt, "stream": False},
                timeout=30,
            )
            return response.json().get("response", "No response from Ollama.")
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama")
            return "Cannot connect to Ollama. Is it running?"
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return f"Error connecting to Ollama: {str(e)}"

    def _build_prompt(self, user_message, context=None, system_prompt=None):
        parts = []

        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        hour = now.hour
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        if system_prompt:
            parts.append(system_prompt)
        else:
            parts.append(
                f"You are JARVIS, a home security AI assistant. "
                f"Current time: {time_str} ({time_of_day}). "
                f"Respond naturally to the user's message like a normal chatbot. "
                f"Do not use forced greetings like Good morning/evening/night "
                f"unless the user specifically greets you first. "
                f"Be concise and helpful. Reply in the same language "
                f"or language mix the user used whenever possible. If the user "
                f"writes Hindi/Hinglish in Roman letters, reply in Roman Hinglish, "
                f"not Hindi script."
            )

        if context:
            parts.append(f"\nCurrent home status:\n{context}")

        parts.append(f"\nUser: {user_message}")

        return "\n".join(parts)

    def summarize_events(self, events, time_range=None):
        if not events:
            return "No events recorded in the specified time."

        context = f"Security events {time_range or 'recent'}:\n"
        for event in events[:10]:
            context += (
                f"- {event.get('timestamp', 'N/A')} | {event.get('camera_name', 'N/A')} | "
                f"{event.get('event_type', 'N/A')} | {event.get('description', 'N/A')}\n"
            )

        prompt = (
            "Summarize these home security events in 2-3 sentences. "
            "Focus on what's important for the homeowner to know. "
            "Be concise and clear."
        )

        return self.chat(prompt, context=context)

    def answer_question(self, question, events=None, camera_status=None):
        context_parts = []

        if events:
            context_parts.append("Recent events:")
            for event in events[:5]:
                context_parts.append(
                    f"- {event.get('timestamp')} | {event.get('camera_name')} | "
                    f"{event.get('event_type')} | {event.get('description')}"
                )

        if camera_status:
            context_parts.append("\nCamera status:")
            for name, status in camera_status.items():
                context_parts.append(f"- {name}: {'Online' if status.get('connected') else 'Offline'}")

        context = "\n".join(context_parts) if context_parts else "No current data available."

        return self.chat(question, context=context)

    def answer_image_question(self, question, image_path, context=None):
        """Answer a question using a live camera snapshot."""
        if not image_path or not Path(image_path).exists():
            return "I could not access a current camera snapshot."

        try:
            if self.provider == "gemini":
                return self._answer_image_gemini(question, image_path, context)
            if self.provider == "openai":
                return self._answer_image_openai(question, image_path, context)
            return (
                "I captured the camera snapshot, but the configured LLM provider "
                "does not support image analysis yet."
            )
        except Exception as e:
            logger.error(f"Image question error: {e}")
            return "I captured the camera snapshot, but could not analyze it."

    def _build_image_prompt(self, question, context=None):
        prompt = (
            "You are JARVIS, a calm home security assistant. Analyze this live "
            "camera snapshot and answer the user's question. Be concise. Mention "
            "visible people, vehicles, packages, animals, unusual activity, and "
            "important safety/security details. Do not invent details that are not "
            "visible in the image. Reply in the same language or language mix the "
            "user used whenever possible. If the user writes Hindi/Hinglish in "
            "Roman letters, reply in Roman Hinglish, not Hindi script."
        )
        if context:
            prompt += f"\n\nCurrent system context:\n{context}"
        prompt += f"\n\nUser question: {question}"
        return prompt

    def _answer_image_gemini(self, question, image_path, context=None):
        if not self.gemini_model:
            return "Gemini API key not configured."

        from PIL import Image

        prompt = self._build_image_prompt(question, context)
        image = Image.open(image_path)
        response = self.gemini_model.generate_content([prompt, image])
        return getattr(response, "text", "").strip() or "I could not describe the camera snapshot."

    def _answer_image_openai(self, question, image_path, context=None):
        if not self.openai_client:
            return "OpenAI API key not configured."

        prompt = self._build_image_prompt(question, context)
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")

        response = self.openai_client.chat.completions.create(
            model=self.config.get("openai", {}).get("model", "gpt-4o-mini"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                    ],
                }
            ],
        )
        return response.choices[0].message.content
