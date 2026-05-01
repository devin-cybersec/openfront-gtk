#!/usr/bin/env python3
"""Standalone launcher — runnable without installing the package.

Just `chmod +x openfront-gtk` and `./openfront-gtk` from a clone.
"""
import os
import sys

# Make the local package importable when running from a clone.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from openfront_gtk.app import main

if __name__ == "__main__":
    sys.exit(main())
