import sys


def ensure_stdout_utf8():
    """Make stdout/stderr tolerate the emoji this app prints everywhere.

    On a Windows console whose codepage isn't UTF-8 (cp1252/850 are common
    non-English-locale defaults, and this is the case with no PYTHONIOENCODING
    set), print()-ing an emoji raises UnicodeEncodeError and crashes whatever
    was running. errors="replace" means a character neither UTF-8 nor the
    original encoding could show still prints as-is instead of crashing.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
