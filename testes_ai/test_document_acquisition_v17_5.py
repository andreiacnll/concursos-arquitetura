from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analise.platform_documents import (
    PlatformDocument,
    _vortal_documents_from_payload,
    detect_platform,
    discover_public_vortal_documents,
)


class DocumentAcquisitionV175Tests(unittest.TestCase):
    def test_vortal_nested_payload_is_read(self) -> None:
        payload = {
            "result": {
                "data": {
                    "documentList": [
                        {
                            "documentId": "doc-1",
                            "fileName": "Programa do Procedimento.pdf",
                            "downloadUrl": "/public/files/programa.pdf",
                        }
                    ]
                }
            }
        }

        docs = _vortal_documents_from_payload(
            payload,
            "https://community.vortal.biz",
        )

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].external_id, "doc-1")
        self.assertEqual(
            docs[0].source_url,
            "https://community.vortal.biz/public/files/programa.pdf",
        )

    def test_vortal_payload_deduplicates_same_download(self) -> None:
        payload = {
            "documents": [
                {
                    "id": "a",
                    "fileName": "Programa.pdf",
                    "downloadUrl": "/x/programa.pdf",
                },
                {
                    "id": "b",
                    "fileName": "Programa duplicado.pdf",
                    "downloadUrl": "/x/programa.pdf",
                },
            ]
        }

        docs = _vortal_documents_from_payload(
            payload,
            "https://community.vortal.biz",
        )
        self.assertEqual(len(docs), 1)

    def test_vortal_uses_browser_when_api_is_empty(self) -> None:
        fake = [
            PlatformDocument(
                external_id="browser-1",
                source_url="https://community.vortal.biz/file/programa.pdf",
                filename="Programa.pdf",
            )
        ]

        with patch(
            "app.analise.platform_documents._request_json",
            return_value={"documentList": []},
        ), patch(
            "app.analise.platform_documents._discover_vortal_with_playwright",
            return_value=(fake, True, []),
        ):
            result = discover_public_vortal_documents(
                "https://community.vortal.biz/Public/public-tender-documents/abc",
                timeout=1,
            )

        self.assertEqual(result.status, "success")
        self.assertTrue(result.used_playwright)
        self.assertEqual(len(result.public_documents or []), 1)

    def test_detect_platform_finds_vortal_in_legacy_extra_field(self) -> None:
        platform, url = detect_platform(
            {
                "link": "https://www.base.gov.pt/Base4/pt/detalhe/?id=1",
                "fonte_antiga": (
                    "Peças: https://community.vortal.biz/"
                    "Public/public-tender-documents/abc"
                ),
            }
        )
        self.assertEqual(platform, "vortal")
        self.assertIn("vortal.biz", url)


if __name__ == "__main__":
    unittest.main()
