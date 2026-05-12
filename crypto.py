"""Lector-side crypto helpers wrapping simdad_crypto + pyrage.

Mirrors ibis/crypto.py. Bootstraps an X25519 keypair on first run, caches
the recipient (public key) at module level, and provides encrypt/decrypt
helpers used by the document library store.

Threat model boundaries are documented in:
  E:\\Projects\\SIM-DAD\\simdad-crypto\\README.md  (sections 1, 4)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pyrage
import pyrage.x25519
import simdad_crypto
from simdad_crypto.errors import (
    DecryptionError,
    KeyNotFoundError,
    KeystoreUnavailableError,
)

logger = logging.getLogger(__name__)

# Account name in the OS keystore. Service name is hard-coded inside
# simdad_crypto as "simdad-crypto"; this is the per-product/per-purpose half.
KEY_NAME = "lector.library"

_recipient_cache: str | None = None

# Re-export for callers that want to catch crypto errors without importing
# simdad_crypto directly.
KeyNotFoundError = KeyNotFoundError
KeystoreUnavailableError = KeystoreUnavailableError
DecryptionError = DecryptionError


def get_recipient() -> str:
    """Return the cached `age1...` public key for encrypting Lector documents.

    On first call (or first run on a fresh machine), generates a new X25519
    keypair, stores the secret in the OS keystore, and caches the public
    half. Subsequent calls return the cache.

    Raises KeystoreUnavailableError if the OS keystore is unreachable.
    """
    global _recipient_cache
    if _recipient_cache is not None:
        return _recipient_cache

    try:
        secret_bytes = simdad_crypto.retrieve_key(KEY_NAME)
        identity = pyrage.x25519.Identity.from_str(secret_bytes.decode("utf-8"))
        _recipient_cache = str(identity.to_public())
        logger.info("Loaded existing Lector encryption key from OS keystore")
        return _recipient_cache
    except KeyNotFoundError:
        identity = pyrage.x25519.Identity.generate()
        simdad_crypto.store_key(KEY_NAME, str(identity).encode("utf-8"))
        _recipient_cache = str(identity.to_public())
        logger.info(
            "Generated new Lector encryption keypair (stored in OS keystore as "
            "'simdad-crypto' / '%s'). Loss of OS profile = loss of this key. "
            "Save the editor draft to a plaintext .md export before any OS reinstall.",
            KEY_NAME,
        )
        return _recipient_cache


def get_identity() -> str:
    """Return the `AGE-SECRET-KEY-1...` private key string for decryption.

    Not cached deliberately: keystore reads are cheap and limiting how long
    the secret string sits in memory is cheap defense in depth (per
    simdad-crypto README §1).
    """
    secret_bytes = simdad_crypto.retrieve_key(KEY_NAME)
    return secret_bytes.decode("utf-8")


def encrypt_path_in_place(plaintext_path: Path) -> Path:
    """Encrypt `plaintext_path` to `plaintext_path.suffix + '.age'` and remove plaintext.

    Returns the new ciphertext path. Used by save_document via the library
    store's temp-file dance. The caller is responsible for ensuring
    plaintext_path lives in a private temp dir, not in user-visible storage.
    """
    recipient = get_recipient()
    encrypted = simdad_crypto.encrypt_file(plaintext_path, recipient=recipient)
    plaintext_path.unlink()
    return encrypted


def decrypt_to_text(age_path: Path, scratch_dir: Path) -> str:
    """Decrypt an `.age` document file and return its UTF-8 text contents.

    Copies the ciphertext into scratch_dir, decrypts (producing a plaintext
    file there), reads the text, and removes both temp files before
    returning. The library/ directory itself is never touched with
    plaintext.

    Raises DecryptionError if the file cannot be decrypted (wrong key,
    tampered file, malformed ciphertext).
    """
    if age_path.suffix != ".age":
        raise ValueError(f"expected .age file; got {age_path.name}")

    scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch_cipher = scratch_dir / age_path.name
    scratch_plain = scratch_dir / age_path.with_suffix("").name

    scratch_cipher.write_bytes(age_path.read_bytes())

    identity = get_identity()
    try:
        decrypted_path = simdad_crypto.decrypt_file(
            scratch_cipher, identity=identity, overwrite=True
        )
        text = decrypted_path.read_text(encoding="utf-8")
        return text
    finally:
        for f in (scratch_cipher, scratch_plain):
            try:
                f.unlink()
            except OSError:
                pass


def cleanup_scratch_dir(scratch_dir: Path) -> int:
    """Remove any leaked plaintext or ciphertext files in scratch_dir.

    Called on Lector startup to mop up after crashes mid-save or mid-load.
    Returns the number of files removed.
    """
    if not scratch_dir.exists():
        return 0
    removed = 0
    for f in scratch_dir.iterdir():
        try:
            f.unlink()
            removed += 1
        except OSError as e:
            logger.warning("Could not delete leftover %s: %s", f, e)
    if removed:
        logger.info("Cleaned %d leftover files from %s", removed, scratch_dir)
    return removed
