from typing import Optional


def split_full_name(full_name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Split a legacy or third-party full name into first and last name."""
    if not full_name or not full_name.strip():
        return None, None

    first, _, remainder = full_name.strip().partition(" ")
    last = remainder.strip() or None
    return first or None, last


def display_name(first_name: Optional[str], last_name: Optional[str]) -> str:
    """Join first and last name for emails and admin display."""
    return " ".join(part for part in (first_name, last_name) if part).strip()
