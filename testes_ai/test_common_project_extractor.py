from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from app.analise.common_project_extractor import (
    apply_common_project_extraction,
    extract_common_project_data,
    extract_docx_text,
)
from app.analise.intervention_program import (
    extract_intervention_program,
)
from app.analise.platform_documents import (
    _content_suffix,
)
from app.analise.worker import (
    _campos_concurso_extraidos,
    _tipo_arquivo,
)


DOC_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Programa do Procedimento</w:t></w:r></w:p>
    <w:p><w:r><w:t>O anúncio foi publicado em 5 de agosto de 2026.</w:t></w:r></w:p>
    <w:p><w:r><w:t>O prazo para apresentação das propostas termina em 18 de setembro de 2026 às 17:00.</w:t></w:r></w:p>
    <w:p><w:r><w:t>O preço base do procedimento é de 125 000,00 €.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Critério de adjudicação: Qualidade 70% e Preço 30%.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Artigo 12.º - Documentos que constituem a proposta</w:t></w:r></w:p>
    <w:p><w:r><w:t>a) Memória descritiva e justificativa</w:t></w:r></w:p>
    <w:p><w:r><w:t>b) Proposta de honorários</w:t></w:r></w:p>
  </w:body>
</w:document>
"""


class CommonProjectExtractionTests(unittest.TestCase):
    def _docx(self, folder: Path) -> Path:
        path = folder / "PC_Projeto.docx"
        with ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", DOC_XML)
            archive.writestr(
                "[Content_Types].xml",
                "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>",
            )
        return path

    def test_ooxml_signature_preserves_declared_extension(self) -> None:
        self.assertEqual(
            _content_suffix(
                b"PK\x03\x04",
                "application/octet-stream",
                "Programa.docx",
            ),
            ".docx",
        )
        self.assertEqual(
            _content_suffix(
                b"PK\x03\x04",
                "application/zip",
                "Anexos.zip",
            ),
            ".zip",
        )

    def test_docx_is_not_treated_as_recursive_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._docx(Path(temporary))
            self.assertEqual(_tipo_arquivo(path), "")

    def test_docx_text_and_common_fields_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._docx(Path(temporary))
            text = extract_docx_text(path)

        self.assertIn("Programa do Procedimento", text)
        result = extract_common_project_data(
            textos={"PC_Projeto.docx": text},
            concurso={
                "titulo": "Concurso Público para elaboração de projeto",
                "tipo_procedimento": "Concurso Público",
            },
        )

        self.assertEqual(
            result["publication_date"]["value"],
            "05/08/2026",
        )
        self.assertEqual(
            result["submission_deadline"]["value"],
            "18-09-2026 17:00",
        )
        self.assertEqual(
            result["base_price"]["value"],
            "125 000,00 €",
        )
        self.assertEqual(
            result["award_criteria"]["summary"],
            "Qualidade 70% • Preço 30%",
        )
        self.assertIn(
            "Memória descritiva e justificativa",
            result["deliverables"],
        )

    def test_apply_updates_card_fields_without_serialized_dict(self) -> None:
        text = (
            "O anúncio foi publicado em 5 de agosto de 2026. "
            "O prazo para apresentação das propostas termina em "
            "18 de setembro de 2026 às 17:00. "
            "Critério de adjudicação: Qualidade 70% e Preço 30%."
        )
        concurso = {
            "data": None,
            "data_entrega_propostas": None,
            "preco_base": None,
            "tipo_procedimento": "Concurso Público",
            "criterio_tipo": None,
            "criterio_resumo": None,
            "criterio_detalhe": None,
            "entregaveis": None,
            "titulo": "Concurso Público para elaboração de projeto",
        }
        ficha = {
            "identificacao": {
                "tipo_procedimento": "Concurso Público",
            },
            "criterios": {},
            "economia": {},
            "entregaveis": {
                "principais": ["{'principais': ['texto corrompido'"],
            },
            "document_insights": {},
        }
        apply_common_project_extraction(
            ficha=ficha,
            textos={"PC_Projeto.docx": text},
            concurso=concurso,
        )
        fields = _campos_concurso_extraidos(concurso, ficha)

        self.assertEqual(fields["data"], "05/08/2026")
        self.assertEqual(
            fields["data_entrega_propostas"],
            "18-09-2026 17:00",
        )
        self.assertFalse(
            str(fields.get("entregaveis") or "").startswith("{")
        )

    def test_intervention_program_rejects_code_and_filename_soup(self) -> None:
        ficha = {
            "identificacao": {
                "titulo": (
                    "Projeto de arquitetura paisagista "
                    "do Parque Urbano"
                )
            }
        }
        result = extract_intervention_program(
            ficha=ficha,
            textos={
                "EIR.pdf": (
                    "SRU0149-SRU-XX-XXX-ET-URB-0003.pdf "
                    "AEP PAI RVI RTV RSU SCI PSS SSI PSA SNL "
                    "SRU0149-SRU-XX-XXX-DS-URB-0004.dwg "
                    "Códigos (3 caracteres) Arquitetura Paisagista PAI."
                ),
                "PC.docx": (
                    "A intervenção visa criar um parque urbano inclusivo, "
                    "articulando a arquitetura paisagista com percursos "
                    "pedonais, sistema verde e drenagem sustentável."
                ),
            },
        )

        self.assertTrue(result["active"])
        program_items = result["themes"]["program_intervention"]["items"]
        self.assertTrue(program_items)
        self.assertFalse(
            any(".pdf" in item or ".dwg" in item for item in program_items)
        )


if __name__ == "__main__":
    unittest.main()
