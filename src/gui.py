"""Distraction Blocker GUI. Tkinter. Runs as regular user, no UAC."""
from __future__ import annotations

import sys
import tkinter as tk
from datetime import datetime, time as dtime, timedelta
from tkinter import messagebox, ttk

from config import (
    OVERRIDE_DURATION_MINUTES,
    ensure_config_dir,
    load_blocklist,
    load_schedule,
    load_state,
    save_blocklist,
    save_schedule,
    write_command,
)
from override import OverrideWindow

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _parse_hhmm(s: str) -> dtime | None:
    try:
        h, m = s.split(":")
        return dtime(int(h), int(m))
    except (ValueError, AttributeError):
        return None


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Distraction Blocker")
        root.geometry("640x520")
        root.minsize(560, 460)

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_status_tab()
        self._build_block_now_tab()
        self._build_schedule_tab()
        self._build_blocklist_tab()

        self._refresh_status()
        self.root.after(5000, self._auto_refresh)

    # ---------- Status tab ----------
    def _build_status_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text="Status")

        self.status_label = ttk.Label(
            frame, text="", font=("Segoe UI", 13, "bold")
        )
        self.status_label.pack(anchor="w", pady=(0, 8))

        self.detail_label = ttk.Label(frame, text="", font=("Segoe UI", 10))
        self.detail_label.pack(anchor="w", pady=(0, 16))

        ttk.Separator(frame).pack(fill="x", pady=10)

        unblock_btn = ttk.Button(
            frame,
            text="Unblock Early (override task)",
            command=self._open_override,
        )
        unblock_btn.pack(anchor="w", pady=4)

        refresh_btn = ttk.Button(
            frame, text="Refresh", command=self._refresh_status
        )
        refresh_btn.pack(anchor="w", pady=4)

    def _refresh_status(self) -> None:
        state = load_state()
        schedule = load_schedule()
        now = datetime.now()

        override_end = _parse_iso(state.get("override_until"))
        block_end = _parse_iso(state.get("end_time")) if state.get("mode") == "block_until" else None
        lock_end = _parse_iso(state.get("schedule_locked_until"))

        underlying_end: datetime | None = None
        underlying_reason = ""
        if block_end and block_end > now:
            underlying_end = block_end
            underlying_reason = "Blocked until"
        if lock_end and lock_end > now:
            if underlying_end is None or lock_end > underlying_end:
                underlying_end = lock_end
                underlying_reason = "Scheduled block until"

        if override_end and override_end > now:
            remaining = override_end - now
            mins, secs = divmod(int(remaining.total_seconds()), 60)
            self.status_label.configure(
                text="◐ OVERRIDE", foreground="#e67e22"
            )
            resume_note = (
                f" — resumes at {underlying_end.strftime('%H:%M')}"
                if underlying_end
                else ""
            )
            self.detail_label.configure(
                text=f"Unblocked for {mins}:{secs:02d}{resume_note}"
            )
            return

        if underlying_end is not None:
            self.status_label.configure(
                text="● BLOCKED", foreground="#c0392b"
            )
            self.detail_label.configure(
                text=f"{underlying_reason} {underlying_end.strftime('%H:%M on %a %d %b')}"
            )
        else:
            self.status_label.configure(
                text="○ not blocked", foreground="#27ae60"
            )
            next_win = self._next_schedule_window(schedule, now)
            self.detail_label.configure(
                text=f"Next scheduled window: {next_win}"
                if next_win
                else "No upcoming scheduled windows."
            )

    def _auto_refresh(self) -> None:
        self._refresh_status()
        state = load_state()
        override_end = _parse_iso(state.get("override_until"))
        now = datetime.now()
        interval = 1000 if (override_end and override_end > now) else 5000
        self.root.after(interval, self._auto_refresh)

    @staticmethod
    def _schedule_active(schedule: dict, now: datetime) -> bool:
        weekday = now.weekday()
        current = dtime(now.hour, now.minute)
        for w in schedule.get("windows", []):
            if weekday not in (w.get("days") or []):
                continue
            start = _parse_hhmm(w.get("start", ""))
            end = _parse_hhmm(w.get("end", ""))
            if not start or not end:
                continue
            if start <= end:
                if start <= current < end:
                    return True
            else:
                if current >= start or current < end:
                    return True
        return False

    @staticmethod
    def _next_schedule_window(schedule: dict, now: datetime) -> str | None:
        windows = schedule.get("windows") or []
        if not windows:
            return None
        best: tuple[datetime, dict] | None = None
        for offset in range(0, 8):
            day = (now + timedelta(days=offset)).date()
            weekday = (now.weekday() + offset) % 7
            for w in windows:
                if weekday not in (w.get("days") or []):
                    continue
                start = _parse_hhmm(w.get("start", ""))
                if not start:
                    continue
                candidate = datetime.combine(day, start)
                if candidate <= now:
                    continue
                if best is None or candidate < best[0]:
                    best = (candidate, w)
        if not best:
            return None
        dt, w = best
        return f"{dt.strftime('%a %d %b %H:%M')}–{w.get('end', '')}"

    # ---------- Block Now tab ----------
    def _build_block_now_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text="Block Now")

        ttk.Label(
            frame,
            text="Start a one-shot block. Closes when time expires.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 12))

        preset_frame = ttk.Frame(frame)
        preset_frame.pack(anchor="w", pady=4)
        for label, mins in [
            ("30 min", 30),
            ("1 hour", 60),
            ("2 hours", 120),
            ("4 hours", 240),
            ("Until 6pm", -1),
        ]:
            ttk.Button(
                preset_frame,
                text=label,
                command=lambda m=mins: self._block_for(m),
            ).pack(side="left", padx=4)

        ttk.Separator(frame).pack(fill="x", pady=14)

        custom_frame = ttk.Frame(frame)
        custom_frame.pack(anchor="w")
        ttk.Label(custom_frame, text="Custom minutes:").pack(
            side="left", padx=(0, 6)
        )
        self.custom_mins = tk.StringVar(value="90")
        ttk.Entry(custom_frame, textvariable=self.custom_mins, width=8).pack(
            side="left"
        )
        ttk.Button(
            custom_frame,
            text="Block",
            command=lambda: self._block_for(self._custom_minutes()),
        ).pack(side="left", padx=8)

    def _custom_minutes(self) -> int:
        try:
            return max(1, int(self.custom_mins.get()))
        except ValueError:
            return 0

    def _block_for(self, minutes: int) -> None:
        now = datetime.now()
        if minutes == -1:
            end = now.replace(hour=18, minute=0, second=0, microsecond=0)
            if end <= now:
                end = end + timedelta(days=1)
        elif minutes <= 0:
            messagebox.showerror("Invalid duration", "Enter a positive number of minutes.")
            return
        else:
            end = now + timedelta(minutes=minutes)

        state = load_state()
        if state.get("mode") == "block_until":
            try:
                current_end = datetime.fromisoformat(state.get("end_time") or "")
            except ValueError:
                current_end = None
            if current_end and current_end > now and current_end > end:
                messagebox.showinfo(
                    "Already blocked",
                    f"Already blocked until {current_end.strftime('%H:%M on %a %d %b')}. "
                    "Keeping the longer block.",
                )
                self._refresh_status()
                return

        write_command(
            {
                "action": "block_until",
                "until": end.isoformat(),
                "issued_at": now.isoformat(),
            }
        )
        messagebox.showinfo(
            "Blocked",
            f"Block applied until {end.strftime('%H:%M on %a %d %b')}.",
        )
        self._refresh_status()

    # ---------- Schedule tab ----------
    def _build_schedule_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text="Schedule")

        ttk.Label(
            frame,
            text="Recurring weekly block windows.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 8))

        self.schedule_tree = ttk.Treeview(
            frame,
            columns=("days", "start", "end"),
            show="headings",
            height=8,
        )
        self.schedule_tree.heading("days", text="Days")
        self.schedule_tree.heading("start", text="Start")
        self.schedule_tree.heading("end", text="End")
        self.schedule_tree.column("days", width=200)
        self.schedule_tree.column("start", width=80, anchor="center")
        self.schedule_tree.column("end", width=80, anchor="center")
        self.schedule_tree.pack(fill="both", expand=True, pady=6)

        form = ttk.LabelFrame(frame, text="Add window", padding=8)
        form.pack(fill="x", pady=8)

        self.day_vars: list[tk.IntVar] = []
        day_row = ttk.Frame(form)
        day_row.pack(anchor="w", pady=2)
        for i, name in enumerate(WEEKDAY_NAMES):
            v = tk.IntVar(value=1 if i < 5 else 0)
            self.day_vars.append(v)
            ttk.Checkbutton(day_row, text=name, variable=v).pack(side="left")

        time_row = ttk.Frame(form)
        time_row.pack(anchor="w", pady=4)
        ttk.Label(time_row, text="Start (HH:MM):").pack(side="left")
        self.start_var = tk.StringVar(value="09:00")
        ttk.Entry(time_row, textvariable=self.start_var, width=8).pack(
            side="left", padx=(4, 12)
        )
        ttk.Label(time_row, text="End (HH:MM):").pack(side="left")
        self.end_var = tk.StringVar(value="17:00")
        ttk.Entry(time_row, textvariable=self.end_var, width=8).pack(
            side="left", padx=4
        )

        btns = ttk.Frame(form)
        btns.pack(anchor="w", pady=6)
        ttk.Button(btns, text="Add", command=self._add_schedule_window).pack(
            side="left", padx=2
        )
        ttk.Button(
            btns, text="Remove Selected", command=self._remove_schedule_window
        ).pack(side="left", padx=2)

        self._reload_schedule_tree()

    def _reload_schedule_tree(self) -> None:
        for row in self.schedule_tree.get_children():
            self.schedule_tree.delete(row)
        schedule = load_schedule()
        for idx, w in enumerate(schedule.get("windows", [])):
            day_labels = ", ".join(
                WEEKDAY_NAMES[d] for d in sorted(w.get("days", []))
            )
            self.schedule_tree.insert(
                "", "end", iid=str(idx), values=(day_labels, w.get("start"), w.get("end"))
            )

    def _add_schedule_window(self) -> None:
        days = [i for i, v in enumerate(self.day_vars) if v.get() == 1]
        if not days:
            messagebox.showerror("No days", "Select at least one day.")
            return
        if not _parse_hhmm(self.start_var.get()) or not _parse_hhmm(
            self.end_var.get()
        ):
            messagebox.showerror("Bad time", "Use HH:MM format.")
            return
        schedule = load_schedule()
        schedule.setdefault("windows", []).append(
            {
                "days": days,
                "start": self.start_var.get(),
                "end": self.end_var.get(),
            }
        )
        save_schedule(schedule)
        self._reload_schedule_tree()

    def _remove_schedule_window(self) -> None:
        sel = self.schedule_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        schedule = load_schedule()
        windows = schedule.get("windows", [])
        if 0 <= idx < len(windows):
            windows.pop(idx)
            schedule["windows"] = windows
            save_schedule(schedule)
            self._reload_schedule_tree()

    # ---------- Blocklist tab ----------
    def _build_blocklist_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text="Blocklist")

        ttk.Label(
            frame,
            text="Domains to block. Subdomain variants (www, m, old, mobile) are added automatically.",
            font=("Segoe UI", 10),
            wraplength=560,
        ).pack(anchor="w", pady=(0, 8))

        self.domain_list = tk.Listbox(frame, height=12, font=("Consolas", 10))
        self.domain_list.pack(fill="both", expand=True, pady=6)

        add_row = ttk.Frame(frame)
        add_row.pack(fill="x", pady=4)
        self.new_domain = tk.StringVar()
        ttk.Entry(add_row, textvariable=self.new_domain).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(add_row, text="Add", command=self._add_domain).pack(
            side="left", padx=4
        )
        ttk.Button(
            add_row, text="Remove Selected", command=self._remove_domain
        ).pack(side="left", padx=4)

        self._reload_domain_list()

    def _reload_domain_list(self) -> None:
        self.domain_list.delete(0, tk.END)
        for domain in load_blocklist():
            self.domain_list.insert(tk.END, domain)

    def _add_domain(self) -> None:
        d = self.new_domain.get().strip().lower()
        if not d:
            return
        if d.startswith("http://"):
            d = d[7:]
        elif d.startswith("https://"):
            d = d[8:]
        d = d.split("/")[0]
        if d.startswith("www."):
            d = d[4:]
        blocklist = load_blocklist()
        if d in blocklist:
            return
        blocklist.append(d)
        save_blocklist(blocklist)
        self.new_domain.set("")
        self._reload_domain_list()

    def _remove_domain(self) -> None:
        sel = self.domain_list.curselection()
        if not sel:
            return
        blocklist = load_blocklist()
        for idx in reversed(sel):
            if 0 <= idx < len(blocklist):
                blocklist.pop(idx)
        save_blocklist(blocklist)
        self._reload_domain_list()
        state = load_state()
        now = datetime.now()
        block_end = (
            _parse_iso(state.get("end_time"))
            if state.get("mode") == "block_until"
            else None
        )
        lock_end = _parse_iso(state.get("schedule_locked_until"))
        if (block_end and block_end > now) or (lock_end and lock_end > now):
            messagebox.showinfo(
                "Removal deferred",
                "The selected domain will stay blocked until the current block ends.",
            )

    # ---------- Override ----------
    def _open_override(self) -> None:
        OverrideWindow(self.root, on_success=self._complete_unblock)

    def _complete_unblock(self) -> None:
        write_command(
            {
                "action": "unblock",
                "issued_at": datetime.now().isoformat(),
            }
        )
        messagebox.showinfo(
            "Unblocked",
            f"You have {OVERRIDE_DURATION_MINUTES} minutes. The block resumes automatically after that.",
        )
        self._refresh_status()


def main() -> int:
    ensure_config_dir()
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
