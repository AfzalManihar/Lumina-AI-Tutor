"""Shared helpers for utility scripts: put backend/ on sys.path and load backend/.env settings."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
