"""
Lector license management — Gumroad license key verification.

Uses urllib only (stdlib, zero external deps). Designed to be called from
server.py endpoints. License state is cached locally with a 7-day offline
grace period.

Flow:
  1. Frontend calls GET /license/check on load.
  2. If invalid, frontend shows activation overlay.
  3. User enters key → POST /license/activate.
  4. On every subsequent load: POST verify with increment_uses_count=false;
     fall back to cached state if offline (grace period: 7 days).
  5. Refunded/chargebacked keys: hard block.
"""
import hashlib
import json
import logging
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import platformdirs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_DIR      = Path(platformdirs.user_config_dir("Lector", appauthor=False))
LICENSE_PATH    = CONFIG_DIR / "license.json"
GUMROAD_VERIFY  = "https://api.gumroad.com/v2/licenses/verify"
GRACE_DAYS      = 7
TIMEOUT         = 10   # seconds

# Gumroad product_id — set after publishing.
PRODUCT_ID      = ""  # TODO: fill after Gumroad product is published

MAX_USES        = 3   # Lector: single tier, 3 devices


# ---------------------------------------------------------------------------
# Machine fingerprint — SHA-256 of a stable hardware identifier
# ---------------------------------------------------------------------------

def _machine_fingerprint() -> str:
    raw = _raw_machine_id()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _raw_machine_id() -> str:
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            return value
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        except Exception:
            pass
    else:
        try:
            return open("/etc/machine-id").read().strip()
        except Exception:
            pass
    import socket
    return socket.gethostname()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(url: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req  = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _load() -> dict | None:
    if not LICENSE_PATH.exists():
        return None
    try:
        with LICENSE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to read license file")
        return None


def _save(data: dict) -> None:
    try:
        LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LICENSE_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        logger.exception("Failed to save license file")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _friendly_error(raw: str) -> str:
    low = (raw or "").lower()
    if "not found" in low or "does not exist" in low:
        return (
            "License key not found. "
            "Check the key in your receipt email and try again."
        )
    return raw or "Activation failed. Contact hello@simdadllc.com."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _dev_mode() -> bool:
    """True when PRODUCT_ID is unset — skip license enforcement during development."""
    return not PRODUCT_ID


def activate(key: str) -> tuple[bool, str]:
    """
    Activate a license key via Gumroad.
    Returns (success, error_message). On success error_message is empty.
    """
    if _dev_mode():
        logger.info("Dev mode — license activation skipped (PRODUCT_ID not set)")
        _save({
            "license_key": "dev-mode",
            "product_name": "Lector (dev)",
            "email": "",
            "uses": 1,
            "max_uses": MAX_USES,
            "activated_at": _now_iso(),
            "last_validated": _now_iso(),
            "machine_id": _machine_fingerprint(),
        })
        return True, ""
    key = key.strip()
    try:
        data = _post(GUMROAD_VERIFY, {
            "product_id":           PRODUCT_ID,
            "license_key":          key,
            "increment_uses_count": "true",
        })
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "License key not found. Check the key in your receipt email and try again."
        return False, "Could not reach the activation server. Check your internet connection."
    except urllib.error.URLError:
        return False, "Could not reach the activation server. Check your internet connection."
    except Exception:
        logger.exception("Unexpected error during activation")
        return False, "An unexpected error occurred. Contact hello@simdadllc.com."

    if not data.get("success"):
        return False, _friendly_error(data.get("message", ""))

    purchase = data.get("purchase", {})

    if purchase.get("refunded") or purchase.get("chargebacked"):
        return False, "This purchase has been refunded. Contact hello@simdadllc.com for help."

    uses = data.get("uses", 0)
    if uses > MAX_USES:
        return False, (
            f"This key has reached its activation limit ({MAX_USES} devices). "
            "Contact hello@simdadllc.com to reset it."
        )

    _save({
        "license_key":    key,
        "product_name":   purchase.get("product_name", "Lector"),
        "email":          purchase.get("email", ""),
        "uses":           uses,
        "max_uses":       MAX_USES,
        "activated_at":   _now_iso(),
        "last_validated": _now_iso(),
        "machine_id":     _machine_fingerprint(),
    })
    logger.info("License activated: %s", purchase.get("product_name", "Lector"))
    return True, ""


def check() -> tuple[bool, str]:
    """
    Check license validity.
    Returns (valid, reason).

    Reasons when invalid:
      "not_activated"  — no license file
      "revoked"        — refunded/chargebacked
      "grace_expired"  — offline too long
    """
    if _dev_mode():
        logger.info("Dev mode — license check skipped (PRODUCT_ID not set)")
        return True, ""

    saved = _load()
    if not saved:
        return False, "not_activated"

    try:
        data = _post(GUMROAD_VERIFY, {
            "product_id":           PRODUCT_ID,
            "license_key":          saved["license_key"],
            "increment_uses_count": "false",
        })

        if not data.get("success"):
            logger.warning("License invalid per Gumroad: %s", data.get("message"))
            return False, "revoked"

        purchase = data.get("purchase", {})
        if purchase.get("refunded") or purchase.get("chargebacked"):
            logger.warning("License revoked — refunded or chargebacked")
            return False, "revoked"

        saved["last_validated"] = _now_iso()
        _save(saved)
        logger.info("License valid (online)")
        return True, ""

    except urllib.error.URLError:
        logger.info("License validation offline — checking grace period")
        return _grace_check(saved)
    except Exception:
        logger.exception("Unexpected error during license check — applying grace period")
        return _grace_check(saved)


def _grace_check(saved: dict) -> tuple[bool, str]:
    last_str = saved.get("last_validated") or saved.get("activated_at", "")
    if not last_str:
        return False, "not_activated"
    try:
        last = datetime.fromisoformat(last_str)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last <= timedelta(days=GRACE_DAYS):
            logger.info("Offline — grace period active (%d-day window)", GRACE_DAYS)
            return True, ""
    except Exception:
        logger.exception("Failed to parse last_validated timestamp")
    return False, "grace_expired"
