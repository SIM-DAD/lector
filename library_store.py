"""Lector encrypted document library.

The library is a directory of `.age` files. Each saved document becomes
`{slug}.txt.age` in `library/`. Display name is reverse-derived from the
slug for v1 (no sidecar metadata file, no leak surface beyond filename
existence + mtime).

Save flow:
    plaintext text in memory
        -> write to scratch_dir/{slug}.txt
        -> simdad_crypto.encrypt_file (produces scratch_dir/{slug}.txt.age)
        -> move {slug}.txt.age into library/
        -> delete plaintext from scratch_dir

Load flow:
    library/{slug}.txt.age
        -> copy bytes to scratch_dir/{slug}.txt.age
        -> simdad_crypto.decrypt_file (produces scratch_dir/{slug}.txt)
        -> read text into memory
        -> delete both scratch files

Crash hygiene: a crash mid-flow can leak files in scratch_dir.
`cleanup_scratch_dir()` runs on every Lector startup to mop up. The
visible library/ folder is touched only with ciphertext.
"""

from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import crypto

logger = logging.getLogger(__name__)

LIBRARY_SUFFIX = ".txt.age"
SCRATCH_SUBDIR = ".tmp"
MAX_SLUG_LEN = 80


def _slugify(name: str) -> str:
    """Turn a display name into a filesystem-safe lowercase slug.

    "Q1 Report — Final Draft 2026" -> "q1-report-final-draft-2026"
    """
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:MAX_SLUG_LEN] or "untitled"


def _display_name_from_slug(slug: str) -> str:
    """Reverse-derive a display name from a slug for the list view.

    Slug "q1-report-final-draft-2026" -> "Q1 Report Final Draft 2026"
    """
    return slug.replace("-", " ").title()


def _unique_slug(library_dir: Path, base_slug: str) -> str:
    """Return base_slug if free, else base_slug-2, -3, ... until free."""
    if not (library_dir / f"{base_slug}{LIBRARY_SUFFIX}").exists():
        return base_slug
    n = 2
    while (library_dir / f"{base_slug}-{n}{LIBRARY_SUFFIX}").exists():
        n += 1
    return f"{base_slug}-{n}"


def list_documents(library_dir: Path) -> list[dict]:
    """Return [{id, name, modified}] for every encrypted document in library_dir.

    Sorted newest-first by mtime. Pure filesystem read — no decryption,
    no keystore touch. Safe to call before the keystore bootstraps.
    """
    if not library_dir.exists():
        return []
    docs = []
    for f in library_dir.iterdir():
        if not f.is_file() or not f.name.endswith(LIBRARY_SUFFIX):
            continue
        slug = f.name[: -len(LIBRARY_SUFFIX)]
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()
        docs.append(
            {
                "id": slug,
                "name": _display_name_from_slug(slug),
                "modified": mtime,
            }
        )
    docs.sort(key=lambda d: d["modified"], reverse=True)
    return docs


def save_document(library_dir: Path, name: str, content: str) -> dict:
    """Encrypt `content` to `library/{slug}.txt.age`. Return doc metadata.

    On slug collision, appends -2, -3, etc. The display name passed in
    is preserved insofar as the slug captures it; the returned `name`
    field reflects what the list view will show.
    """
    library_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir = library_dir / SCRATCH_SUBDIR
    scratch_dir.mkdir(parents=True, exist_ok=True)

    base_slug = _slugify(name)
    slug = _unique_slug(library_dir, base_slug)

    scratch_plain = scratch_dir / f"{slug}.txt"
    scratch_plain.write_text(content, encoding="utf-8")

    try:
        ciphertext_in_scratch = crypto.encrypt_path_in_place(scratch_plain)
        final_path = library_dir / ciphertext_in_scratch.name
        if final_path.exists():
            # Collision check happened above, but a concurrent save could
            # squeeze in. Refuse rather than overwrite a real document.
            try:
                ciphertext_in_scratch.unlink()
            except OSError:
                pass
            raise FileExistsError(f"library file appeared during save: {final_path.name}")
        shutil.move(str(ciphertext_in_scratch), str(final_path))
    except Exception:
        # Best-effort cleanup of any plaintext or ciphertext leftover in scratch.
        for stray in (scratch_plain, scratch_dir / f"{slug}.txt.age"):
            if stray.exists():
                try:
                    stray.unlink()
                except OSError:
                    pass
        raise

    mtime = datetime.fromtimestamp(final_path.stat().st_mtime, tz=timezone.utc).isoformat()
    logger.info("Saved encrypted document: %s", final_path.name)
    return {
        "id": slug,
        "name": _display_name_from_slug(slug),
        "modified": mtime,
    }


def load_document(library_dir: Path, doc_id: str) -> dict:
    """Decrypt `library/{doc_id}.txt.age` and return {id, name, content, modified}.

    Raises FileNotFoundError if doc_id has no corresponding ciphertext.
    Raises crypto.DecryptionError if the ciphertext is unreadable.
    """
    age_path = library_dir / f"{doc_id}{LIBRARY_SUFFIX}"
    if not age_path.exists():
        raise FileNotFoundError(f"document not found: {doc_id}")
    scratch_dir = library_dir / SCRATCH_SUBDIR
    text = crypto.decrypt_to_text(age_path, scratch_dir)
    mtime = datetime.fromtimestamp(age_path.stat().st_mtime, tz=timezone.utc).isoformat()
    return {
        "id": doc_id,
        "name": _display_name_from_slug(doc_id),
        "content": text,
        "modified": mtime,
    }


def delete_document(library_dir: Path, doc_id: str) -> None:
    """Remove `library/{doc_id}.txt.age`. Silent if it does not exist."""
    age_path = library_dir / f"{doc_id}{LIBRARY_SUFFIX}"
    age_path.unlink(missing_ok=True)
    logger.info("Deleted encrypted document: %s", age_path.name)


def cleanup_scratch_dir(library_dir: Path) -> int:
    """Mop up any plaintext or ciphertext leftover from a crashed save/load."""
    return crypto.cleanup_scratch_dir(library_dir / SCRATCH_SUBDIR)
