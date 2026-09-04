import re
from dataclasses import dataclass


MASK = "[DONNÉE SENSIBLE MASQUÉE]"
IBAN_RE = re.compile(r"\b[A-Z]{2}\s?\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b", re.IGNORECASE)
CVV_RE = re.compile(r"\b(?:cvv|cvc|cryptogramme|code\s+de\s+sécurité)\s*(?:est|:)?\s*\d{3,4}\b", re.IGNORECASE)
PASSWORD_RE = re.compile(r"\b(?:mot\s+de\s+passe|password)\s*(?:est|:)?\s*[^\s,.;]{3,}\b", re.IGNORECASE)
CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def luhn_valid(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    parity = len(digits) % 2
    total = 0
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def sensitive_kinds(text: str) -> set[str]:
    kinds: set[str] = set()
    if IBAN_RE.search(text):
        kinds.add("iban")
    if CVV_RE.search(text):
        kinds.add("cryptogramme")
    if PASSWORD_RE.search(text):
        kinds.add("mot_de_passe")
    if any(luhn_valid(match.group()) for match in CARD_CANDIDATE_RE.finditer(text)):
        kinds.add("carte_bancaire")
    return kinds


def redact_free_text(text: str | None) -> tuple[str | None, set[str]]:
    if text is None:
        return None, set()
    kinds = sensitive_kinds(text)
    cleaned = IBAN_RE.sub(MASK, text)
    cleaned = CVV_RE.sub(MASK, cleaned)
    cleaned = PASSWORD_RE.sub(MASK, cleaned)
    cleaned = CARD_CANDIDATE_RE.sub(lambda m: MASK if luhn_valid(m.group()) else m.group(), cleaned)
    return cleaned, kinds
