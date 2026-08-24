from __future__ import annotations

import socket
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
import uvicorn

from app.core.config import Settings
from app.main import create_app


@pytest.mark.requires_browser
def test_ui_browser_ingest_query_and_delete_flow(tmp_path: Path) -> None:
    playwright_sync_api = pytest.importorskip(
        "playwright.sync_api",
        reason="playwright is not installed; install RegLens with .[browser]",
    )
    corpus_id = f"ui-browser-{uuid4().hex[:10]}"
    corpus_version = "2026-ui-browser"

    with _live_server(tmp_path) as base_url:
        with playwright_sync_api.sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except playwright_sync_api.Error as exc:
                pytest.skip(f"Playwright Chromium is unavailable: {exc}")

            page = browser.new_page(viewport={"width": 1280, "height": 900})
            try:
                page.goto(base_url, wait_until="networkidle")
                page.locator("h1").filter(has_text="RegLens").wait_for()
                page.locator("#health-pill").filter(has_text="ready").wait_for()

                page.locator('#ingest-form input[name="corpus_id"]').fill(corpus_id)
                page.locator('#ingest-form input[name="corpus_name"]').fill(
                    "UI Browser FINRA Rulebook"
                )
                page.locator('#ingest-form input[name="version"]').fill(corpus_version)
                page.locator('#ingest-form button[type="submit"]').click()
                page.locator("#ingest-notice").filter(has_text="Ingested").wait_for()

                page.locator(".select-source").first.click()
                page.locator('#query-form textarea[name="question"]').fill(
                    "How long must records be retained?"
                )
                page.locator('#query-form button[type="submit"]').click()
                page.locator("#query-notice").filter(has_text="Answered with").wait_for()
                page.locator("#citations").filter(has_text="FINRA Rule 1030(b)").wait_for()
                page.locator("#evidence").filter(has_text="six years").wait_for()

                page.locator("#verify-audit").click()
                page.locator("#query-notice").filter(has_text="Audit records: 1").wait_for()

                page.locator(".delete-source").first.click()
                page.locator("#source-list").filter(has_text="No persisted sources").wait_for()

                deleted_payload = page.evaluate(
                    """async ({ corpusId, corpusVersion }) => {
                        const response = await fetch('/retrieve', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            question: 'How long must records be retained?',
                            corpus_id: corpusId,
                            corpus_version: corpusVersion,
                            top_k: 1
                          })
                        });
                        return response.json();
                    }""",
                    {"corpusId": corpus_id, "corpusVersion": corpus_version},
                )

                assert deleted_payload["evidence"] == []
            finally:
                browser.close()


@contextmanager
def _live_server(tmp_path: Path) -> Iterator[str]:
    port = _free_port()
    settings = Settings(
        app_env="test",
        rag_mode="mock",
        default_top_k=4,
        database_url=f"sqlite:///{(tmp_path / 'ui-browser-smoke.db').as_posix()}",
    )
    app = create_app(settings)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_ready(base_url)
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _wait_for_ready(base_url: str) -> None:
    deadline = time.monotonic() + 10
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/ready", timeout=0.5) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"server did not become ready: {last_error}")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
