
import re


PROMPT_INJECTION_PATTERNS = [
    r"ignore (all|any|the|previous|prior) instructions",
    r"ignore your instructions",
    r"forget your instructions",
    r"reveal (your|the) system prompt",
    r"show (me )?(your|the) system prompt",
    r"what are your system instructions",
    r"bypass (your|the) (rules|instructions|restrictions)",
    r"override (your|the) instructions",
    r"disregard (all|your|the) previous instructions",
]


def detect_prompt_injection(text):
    if not text:
        return False

    text = text.lower()

    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text):
            return True

    return False