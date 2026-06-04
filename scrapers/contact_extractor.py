from __future__ import annotations

import re

PHONE_PATTERN: str = r"(?:\+62|62|08)[\d\s\-]{8,15}"
EMAIL_PATTERN: str = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"

PHONE_REGEX = re.compile(PHONE_PATTERN)
EMAIL_REGEX = re.compile(EMAIL_PATTERN)


def extract_phone_numbers(text: str) -> list[str]:
    if not text:
        return []

    raw_matches = PHONE_REGEX.findall(text)
    cleaned: list[str] = []
    for phone in raw_matches:
        normalized = re.sub(r"[\s\-]", "", phone)
        if len(normalized) < 10:
            continue
        if normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def extract_emails(text: str) -> list[str]:
    if not text:
        return []

    raw_matches = EMAIL_REGEX.findall(text)
    cleaned: list[str] = []
    for email in raw_matches:
        lower_email = email.lower()
        if lower_email not in cleaned:
            cleaned.append(lower_email)
    return cleaned


def extract_contacts(text: str) -> dict[str, list[str]]:
    return {
        "phones": extract_phone_numbers(text),
        "emails": extract_emails(text),
    }
