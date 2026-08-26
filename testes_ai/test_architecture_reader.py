import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.analise.reader import (
    create_source_manifest,
    read_architecture_documents,
)
from app.architecture_intelligence.pipeline import (
    materialize_experimental_source_documents,
)
from app.architecture_intelligence.schemas import SourceDocument


class ArchitectureReaderManifestTests(unittest.TestCase):
    def test_blocks_previous_analysis_outputs_and_gold_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ficha.json").write_text("{}", encoding="utf-8")
            (root / "analise.json").write_text("{}", encoding="utf-8")
            (root / "textos.json").write_text("{}", encoding="utf-8")
            (root / "ficha_analise_existente.txt").write_text(
                "analise antiga",
                encoding="utf-8",
            )
            (root / "lumiar_expected_analysis.json").write_text(
                json.dumps({"gold": True}),
                encoding="utf-8",
            )
            (root / "base_announcement.json").write_text(
                json.dumps({"source_role": "official_announcement"}),
                encoding="utf-8",
            )
            (root / "programa.pdf").write_bytes(b"%PDF-1.4")

            manifest = create_source_manifest(root, job_id=1)
            by_name = {item.filename: item for item in manifest.items}

            self.assertEqual(by_name["ficha.json"].source_type, "legacy_analysis")
            self.assertFalse(by_name["ficha.json"].accepted_for_reader)
            self.assertEqual(by_name["analise.json"].source_type, "generated_analysis")
            self.assertFalse(by_name["analise.json"].accepted_for_reader)
            self.assertEqual(by_name["textos.json"].source_type, "extracted_text")
            self.assertFalse(by_name["textos.json"].accepted_for_reader)
            self.assertFalse(
                by_name["ficha_analise_existente.txt"].accepted_for_reader
            )
            self.assertFalse(
                by_name["lumiar_expected_analysis.json"].accepted_for_reader
            )
            self.assertEqual(
                by_name["base_announcement.json"].source_type,
                "official_announcement",
            )
            self.assertFalse(by_name["base_announcement.json"].accepted_for_reader)
            self.assertTrue(by_name["base_announcement.json"].accepted_for_metadata)
            self.assertEqual(by_name["programa.pdf"].source_type, "official_document")
            self.assertTrue(by_name["programa.pdf"].accepted_for_reader)

    def test_reader_reports_missing_official_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ficha.json").write_text("{}", encoding="utf-8")
            manifest = create_source_manifest(root, job_id=2)
            output = read_architecture_documents(
                concurso={
                    "titulo": "Concurso de Concecao para Reabilitacao da Escola Secundaria do Lumiar",
                    "entidade": "Municipio de Lisboa",
                    "tipo_procedimento": "Concurso de concecao",
                },
                manifest=manifest,
                root=root,
            )

            self.assertEqual(output["sources"], [])
            self.assertTrue(output["document_alerts"])
            self.assertIn(
                "Nenhum documento oficial aceite",
                output["document_alerts"][0]["value"],
            )

    def test_reader_uses_base_announcement_as_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "base_announcement.json").write_text(
                json.dumps(
                    {
                        "source_role": "official_announcement",
                        "source_name": "Anuncio BASE 420959",
                        "titulo": "Concurso de Concecao para Reabilitacao da Escola Secundaria do Lumiar",
                        "entidade": "Municipio de Lisboa",
                        "tipo_procedimento": "Concurso de concecao",
                    }
                ),
                encoding="utf-8",
            )
            manifest = create_source_manifest(root, job_id=3)
            output = read_architecture_documents(
                concurso={},
                manifest=manifest,
                root=root,
            )

            self.assertEqual(output["document_quality"], "announcement_only")
            self.assertEqual(output["sources"], [])
            self.assertEqual(
                output["procedure_identity"]["object"]["source_document"],
                "Anuncio BASE 420959",
            )
            self.assertIn("criterios", output["fields_missing"])

    def test_disguised_acingov_zip_is_expanded_into_official_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloads = root / "plataforma_publica" / "downloads"
            downloads.mkdir(parents=True)
            cache = root / "jobs" / "52"
            cache.mkdir(parents=True)
            (cache / "textos.json").write_text(
                json.dumps(
                    {
                        "Processo Concurso\\CE_ES_Lumiar.pdf": "Caderno de encargos. ARTIGO 1.º Objeto.",
                        "Processo Concurso\\ANEXO I - Programa Preliminar ES LUMIAR.pdf": "Programa preliminar. Fase 1.",
                        "Processo Concurso\\ANEXOII-designacaojuri - Lumiar.docx": "Designacao do juri.",
                    }
                ),
                encoding="utf-8",
            )
            container = downloads / "01-OTMxNTc2.pdf"
            with zipfile.ZipFile(container, "w") as archive:
                archive.writestr("Processo Concurso/CE_ES_Lumiar.pdf", b"%PDF-1.4 CE")
                archive.writestr(
                    "Processo Concurso/ANEXO I - Programa Preliminar ES LUMIAR.pdf",
                    b"%PDF-1.4 PROGRAMA",
                )
                archive.writestr(
                    "Processo Concurso/ANEXOII-designacaojuri - Lumiar.docx",
                    b"PK\x03\x04",
                )

            source = SourceDocument(
                document_id="acingov-931576",
                concurso_id=435,
                filename="01-OTMxNTc2.pdf",
                path=container.as_posix(),
                origin="acingov",
                source_role="platform_document",
                content_type="application/pdf",
                text="",
                metadata={
                    "source_url": "https://www.acingov.pt/acingovprod/2/zonaPublica/zona_publica_c/donwloadProcedurePiece/OTMxNTc2",
                    "text_cache_paths": [(cache / "textos.json").as_posix()],
                },
            )
            materialized = materialize_experimental_source_documents([source])
            accepted = materialized.documents
            accepted_names = {item.filename for item in accepted}

            self.assertIn("CE_ES_Lumiar.pdf", accepted_names)
            self.assertIn("ANEXO I - Programa Preliminar ES LUMIAR.pdf", accepted_names)
            self.assertIn("ANEXOII-designacaojuri - Lumiar.docx", accepted_names)
            self.assertTrue(all(item.sha256 for item in accepted))
            self.assertTrue(
                all(
                    item.origin == "acingov"
                    and item.source_role == "official_document"
                    and item.metadata["source_url"].startswith("https://www.acingov.pt")
                    and item.metadata["parent_document_id"] == "acingov-931576"
                    and item.metadata["parent_sha256"]
                    and item.text.strip()
                    for item in accepted
                )
            )
            self.assertEqual(
                materialized.manifest["summary"]["children_accepted"],
                3,
            )
            self.assertEqual(
                materialized.manifest["summary"]["children_with_text"],
                3,
            )


if __name__ == "__main__":
    unittest.main()
