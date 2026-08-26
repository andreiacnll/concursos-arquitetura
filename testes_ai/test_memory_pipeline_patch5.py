from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.analise import document_ai, worker
from app.analise.reader.architecture_reader import read_architecture_documents
from app.analise.reader.source_manifest import SourceManifest, SourceManifestItem


class _FakePage:
    def __init__(self, text: str | Exception) -> None:
        self.text = text

    def extract_text(self) -> str:
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


class _FakeReader:
    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages


class MemoryPipelinePatch5Tests(unittest.TestCase):
    def test_pdf_extraction_keeps_page_order_without_page_text_list(self) -> None:
        reader = _FakeReader(
            [
                _FakePage("first page"),
                _FakePage(""),
                _FakePage(RuntimeError("broken page")),
                _FakePage("last page"),
            ]
        )
        with patch("app.analise.worker.PdfReader", return_value=reader):
            result = worker._extrair_texto_pdf(Path("synthetic.pdf"))

        self.assertEqual(result, "first page\n\nlast page")
        self.assertNotIn("paginas = []", inspect.getsource(worker._extrair_texto_pdf))

    def test_textos_json_is_valid_without_global_json_dumps(self) -> None:
        expected = {
            "Programa.pdf": "Mandatory team: architect.",
            "Caderno.pdf": "Exclusion if proposal is late.",
        }
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "textos.json"
            worker._escrever_textos_json(destination, expected)
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), expected)

        source = inspect.getsource(worker._guardar_resultados)
        self.assertNotIn("json.dumps(textos", source)
        self.assertIn("_escrever_textos_json", source)

    def test_architecture_reader_reuses_cached_pdf_text_without_global_join(self) -> None:
        cached_text = (
            "Programa funcional\n"
            "A equipa inclui arquiteto coordenador.\n"
            "Criterio qualidade 70%.\n"
            "Preco base 12 000 EUR.\n"
            "A proposta fora do prazo sera excluida."
        )
        manifest = SourceManifest(
            job_id=1,
            root=".",
            items=[
                SourceManifestItem(
                    path="Programa.pdf",
                    filename="Programa.pdf",
                    source_type="official_document",
                    source_role="procedure_piece",
                    accepted_for_reader=True,
                )
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Programa.pdf").write_bytes(b"not-read")
            with patch(
                "app.analise.reader.architecture_reader._read_pdf",
                side_effect=AssertionError("PDF should be reused from cache"),
            ):
                result = read_architecture_documents(
                    concurso={"titulo": "Synthetic competition"},
                    manifest=manifest,
                    root=root,
                    extracted_texts={"Programa.pdf": cached_text},
                )

        self.assertEqual(result["prices"]["values"][0]["value"], "12 000 EUR")
        self.assertTrue(result["required_team"])
        source = inspect.getsource(read_architecture_documents)
        self.assertNotIn('"\\n".join(text for _, text in source_texts)', source)

    def test_ai_context_is_selected_once_and_keeps_priority_documents(self) -> None:
        textos = {
            "Programa funcional.pdf": "Espacos: biblioteca e auditorio.",
            "Regulamento.pdf": "A equipa deve incluir arquiteto coordenador.",
        }
        with patch.object(
            document_ai,
            "_selecionar_texto_prioritario",
            wraps=document_ai._selecionar_texto_prioritario,
        ) as selecionar, patch.object(document_ai, "_chamar_openai", return_value=None):
            result = document_ai.analisar_documentos_ai(
                textos=textos,
                documentos=[],
                titulo="Synthetic competition",
            )

        self.assertEqual(selecionar.call_count, 1)
        self.assertEqual(result["origem"], "extracao_documental_local")
        contexto = document_ai._selecionar_texto_prioritario(textos)
        self.assertIn("Programa funcional.pdf", contexto)
        self.assertIn("Regulamento.pdf", contexto)



if __name__ == "__main__":
    unittest.main()