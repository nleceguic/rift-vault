"""Reusable animation helpers for CTk windows."""


def dialog_fade_in(
    toplevel,
    delay_ms:    int = 55,
    steps:       int = 8,
    interval_ms: int = 14,
    y_offset:    int = 10,
):
    """
    Fade-in + upward float for a CTkToplevel dialog.
    Call at the end of __init__, after centering is scheduled.
    delay_ms should exceed the centering delay (typically 50 ms).
    """
    try:
        toplevel.attributes("-alpha", 0.0)
    except Exception:
        return

    def _start():
        if not toplevel.winfo_exists():
            return
        try:
            toplevel.update_idletasks()
            x     = toplevel.winfo_x()
            y_end = toplevel.winfo_y()
            toplevel.geometry(f"+{x}+{y_end + y_offset}")
            _step(1, x, y_end)
        except Exception:
            pass

    def _step(i: int, x: int, y_end: int):
        if not toplevel.winfo_exists():
            return
        try:
            t    = i / steps
            ease = 1.0 - (1.0 - t) ** 2         # quadratic ease-out
            toplevel.attributes("-alpha", t)
            toplevel.geometry(f"+{x}+{y_end + round(y_offset * (1.0 - ease))}")
            if i < steps:
                toplevel.after(interval_ms, lambda: _step(i + 1, x, y_end))
        except Exception:
            pass

    toplevel.after(delay_ms, _start)
