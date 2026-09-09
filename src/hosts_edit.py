"""Read/write the hosts-file marker block and flush DNS."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from config import HOSTS_PATH, MARKER_END, MARKER_START, SUBDOMAIN_PREFIXES

CREATE_NO_WINDOW = 0x08000000


def _read_hosts() -> str:
    try:
        return HOSTS_PATH.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return HOSTS_PATH.read_text(encoding="mbcs")


def _write_hosts(content: str) -> None:
    fd, tmp = tempfile.mkstemp(
        prefix="hosts.", suffix=".tmp", dir=str(HOSTS_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(content)
        os.replace(tmp, HOSTS_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _strip_block(content: str) -> str:
    lines = content.splitlines()
    out: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped == MARKER_START:
            skipping = True
            continue
        if stripped == MARKER_END:
            skipping = False
            continue
        if not skipping:
            out.append(line)
    while out and out[-1].strip() == "":
        out.pop()
    return "\n".join(out) + "\n"


def _build_block(domains: list[str]) -> str:
    lines = [MARKER_START]
    for domain in domains:
        domain = domain.strip().lower()
        if not domain:
            continue
        if domain.startswith("www."):
            domain = domain[4:]
        for prefix in SUBDOMAIN_PREFIXES:
            lines.append(f"127.0.0.1 {prefix}{domain}")
            lines.append(f"::1 {prefix}{domain}")
    lines.append(MARKER_END)
    return "\n".join(lines) + "\n"


def apply_block(domains: list[str]) -> bool:
    """Write the block for the given domains. Returns True if hosts changed."""
    current = _read_hosts()
    base = _strip_block(current)
    desired = base.rstrip() + "\n\n" + _build_block(domains)
    if desired == current:
        return False
    _write_hosts(desired)
    flush_dns()
    return True


def remove_block() -> bool:
    """Strip the block. Returns True if hosts changed."""
    current = _read_hosts()
    stripped = _strip_block(current)
    if stripped == current:
        return False
    _write_hosts(stripped)
    flush_dns()
    return True


def has_block() -> bool:
    try:
        return MARKER_START in _read_hosts()
    except FileNotFoundError:
        return False


def flush_dns() -> None:
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            creationflags=CREATE_NO_WINDOW,
            capture_output=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        pass
