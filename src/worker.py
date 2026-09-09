"""Enforcer worker. Run once per tick by the SYSTEM scheduled task.

Reconciles desired block state (command > state > schedule) against the
hosts file and re-applies if drift is detected.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, time as dtime, timedelta
from logging.handlers import RotatingFileHandler

from config import (
    LOG_PATH,
    OVERRIDE_DURATION_MINUTES,
    clear_command,
    ensure_install_dir,
    load_blocklist,
    load_command,
    load_schedule,
    load_state,
    save_state,
)
from hosts_edit import apply_block, has_block, remove_block

log = logging.getLogger("worker")


def _setup_logging() -> None:
    ensure_install_dir()
    handler = RotatingFileHandler(
        LOG_PATH, maxBytes=512_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def _compute_active_window_end(schedule: dict, now: datetime) -> datetime | None:
    """If any schedule window covers `now`, return the latest end datetime
    among all covering windows. Otherwise None.

    Only same-day windows are considered (start <= end). Overnight windows
    are not supported in this version.
    """
    windows = schedule.get("windows") or []
    weekday = now.weekday()
    current = dtime(now.hour, now.minute)
    latest_end: datetime | None = None
    for w in windows:
        days = w.get("days") or []
        if weekday not in days:
            continue
        try:
            start_h, start_m = (int(x) for x in w["start"].split(":"))
            end_h, end_m = (int(x) for x in w["end"].split(":"))
        except (KeyError, ValueError):
            continue
        start = dtime(start_h, start_m)
        end = dtime(end_h, end_m)
        if start <= end and start <= current < end:
            candidate = datetime.combine(now.date(), end)
            if latest_end is None or candidate > latest_end:
                latest_end = candidate
    return latest_end


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _apply_command(cmd: dict, state: dict, now: datetime) -> dict:
    action = cmd.get("action")
    if action == "block_until":
        end = _parse_iso(cmd.get("until"))
        if end and end > now:
            if state.get("mode") == "block_until":
                current_end = _parse_iso(state.get("end_time"))
                if current_end and current_end > end:
                    log.info(
                        "Command ignored: block_until %s is shorter than current %s",
                        end.isoformat(),
                        current_end.isoformat(),
                    )
                    return state
            state = dict(state)
            state["mode"] = "block_until"
            state["end_time"] = end.isoformat()
            log.info("Command: block_until %s", end.isoformat())
    elif action == "unblock":
        override_end = now + timedelta(minutes=OVERRIDE_DURATION_MINUTES)
        existing = _parse_iso(state.get("override_until"))
        if existing and existing > override_end:
            log.info(
                "Command ignored: override already active until %s",
                existing.isoformat(),
            )
            return state
        state = dict(state)
        state["override_until"] = override_end.isoformat()
        log.info(
            "Command: override until %s (%d min)",
            override_end.isoformat(),
            OVERRIDE_DURATION_MINUTES,
        )
    elif action == "reload":
        log.info("Command: reload")
    return state


def _desired_block(state: dict, now: datetime) -> bool:
    override_until = _parse_iso(state.get("override_until"))
    if override_until and override_until > now:
        return False
    mode = state.get("mode")
    if mode == "block_until":
        end = _parse_iso(state.get("end_time"))
        if end and end > now:
            return True
    locked = _parse_iso(state.get("schedule_locked_until"))
    if locked and locked > now:
        return True
    return False


def _underlying_block_active(state: dict, now: datetime) -> bool:
    """Return whether a block is active, ignoring a temporary override."""
    mode = state.get("mode")
    if mode == "block_until":
        end = _parse_iso(state.get("end_time"))
        if end and end > now:
            return True
    locked = _parse_iso(state.get("schedule_locked_until"))
    return bool(locked and locked > now)


def _locked_blocklist(state: dict, blocklist: list[str]) -> tuple[list[str], bool]:
    """Keep the active blocklist monotonic for the life of a block.

    Current-list additions take effect immediately, while removals are deferred
    until no timed or scheduled block remains active.
    """
    saved = state.get("active_blocklist")
    if not isinstance(saved, list):
        saved = []

    merged: list[str] = []
    seen: set[str] = set()
    for domain in [*saved, *blocklist]:
        if not isinstance(domain, str) or domain in seen:
            continue
        seen.add(domain)
        merged.append(domain)

    changed = state.get("active_blocklist") != merged
    if changed:
        state["active_blocklist"] = merged
    return merged, changed


def tick() -> None:
    now = datetime.now()
    state = load_state()
    schedule = load_schedule()
    blocklist = load_blocklist()

    cmd = load_command()
    if cmd is not None:
        state = _apply_command(cmd, state, now)
        save_state(state)
        clear_command()

    dirty = False

    if state.get("mode") == "block_until":
        end = _parse_iso(state.get("end_time"))
        if end and end <= now:
            state["mode"] = "inactive"
            state["end_time"] = None
            dirty = True
            log.info("Timed block expired")

    override_until = _parse_iso(state.get("override_until"))
    if override_until and override_until <= now:
        state["override_until"] = None
        dirty = True
        log.info("Override expired")

    active_end = _compute_active_window_end(schedule, now)
    if active_end is not None:
        current_lock = _parse_iso(state.get("schedule_locked_until"))
        if current_lock is None or active_end > current_lock:
            state["schedule_locked_until"] = active_end.isoformat()
            dirty = True
            log.info("Schedule lock set to %s", active_end.isoformat())

    locked_until = _parse_iso(state.get("schedule_locked_until"))
    if locked_until and locked_until <= now:
        state["schedule_locked_until"] = None
        dirty = True
        log.info("Schedule lock cleared")

    underlying_block = _underlying_block_active(state, now)
    if underlying_block:
        effective_blocklist, snapshot_changed = _locked_blocklist(state, blocklist)
        dirty = dirty or snapshot_changed
    else:
        effective_blocklist = blocklist
        if state.get("active_blocklist") is not None:
            state["active_blocklist"] = None
            dirty = True

    if dirty:
        save_state(state)

    should_block = _desired_block(state, now)
    currently_blocked = has_block()

    if should_block and not currently_blocked:
        log.info("Applying block (%d domains)", len(effective_blocklist))
        apply_block(effective_blocklist)
    elif should_block and currently_blocked:
        apply_block(effective_blocklist)
    elif not should_block and currently_blocked:
        log.info("Removing block")
        remove_block()


def run_loop(interval_seconds: float = 2.0) -> None:
    """Persistent worker loop. Polls command/state/schedule; reconciles hosts."""
    log.info("Worker loop started (interval=%.1fs)", interval_seconds)
    while True:
        try:
            tick()
        except Exception:
            log.exception("tick failed")
        time.sleep(interval_seconds)


def main() -> int:
    _setup_logging()
    try:
        if "--tick" in sys.argv:
            tick()
        else:
            run_loop()
    except Exception:
        log.exception("worker failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
