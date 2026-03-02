from __future__ import annotations

import httpx

from app.config import Settings


class LlmClientService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        timeout_seconds = max(1.0, self.settings.llm_timeout_ms / 1000.0)
        prompt = self._compose_prompt(system_prompt, user_prompt)
        payload = {
            "prompt": prompt,
            "n_predict": self.settings.llm_max_tokens,
            "temperature": self.settings.llm_temperature,
            "stop": ["<END_OF_ADVICE>"],
        }

        response = httpx.post(
            f"{self.settings.llm_base_url.rstrip('/')}/completion",
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()

        if isinstance(body, dict):
            content = body.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            choices = body.get("choices")
            if isinstance(choices, list) and choices:
                text = choices[0].get("text") if isinstance(choices[0], dict) else None
                if isinstance(text, str) and text.strip():
                    return text.strip()
        raise RuntimeError("llm_response_missing_content")

    def _compose_prompt(self, system_prompt: str, user_prompt: str) -> str:
        return (
            f"<|system|>\n{system_prompt}\n"
            f"<|user|>\n{user_prompt}\n"
            "<|assistant|>\n"
        )
