"""Click-the-dot override window. Focus-tracked, misclick-reset."""
from __future__ import annotations

import random
import tkinter as tk
from typing import Callable

DOT_RADIUS = 18
TARGET_CLICKS = 100
RESPAWN_MIN_MS = 300
RESPAWN_MAX_MS = 800
BG = "#101010"
DOT_COLOR = "#ffffff"
TEXT_COLOR = "#dddddd"
RESET_COLOR = "#ff5050"


class OverrideWindow:
    def __init__(self, master: tk.Misc, on_success: Callable[[], None]):
        self.on_success = on_success
        self.count = 0
        self.dot_id: int | None = None
        self.dot_x = 0
        self.dot_y = 0
        self._pending_respawn: str | None = None
        self._reset_flash_after: str | None = None

        self.top = tk.Toplevel(master)
        self.top.title("Unblock Task")
        self.top.configure(bg=BG)
        self.top.geometry("900x650")
        self.top.minsize(600, 450)
        self.top.protocol("WM_DELETE_WINDOW", self._on_close)

        self.canvas = tk.Canvas(
            self.top, bg=BG, highlightthickness=0, cursor="crosshair"
        )
        self.canvas.pack(fill="both", expand=True)

        self.status = tk.Label(
            self.top,
            text=self._status_text(),
            bg=BG,
            fg=TEXT_COLOR,
            font=("Segoe UI", 14),
        )
        self.status.pack(side="bottom", fill="x", pady=6)

        self.canvas.bind("<Button-1>", self._on_click)
        self.top.bind("<FocusOut>", self._on_focus_out)
        self.top.bind("<Configure>", self._on_resize)

        self.top.after(200, self._spawn_dot)
        self.top.focus_force()

    def _status_text(self, note: str = "") -> str:
        base = f"{self.count} / {TARGET_CLICKS} — misclick or losing focus resets you."
        return f"{base}   {note}" if note else base

    def _set_status(self, note: str = "", color: str = TEXT_COLOR) -> None:
        self.status.configure(text=self._status_text(note), fg=color)

    def _spawn_dot(self) -> None:
        self._pending_respawn = None
        self.canvas.delete("dot")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 2 * DOT_RADIUS + 20 or h < 2 * DOT_RADIUS + 20:
            self.top.after(100, self._spawn_dot)
            return
        self.dot_x = random.randint(DOT_RADIUS + 10, w - DOT_RADIUS - 10)
        self.dot_y = random.randint(DOT_RADIUS + 10, h - DOT_RADIUS - 10)
        self.dot_id = self.canvas.create_oval(
            self.dot_x - DOT_RADIUS,
            self.dot_y - DOT_RADIUS,
            self.dot_x + DOT_RADIUS,
            self.dot_y + DOT_RADIUS,
            fill=DOT_COLOR,
            outline="",
            tags=("dot",),
        )

    def _on_click(self, event: tk.Event) -> None:
        if self.dot_id is None:
            return
        dx = event.x - self.dot_x
        dy = event.y - self.dot_y
        if dx * dx + dy * dy <= DOT_RADIUS * DOT_RADIUS:
            self.count += 1
            self.canvas.delete("dot")
            self.dot_id = None
            if self.count >= TARGET_CLICKS:
                self._set_status("Done.", TEXT_COLOR)
                self.top.after(150, self._succeed)
                return
            self._set_status()
            delay = random.randint(RESPAWN_MIN_MS, RESPAWN_MAX_MS)
            self._pending_respawn = self.top.after(delay, self._spawn_dot)
        else:
            self._reset("missed")

    def _on_focus_out(self, _event: tk.Event) -> None:
        if self.count > 0:
            self._reset("focus lost")

    def _on_resize(self, _event: tk.Event) -> None:
        pass

    def _reset(self, reason: str) -> None:
        self.count = 0
        if self._pending_respawn is not None:
            self.top.after_cancel(self._pending_respawn)
            self._pending_respawn = None
        self.canvas.delete("dot")
        self.dot_id = None
        self._set_status(f"reset — {reason}", RESET_COLOR)
        if self._reset_flash_after is not None:
            self.top.after_cancel(self._reset_flash_after)
        self._reset_flash_after = self.top.after(
            900, lambda: self._set_status()
        )
        self.top.after(400, self._spawn_dot)

    def _succeed(self) -> None:
        try:
            self.on_success()
        finally:
            self._on_close()

    def _on_close(self) -> None:
        if self._pending_respawn is not None:
            try:
                self.top.after_cancel(self._pending_respawn)
            except Exception:
                pass
        try:
            self.top.destroy()
        except Exception:
            pass
