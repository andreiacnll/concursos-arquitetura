from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from app.fontes import common


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        text: str = "<html></html>",
        headers: dict[str, str] | None = None,
        reason: str = "Service Unavailable",
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers or {
            "content-type": "text/html"
        }
        self.reason = reason

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}"
            )


class FakeSession:
    def __init__(
        self,
        responses: list[FakeResponse],
    ) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls = 0

    def get(self, *_args: object, **_kwargs: object) -> FakeResponse:
        self.calls += 1
        return self.responses.pop(0)

    def close(self) -> None:
        return None


class ExternalSourceThrottleTests(unittest.TestCase):
    def setUp(self) -> None:
        common._LAST_REQUEST_AT.clear()

    def test_retry_after_and_backoff_are_respected(self) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    503,
                    headers={
                        "content-type": "text/html",
                        "Retry-After": "7",
                    },
                ),
                FakeResponse(
                    200,
                    text="<html>ok</html>",
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as temp:
            state_path = Path(temp) / "state.json"
            with (
                patch.object(
                    common,
                    "TRANSPORT_STATE_PATH",
                    state_path,
                ),
                patch.object(common, "MAX_RETRIES", 2),
                patch.object(common, "LISTING_INTERVAL", 0.0),
                patch.object(common, "JITTER_MAX", 0.0),
                patch.object(common, "BACKOFF_BASE", 1.0),
                patch.object(common, "BACKOFF_MAX", 20.0),
                patch.object(common.time, "sleep") as sleep,
            ):
                html = common.fetch_html(
                    "https://example.test/list",
                    session=session,
                    request_kind="listing",
                )

        self.assertEqual(html, "<html>ok</html>")
        self.assertEqual(session.calls, 2)
        sleep.assert_any_call(7.0)

    def test_circuit_breaker_suspends_repeated_503_source(self) -> None:
        session = FakeSession(
            [
                FakeResponse(503),
                FakeResponse(503),
                FakeResponse(503),
            ]
        )

        with tempfile.TemporaryDirectory() as temp:
            state_path = Path(temp) / "state.json"
            with (
                patch.object(
                    common,
                    "TRANSPORT_STATE_PATH",
                    state_path,
                ),
                patch.object(common, "MAX_RETRIES", 3),
                patch.object(common, "CIRCUIT_FAILURES", 3),
                patch.object(common, "DETAIL_INTERVAL", 0.0),
                patch.object(common, "JITTER_MAX", 0.0),
                patch.object(common, "BACKOFF_BASE", 1.0),
                patch.object(common, "BACKOFF_MAX", 1.0),
                patch.object(common.time, "sleep"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "suspensa",
                ):
                    common.fetch_html(
                        "https://blocked.test/detail",
                        session=session,
                        request_kind="detail",
                    )

            payload = json.loads(
                state_path.read_text(encoding="utf-8")
            )

        host_state = payload["hosts"]["blocked.test"]
        self.assertEqual(
            host_state["consecutive_failures"],
            3,
        )
        self.assertTrue(host_state["suspended_until"])

    def test_weekly_workflow_contains_slow_search_policy(self) -> None:
        workflow = Path(
            ".github/workflows/"
            "procurar-concursos-fontes-externas.yml"
        ).read_text(encoding="utf-8")

        self.assertIn('cron: "47 10 * * 6"', workflow)
        self.assertIn(
            "FONTES_EXTERNAS_INTERVALO_DETALHES",
            workflow,
        )
        self.assertIn(
            "fontes_externas_transport_state.json",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
