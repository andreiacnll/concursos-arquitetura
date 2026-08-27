from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from app.analise import worker
from app.analise.platform_documents import (
    PlatformDocument,
    PlatformDocumentResult,
    discover_public_vortal_documents,
    download_public_documents,
)


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        body: bytes,
        content_type: str = "text/html; charset=utf-8",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.body = body
        self.status_code = status_code
        self.encoding = "utf-8"
        self.headers = {"content-type": content_type, **(headers or {})}
        self.closed = False

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int):
        for offset in range(0, len(self.body), max(1, chunk_size)):
            yield self.body[offset : offset + chunk_size]

    def close(self) -> None:
        self.closed = True


class PublicVortalAnalysisTests(unittest.TestCase):
    def test_public_vortal_documents_reach_worker_text_pipeline(self) -> None:
        page_url = "https://community.vortal.biz/Public/tender/open"
        html = b"""
        <html><body>
          <a href="/public/files/Programa-Concurso.txt">
            Programa de Concurso
          </a>
        </body></html>
        """
        response = FakeResponse(url=page_url, body=html)

        with patch(
            "app.analise.platform_documents.requests.get",
            return_value=response,
        ), patch(
            "app.analise.platform_documents._request_json"
        ) as request_json, patch(
            "app.analise.platform_documents._discover_vortal_with_playwright"
        ) as browser:
            result = discover_public_vortal_documents(page_url, timeout=1)

        self.assertEqual(result.status, "success")
        self.assertFalse(result.requires_login)
        self.assertEqual(len(result.public_documents or []), 1)
        request_json.assert_not_called()
        browser.assert_not_called()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache_dir = root / "cache"
            destination = root / "extraido"

            def fake_download(
                documents: list[PlatformDocument],
                selected_cache: Path,
                timeout: int = 90,
            ) -> list[PlatformDocument]:
                downloads = selected_cache / "downloads"
                downloads.mkdir(parents=True, exist_ok=True)
                target = downloads / "001-Programa-Concurso.txt"
                target.write_text(
                    "Programa de Concurso\n"
                    "Criterio de adjudicacao: Qualidade 70% e Preco 30%.",
                    encoding="utf-8",
                )
                document = documents[0]
                document.path = target.relative_to(selected_cache).as_posix()
                document.sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
                return [document]

            concurso = {
                "id": 9001,
                "link_pecas": page_url,
            }
            with patch(
                "app.analise.worker._cache_plataforma_dir",
                return_value=cache_dir,
            ), patch(
                "app.analise.worker.discover_public_documents",
                return_value=result,
            ), patch(
                "app.analise.worker.download_public_documents",
                side_effect=fake_download,
            ), patch(
                "app.analise.worker.atualizar_analise_job",
            ):
                warnings = worker._tentar_recolha_plataforma_publica(
                    {"id": 77},
                    concurso,
                    destination,
                    worker._novo_orcamento_extracao(),
                )

            with patch(
                "app.analise.worker._cache_plataforma_dir",
                return_value=cache_dir,
            ), patch(
                "app.analise.worker._verificar_cancelamento",
            ), patch(
                "app.analise.worker.concurso_por_id",
                return_value=concurso,
            ):
                texts, documents, summary = worker._fase_processamento(
                    {"id": 77, "concurso_id": 9001},
                    destination,
                    warnings,
                    concurso,
                )

            self.assertEqual(warnings, [])
            self.assertTrue(texts)
            self.assertTrue(documents)
            self.assertIn(
                "Qualidade 70%",
                "\n".join(texts.values()),
            )
            self.assertIn("source_platform_status", summary)

    def test_public_intermediate_page_discovers_document_links(self) -> None:
        source_url = "https://community.vortal.biz/Public/redirect/abc"
        final_url = "https://community.vortal.biz/Public/procedure/123"
        html = b"""
        <html><body>
          <a href="/public/files/Programa.pdf">Programa de Concurso</a>
          <a href="/public/files/Caderno.pdf">Caderno de Encargos</a>
          <a href="/public/files/Retificacao-1.pdf">Retificacao</a>
          <a href="/public/files/Esclarecimentos.zip">Esclarecimentos</a>
        </body></html>
        """
        response = FakeResponse(url=final_url, body=html)

        with patch(
            "app.analise.platform_documents.requests.get",
            return_value=response,
        ), patch(
            "app.analise.platform_documents._request_json"
        ) as request_json, patch(
            "app.analise.platform_documents._discover_vortal_with_playwright"
        ) as browser:
            result = discover_public_vortal_documents(source_url, timeout=1)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.platform_url, final_url)
        self.assertEqual(len(result.public_documents or []), 4)
        self.assertTrue(
            all(
                document.source_url.startswith(
                    "https://community.vortal.biz/public/files/"
                )
                for document in result.public_documents or []
            )
        )
        request_json.assert_not_called()
        browser.assert_not_called()

    def test_authenticated_vortal_is_not_bypassed(self) -> None:
        source_url = "https://community.vortal.biz/Public/procedure/private"
        login_url = "https://community.vortal.biz/Account/Login"
        response = FakeResponse(
            url=login_url,
            body=(
                b"<html><body><form>"
                b"<label>Sign in</label>"
                b"<input type='password' name='password'>"
                b"</form></body></html>"
            ),
        )

        with patch(
            "app.analise.platform_documents.requests.get",
            return_value=response,
        ), patch(
            "app.analise.platform_documents._request_json"
        ) as request_json, patch(
            "app.analise.platform_documents._discover_vortal_with_playwright"
        ) as browser:
            result = discover_public_vortal_documents(source_url, timeout=1)

        self.assertEqual(result.status, "login_required")
        self.assertTrue(result.requires_login)
        self.assertEqual(result.public_documents, [])
        request_json.assert_not_called()
        browser.assert_not_called()

    def test_no_documents_does_not_create_document_evidence(self) -> None:
        url = (
            "https://community.vortal.biz/Public/"
            "public-tender-documents/empty-key"
        )
        response = FakeResponse(
            url=url,
            body=b"<html><body>Procedimento sem documentos publicados.</body></html>",
        )

        with patch(
            "app.analise.platform_documents.requests.get",
            return_value=response,
        ), patch(
            "app.analise.platform_documents._request_json",
            return_value={"documentList": []},
        ), patch(
            "app.analise.platform_documents._discover_vortal_with_playwright",
            return_value=([], True, []),
        ):
            result = discover_public_vortal_documents(url, timeout=1)

        self.assertEqual(result.status, "no_documents")
        self.assertFalse(result.requires_login)
        self.assertEqual(result.public_documents, [])

    def test_authenticated_vortal_worker_never_uses_generic_downloader(self) -> None:
        page_url = "https://community.vortal.biz/Account/Login"
        result = PlatformDocumentResult(
            platform="vortal",
            platform_url=page_url,
            status="login_required",
            requires_login=True,
            public_documents=[],
            warnings=["Autenticacao VORTAL obrigatoria."],
        )
        concurso = {
            "id": 9002,
            "titulo": "Procedimento privado",
            "link": "https://www.base.gov.pt/Base4/pt/detalhe/?id=9002",
            "link_pecas": page_url,
        }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache_dir = root / "cache"
            with patch(
                "app.analise.worker._cache_plataforma_dir",
                return_value=cache_dir,
            ), patch(
                "app.analise.worker._copiar_documentos_existentes",
                return_value=False,
            ), patch(
                "app.analise.worker.discover_public_documents",
                return_value=result,
            ), patch(
                "app.analise.worker.download_public_documents"
            ) as download, patch(
                "app.analise.worker._descarregar"
            ) as generic_download, patch(
                "app.analise.worker.atualizar_analise_job",
            ), patch(
                "app.analise.worker._verificar_cancelamento",
            ):
                extracted, warnings = worker._fase_extracao(
                    {"id": 78, "concurso_id": 9002},
                    concurso,
                    root / "job",
                )

            download.assert_not_called()
            generic_download.assert_not_called()
            fallback = extracted / "dados_concurso.txt"
            self.assertTrue(fallback.exists())
            self.assertNotIn("70%", fallback.read_text(encoding="utf-8"))
            self.assertTrue(
                any("Autenticacao VORTAL" in warning for warning in warnings)
            )
            self.assertIn(
                '"status": "login_required"',
                (cache_dir / "metadata.json").read_text(encoding="utf-8"),
            )
    def test_login_html_is_never_saved_as_a_document(self) -> None:
        document = PlatformDocument(
            external_id="private-pdf",
            source_url="https://community.vortal.biz/files/Programa.pdf",
            filename="Programa.pdf",
        )
        response = FakeResponse(
            url="https://community.vortal.biz/Account/Login",
            body=b"<!doctype html><html><form><input type='password'></form></html>",
            content_type="text/html; charset=utf-8",
        )

        with tempfile.TemporaryDirectory() as temporary, patch(
            "app.analise.platform_documents.requests.get",
            return_value=response,
        ):
            saved = download_public_documents(
                [document],
                Path(temporary),
                timeout=1,
            )
            files = [
                path
                for path in Path(temporary).rglob("*")
                if path.is_file()
            ]

        self.assertEqual(saved, [])
        self.assertEqual(files, [])


if __name__ == "__main__":
    unittest.main()