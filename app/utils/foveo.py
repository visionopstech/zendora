import re
from typing import Optional, Sequence

FOVEO_PASSWORD_MANAGED_MESSAGE = "Password is managed on Foveo"

_PLACEHOLDER_FAMILY_LOCAL = re.compile(r"^family_[a-z]{5}$")
_TUKIOS_PLACEHOLDER_LOCAL = "tukios_nok"


def is_foveo_linked(user) -> bool:
    """True when this Zendora user is owned by a Foveo identity."""
    return getattr(user, "foveo_user_id", None) is not None


def normalize_password_hash(value: Optional[str]) -> Optional[str]:
    """Return a usable Django/passlib hash, or None for missing/unusable passwords."""
    if not value:
        return None
    stripped = value.strip()
    if not stripped or stripped.startswith("!"):
        return None
    return stripped


def is_placeholder_email(email: Optional[str], domains: Sequence[str]) -> bool:
    """
    True for Foveo-generated family placeholders that must not be synced.

    Real staff addresses on the same domain (anything other than family_xxxxx
    or tukios_nok) still sync.
    """
    if not email or "@" not in email:
        return False
    local, domain = email.lower().strip().rsplit("@", 1)
    allowed = {item.lower() for item in domains}
    if domain not in allowed:
        return False
    if local == _TUKIOS_PLACEHOLDER_LOCAL:
        return True
    return bool(_PLACEHOLDER_FAMILY_LOCAL.fullmatch(local))
