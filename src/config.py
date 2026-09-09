"""Shared paths, defaults, and JSON helpers."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

INSTALL_DIR = Path(r"C:\ProgramData\DistractionBlocker")
CONFIG_DIR = INSTALL_DIR / "config"
STATE_DIR = INSTALL_DIR / "state"
BLOCKLIST_PATH = CONFIG_DIR / "blocklist.json"
SCHEDULE_PATH = CONFIG_DIR / "schedule.json"
COMMAND_PATH = CONFIG_DIR / "command.json"
STATE_PATH = STATE_DIR / "state.json"
LOG_PATH = STATE_DIR / "worker.log"

HOSTS_PATH = Path(r"C:\Windows\System32\drivers\etc\hosts")
MARKER_START = "# DISTRACTION_BLOCKER_START"
MARKER_END = "# DISTRACTION_BLOCKER_END"

TASK_NAME = "DistractionBlockerWorker"

DEFAULT_BLOCKLIST = [
    "x.com",
    "twitter.com",
    "reddit.com",
    "youtube.com",
    "instagram.com",
    "tiktok.com",
    "facebook.com",
]

DEFAULT_SCHEDULE = {
    "windows": []
}

DEFAULT_STATE = {
    "mode": "inactive",
    "end_time": None,
    "schedule_locked_until": None,
    "override_until": None,
    # Domains are snapshotted while a timed/scheduled block is active so
    # editing blocklist.json cannot weaken a block that is already underway.
    "active_blocklist": None,
}

OVERRIDE_DURATION_MINUTES = 5

SUBDOMAIN_PREFIXES = ["", "www.", "m.", "old.", "mobile."]


def ensure_install_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_blocklist() -> list[str]:
    data = load_json(BLOCKLIST_PATH, None)
    if data is None:
        save_json(BLOCKLIST_PATH, DEFAULT_BLOCKLIST)
        return list(DEFAULT_BLOCKLIST)
    return list(data)


def save_blocklist(domains: list[str]) -> None:
    save_json(BLOCKLIST_PATH, domains)


def load_schedule() -> dict:
    data = load_json(SCHEDULE_PATH, None)
    if data is None:
        save_json(SCHEDULE_PATH, DEFAULT_SCHEDULE)
        return dict(DEFAULT_SCHEDULE)
    return data


def save_schedule(schedule: dict) -> None:
    save_json(SCHEDULE_PATH, schedule)


def load_state() -> dict:
    data = load_json(STATE_PATH, None)
    if data is None:
        return dict(DEFAULT_STATE)
    return data


def save_state(state: dict) -> None:
    save_json(STATE_PATH, state)


def load_command() -> dict | None:
    return load_json(COMMAND_PATH, None)


def clear_command() -> None:
    try:
        COMMAND_PATH.unlink()
    except FileNotFoundError:
        pass


def write_command(command: dict) -> None:
    save_json(COMMAND_PATH, command)
