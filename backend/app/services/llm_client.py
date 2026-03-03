from __future__ import annotations

import httpx

from app.config import Settings


class LlmClientService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        local_error: Exception | None = None
        try:
            return self._generate_local(system_prompt, user_prompt)
        except Exception as exc:
            local_error = exc

        if self.settings.openai_api_key:
            return self._generate_openai(system_prompt, user_prompt)

        raise RuntimeError(f"llm_generation_failed:{local_error.__class__.__name__ if local_error else 'unknown'}")

    def _generate_local(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
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
                return content.strip(), self.settings.llm_model_name
            choices = body.get("choices")
            if isinstance(choices, list) and choices:
                text = choices[0].get("text") if isinstance(choices[0], dict) else None
                if isinstance(text, str) and text.strip():
                    return text.strip(), self.settings.llm_model_name
        raise RuntimeError("llm_response_missing_content")

    def _generate_openai(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        timeout_seconds = max(1.0, self.settings.llm_timeout_ms / 1000.0)
        payload = {
            "model": self.settings.openai_model,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        response = httpx.post(
            f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices", [])
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str) and content.strip():
                return content.strip(), self.settings.openai_model
        raise RuntimeError("openai_response_missing_content")

    def _compose_prompt(self, system_prompt: str, user_prompt: str) -> str:
        return (
            f"<|system|>\n{system_prompt}\n"
            f"<|user|>\n{user_prompt}\n"
            "<|assistant|>\n"
        )
