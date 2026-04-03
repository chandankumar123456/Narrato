"""Tests for the FastAPI API endpoints."""
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import app
from services.job_store import set_job, get_job


client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "redis" in data
    assert "celery" in data


def test_generate_empty_prompt():
    resp = client.post("/generate", json={"prompt": ""})
    assert resp.status_code == 400


def test_generate_long_prompt():
    resp = client.post("/generate", json={"prompt": "x" * 5001})
    assert resp.status_code == 400


def test_status_not_found():
    resp = client.get("/status/nonexistent-job-id")
    assert resp.status_code == 404


def test_download_not_found():
    resp = client.get("/download/nonexistent-job-id")
    assert resp.status_code == 404


def test_status_returns_job():
    set_job("test-api-1", status="processing", progress=50)
    resp = client.get("/status/test-api-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processing"
    assert data["progress"] == 50


def test_preview_not_completed():
    set_job("test-api-2", status="processing", progress=50)
    resp = client.post("/preview/test-api-2")
    assert resp.status_code == 404
