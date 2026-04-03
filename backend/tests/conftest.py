"""
Tests for the Narrato pipeline and API.

Run with:
    cd backend && uv run pytest tests/ -v
"""
import sys
import os

# Ensure backend is in path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
