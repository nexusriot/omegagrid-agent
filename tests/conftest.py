"""Pytest configuration for omegagrid-agent unit tests.

Adds the project root to sys.path so tests can `from skills...` and `from core...`
without installing the project as a package.
"""
import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
