"""Ensure the backend directory is importable as the `app` package during tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
