from __future__ import annotations

import re

from app.config import Settings


class AdvisoryValidationService:
    REQUIRED_SECTIONS = [
        "Verdict:",
        "Suggested down payment:",
        "Market conditions this week:",
        "Key risks:",
        "Primary action:",
        "Note:",
    ]

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate(self, text: str) -> tuple[bool, list[str]]:
        errors: list[str] = []
        stripped = text.strip()
        if not stripped:
            return False, ["empty_response"]

        if len(stripped) > self.settings.llm_max_response_chars:
            errors.append("response_too_long")

        lowered = stripped.lower()
        for label in self.REQUIRED_SECTIONS:
            if label.lower() not in lowered:
                errors.append(f"missing_section:{label}")

        down_payment_line = self._extract_labeled_line(stripped, "Suggested down payment:")
        if down_payment_line is None:
            errors.append("missing_down_payment_line")
        elif not self._contains_cad_amount(down_payment_line):
            errors.append("down_payment_missing_cad_amount")

        is_valid = len(errors) == 0
        return is_valid, errors

    def _extract_labeled_line(self, text: str, label: str) -> str | None:
        pattern = re.compile(rf"{re.escape(label)}\s*(.+)", re.IGNORECASE)
        match = pattern.search(text)
        if not match:
            return None
        return match.group(1).strip()

    def _contains_cad_amount(self, text: str) -> bool:
        return bool(
            re.search(r"(CAD\s*\$?\s*\d[\d,]*)|(\$\s*\d[\d,]*\s*CAD)|(\$\s*\d[\d,]*)", text, flags=re.IGNORECASE)
        )
