"""
Narrato — AI-powered presentation generation engine.

Start the API server:
    cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Start the Celery worker (optional, for production async):
    cd backend && uv run celery -A worker.celery_app worker --loglevel=info

Start the frontend dev server:
    cd frontend && npm run dev
"""

import subprocess
import sys


def main():
    print("Starting Narrato API server...")
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd="backend",
    )


if __name__ == "__main__":
    main()