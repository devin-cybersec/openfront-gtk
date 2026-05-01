"""Unit tests for the host allowlist."""
import os
import sys

# Allow `python3 tests/test_allowlist.py` from project root without setting
# PYTHONPATH manually.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from openfront_gtk.app import _host_allowed


def test_allowlist():
    cases = [
        # (uri, expected_allowed)
        ("https://openfront.io/", True),
        ("https://www.openfront.io/play", True),
        ("https://api.openfront.io/v1/games", True),
        ("https://discord.com/invite/abc", True),
        ("https://discord.gg/abc", True),
        ("https://github.com/openfrontio/OpenFrontIO", True),
        ("https://accounts.google.com/oauth", True),
        ("https://www.example.com/", False),
        ("https://evil-openfront.io.attacker.com/", False),  # don't be fooled by suffix
        ("https://openfront.io.attacker.com/", False),
        ("about:blank", False),
        ("", False),
        ("not a url", False),
    ]
    failed = 0
    for uri, expected in cases:
        got = _host_allowed(uri)
        ok = "OK" if got == expected else "FAIL"
        if got != expected:
            failed += 1
        print(f"{ok}  _host_allowed({uri!r}) = {got}  (expected {expected})")
    print(f"\n{failed} failure(s)")
    return failed


if __name__ == "__main__":
    import sys
    sys.exit(test_allowlist())
