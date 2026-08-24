from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.analise import sharepoint_public


def listing_html(rows: list[dict[str, object]]) -> str:
    payload = {
        "wpq": "",
        "Templates": {},
        "ListData": {
            "Row": rows,
        },
    }
    return (
        "<html><script>"
        "var g_listData = "
        + json.dumps(payload)
        + "; var after = true;"
        "</script></html>"
    )


class DummySession:
    def close(self) -> None:
        return None


class SharePointPublicTests(unittest.TestCase):
    def test_parses_embedded_list_data(self) -> None:
        rows = [
            {
                "FSObjType": "0",
                "FileRef": "/personal/test/Documents/root/programa.pdf",
                "FileLeafRef": "programa.pdf",
                "UniqueId": "{ABC}",
            }
        ]
        parsed = sharepoint_public.list_rows_from_html(
            listing_html(rows)
        )
        self.assertEqual(parsed, rows)

    def test_recurses_into_public_subfolders(self) -> None:
        root_ref = "/personal/test/Documents/root"
        child_ref = root_ref + "/PC"
        root_html = listing_html(
            [
                {
                    "FSObjType": "1",
                    "FileRef": child_ref,
                    "FileLeafRef": "PC",
                    "UniqueId": "{FOLDER}",
                }
            ]
        )
        child_html = listing_html(
            [
                {
                    "FSObjType": "0",
                    "FileRef": child_ref + "/Programa.pdf",
                    "FileLeafRef": "Programa.pdf",
                    "UniqueId": "{FILE}",
                    "Modified.": "2026-08-04T12:00:00Z",
                }
            ]
        )

        responses = [
            (
                root_html,
                (
                    "https://tenant-my.sharepoint.com"
                    + root_ref
                    + "?ga=1"
                ),
            ),
            (
                child_html,
                (
                    "https://tenant-my.sharepoint.com"
                    + child_ref
                    + "?ga=1"
                ),
            ),
        ]

        with (
            patch.object(
                sharepoint_public,
                "_session",
                return_value=DummySession(),
            ),
            patch.object(
                sharepoint_public,
                "_fetch_listing",
                side_effect=responses,
            ),
        ):
            files = (
                sharepoint_public
                .discover_public_sharepoint_files(
                    (
                        "https://tenant-my.sharepoint.com/"
                        ":f:/g/personal/test/TOKEN"
                    ),
                    interval=0,
                )
            )

        self.assertEqual(len(files), 1)
        self.assertEqual(
            files[0].relative_path,
            "PC/Programa.pdf",
        )
        self.assertEqual(
            files[0].server_relative_url,
            child_ref + "/Programa.pdf",
        )
        self.assertIn(
            "download=1",
            files[0].source_url,
        )

    def test_recognises_sharepoint_links(self) -> None:
        self.assertTrue(
            sharepoint_public.is_sharepoint_public_url(
                "https://tenant-my.sharepoint.com/:f:/g/token"
            )
        )
        self.assertFalse(
            sharepoint_public.is_sharepoint_public_url(
                "https://example.com/documentos"
            )
        )


if __name__ == "__main__":
    unittest.main()
