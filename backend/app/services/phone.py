from __future__ import annotations

import re

WORD_DIGITS = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "ate": "8",
    "nine": "9",
}


def normalize_indian_phone(value: str) -> str:
    """Normalize a spoken or typed Indian mobile number to +91XXXXXXXXXX."""
    if not value or not isinstance(value, str):
        raise ValueError("Please provide the 10-digit mobile number.")

    text = value.lower().replace("+", " plus ")
    tokens = re.findall(r"[a-z]+|\d+", text)
    spoken_digits = "".join(WORD_DIGITS[token] for token in tokens if token in WORD_DIGITS)
    digits = spoken_digits or re.sub(r"\D", "", value)

    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    if len(digits) != 10:
        raise ValueError("I could not read a valid 10-digit Indian mobile number. Please repeat it.")
    if digits[0] not in "6789":
        raise ValueError("That does not look like a valid Indian mobile number. Please repeat it.")
    return f"+91{digits}"


def format_phone_for_speech(normalized: str) -> str:
    digits = normalized.removeprefix("+91")
    return "+91 " + " ".join(digits)


def mask_phone(number: str) -> str:
    digits = re.sub(r"\D", "", number or "")
    if len(digits) < 4:
        return "••••"
    return f"+91 ••••• {digits[-4:]}"
