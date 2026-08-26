from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..extrair_texto_pdf import extrair_pdf
from .source_manifest import SourceManifest
from .spreadsheet_reader import (
    SPREADSHEET_EXTENSIONS,
    extract_spreadsheet_text,
    structured_tables_from_results,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split()).strip()


def _sentence(value: Any, limit: int = 360) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    window = text[:limit].rstrip()
    end = max(window.rfind("."), window.rfind("?"), window.rfind("!"))
    if end < max(80, limit // 3):
        end = window.rfind(";")
    if end < max(80, limit // 3):
        end = window.rfind(" ")
    return (window[: end + 1] if end > 0 else window).rstrip(" ,;:") + "..."


def _evidence(
    value: str,
    *,
    document: str,
    section: str = "",
    confidence: float = 0.7,
    status: str = "confirmado",
) -> dict:
    text = _clean(value)
    return {
        "value": text or "Nao identificado nas pecas analisadas",
        "source_document": document,
        "page": None,
        "section": section,
        "confidence": confidence,
        "status": status if text else "por validar",
        "evidence_excerpt": _sentence(text, 280) if text else "",
    }


def _read_pdf(path: Path) -> str:
    try:
        return extrair_pdf(path)
    except Exception:
        return ""


def _cached_text_for_path(
    extracted_texts: Mapping[str, str] | None,
    path: str,
) -> str | None:
    if not extracted_texts:
        return None
    normalizado = path.replace("\\", "/")
    for nome, texto in extracted_texts.items():
        if str(nome).replace("\\", "/") == normalizado:
            return texto
    return None


def _read_source(
    path: Path,
    display_name: str,
    *,
    cached_text: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return cached_text if cached_text is not None else _read_pdf(path), None
    if suffix in SPREADSHEET_EXTENSIONS:
        text, structured = extract_spreadsheet_text(
            path,
            display_name=display_name,
        )
        return cached_text if cached_text is not None else text, structured
    if suffix in {".txt", ".json"}:
        if cached_text is not None:
            return cached_text, None
        return path.read_text(encoding="utf-8", errors="ignore"), None
    return "", None

def _source_texts(
    manifest: SourceManifest,
    root: Path,
    extracted_texts: Mapping[str, str] | None = None,
) -> tuple[
    list[tuple[str, str]],
    dict[str, str],
    list[dict[str, Any]],
]:
    texts: list[tuple[str, str]] = []
    read_status: dict[str, str] = {}
    spreadsheet_results: list[dict[str, Any]] = []
    for item in manifest.items:
        if not item.accepted_for_reader:
            continue
        path = root / item.path
        cached_text = _cached_text_for_path(extracted_texts, item.path)
        text, structured = _read_source(
            path,
            item.path,
            cached_text=cached_text,
        )
        if text:
            texts.append((item.path, text))
            read_status[item.path] = "read"
            if structured is not None:
                spreadsheet_results.append(structured)
        else:
            read_status[item.path] = "read_failed"
    return texts, read_status, spreadsheet_results


def _announcement_metadata(
    manifest: SourceManifest,
    root: Path,
) -> dict[str, Any] | None:
    for item in manifest.items:
        if item.source_type != "official_announcement":
            continue
        path = root / item.path
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None
    return None


def _find_money(texts: Iterable[str]) -> list[str]:
    seen = []
    for text in texts:
        for match in re.finditer(
            r"\d{1,3}(?:[ .]\d{3})*(?:,\d{2})?\s*(?:€|EUR|euros)",
            text,
            flags=re.IGNORECASE,
        ):
            clean = _clean(match.group(0))
            if clean not in seen:
                seen.append(clean)
    return seen[:8]


def _find_percentages(texts: Iterable[str]) -> list[str]:
    seen = []
    for text in texts:
        for match in re.finditer(r"\b\d{1,3}\s*%", text):
            clean = _clean(match.group(0))
            if clean not in seen:
                seen.append(clean)
    return seen[:12]


def _lines_matching(
    texts: Iterable[str],
    patterns: list[str],
    limit: int = 12,
) -> list[str]:
    result = []
    for text in texts:
        for match in re.finditer(r"[^\r\n]+", text):
            clean = _clean(match.group(0))
            if len(clean) < 8:
                continue
            lower = clean.lower()
            if any(pattern in lower for pattern in patterns):
                if clean not in result:
                    result.append(clean)
            if len(result) >= limit:
                return result
    return result


def _source_text_values(source_texts: Iterable[tuple[str, str]]) -> Iterable[str]:
    return (text for _, text in source_texts)

def _source_summary(source_texts: list[tuple[str, str]]) -> list[dict]:
    return [
        {
            "name": name,
            "classification": "peca do procedimento",
            "format": Path(name).suffix.lower().lstrip("."),
            "pages": None,
            "status": "analisado" if text else "sem texto",
            "origin": "official_document",
        }
        for name, text in source_texts
    ]


def _manifest_source_audit(
    manifest: SourceManifest,
    read_status: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    result = []
    read_status = read_status or {}
    for item in manifest.items:
        if not (item.accepted_for_reader or item.accepted_for_metadata):
            continue
        result.append(
            {
                "name": item.filename,
                "path": item.path,
                "source_type": item.source_type,
                "source_role": item.source_role,
                "origin": item.origin,
                "sha256": item.sha256,
                "read_status": read_status.get(item.path, item.read_status),
                "accepted_for_reader": item.accepted_for_reader,
                "accepted_for_metadata": item.accepted_for_metadata,
            }
        )
    return result


def _document_quality(source_texts: list[tuple[str, str]], announcement: dict[str, Any] | None) -> str:
    if source_texts:
        names = " ".join(name.lower() for name, _ in source_texts)
        has_program = "programa" in names
        has_caderno = "caderno" in names or "encargos" in names
        has_preliminar = "preliminar" in names
        return "complete" if has_program and has_caderno and has_preliminar else "partial"
    if announcement:
        return "announcement_only"
    return "unavailable"


def _fields_status(output: dict[str, Any]) -> tuple[list[str], list[str]]:
    filled: list[str] = []
    missing: list[str] = []

    procedure = output.get("procedure_identity") or {}
    checks = {
        "objeto": procedure.get("object"),
        "entidade": procedure.get("entity"),
        "tipo_procedimento": procedure.get("procedure_type"),
        "precos": (output.get("prices") or {}).get("values"),
        "criterios": (output.get("award_strategy") or {}).get("criteria"),
        "equipa": output.get("required_team"),
        "fases_entregaveis": output.get("phases_and_deliverables"),
        "documentos_proposta": output.get("submission_documents"),
        "documentos_habilitacao": output.get("post_award_documents"),
        "condicoes_financeiras": (output.get("financial_conditions") or {}).get("payments"),
        "riscos_exclusao": output.get("exclusion_risks"),
        "condicionantes_tecnicas": output.get("technical_constraints"),
    }
    for key, value in checks.items():
        if value:
            filled.append(key)
        else:
            missing.append(key)
    return filled, missing


def read_architecture_documents(
    *,
    concurso: dict[str, Any],
    manifest: SourceManifest,
    root: Path,
    extracted_texts: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source_texts, read_status, spreadsheet_results = _source_texts(
        manifest,
        root,
        extracted_texts,
    )
    announcement = _announcement_metadata(manifest, root)
    first_document = (
        source_texts[0][0]
        if source_texts
        else (announcement or {}).get("source_name")
        or "Anuncio BASE"
    )

    prices = _find_money(_source_text_values(source_texts))
    percentages = _find_percentages(_source_text_values(source_texts))
    team_lines = _lines_matching(
        _source_text_values(source_texts),
        ["coordenador", "arquiteto", "engenheiro", "ordem", "especialidade"],
    )
    deliverable_lines = _lines_matching(
        _source_text_values(source_texts),
        ["memoria", "memória", "descritiva", "painel", "proposta", "cronograma", "estimativa"],
    )
    phase_lines = _lines_matching(
        _source_text_values(source_texts),
        ["fase", "prazo", "pagamento", "dias", "meses"],
    )
    exclusion_lines = _lines_matching(
        _source_text_values(source_texts),
        ["exclus", "anonim", "caduc", "fora do prazo", "assinatura", "habilitação"],
    )
    constraint_lines = _lines_matching(
        _source_text_values(source_texts),
        ["bim", "acessibilidade", "segurança", "sustentabilidade", "funcionamento", "reabilitação"],
    )

    structured_tables = structured_tables_from_results(spreadsheet_results)

    result = {
        "structured_tables": structured_tables,
        "spreadsheet_reader_results": spreadsheet_results,
        "procedure_identity": {
            "object": _evidence(
                (announcement or {}).get("titulo") or concurso.get("titulo"),
                document=first_document,
                section="Anuncio / identificacao",
                confidence=0.62 if not source_texts else 0.78,
            ),
            "entity": _evidence(
                (announcement or {}).get("entidade") or concurso.get("entidade"),
                document=first_document,
                section="Entidade adjudicante",
                confidence=0.62 if not source_texts else 0.78,
            ),
            "procedure_type": _evidence(
                (announcement or {}).get("tipo_procedimento") or concurso.get("tipo_procedimento"),
                document=first_document,
                section="Procedimento",
                confidence=0.62 if not source_texts else 0.78,
            ),
        },
        "prices": {
            "values": [
                _evidence(value, document=first_document, section="Precos")
                for value in prices
            ],
            "service_price": None,
            "maximum_construction_cost": None,
            "alerts": [
                "Nao foi possivel separar automaticamente preco dos servicos e custo da obra."
            ] if len(prices) > 1 else [],
        },
        "award_strategy": {
            "criteria": [
                {
                    "factor": "Criterio identificado",
                    "weight": value,
                    "evidence": _evidence(
                        value,
                        document=first_document,
                        section="Criterios de adjudicacao",
                    ),
                }
                for value in percentages
            ]
        },
        "required_team": [
            {
                "requirement": line,
                "category": "equipa exigida",
                "evidence": _evidence(
                    line,
                    document=first_document,
                    section="Equipa exigida",
                ),
            }
            for line in team_lines
        ],
        "phases_and_deliverables": [
            {
                "phase": "fase identificada",
                "items": [
                    _evidence(
                        line,
                        document=first_document,
                        section="Entregaveis e fases",
                    )
                    for line in deliverable_lines[:8]
                ],
                "timeline": [
                    _evidence(
                        line,
                        document=first_document,
                        section="Prazos e pagamentos",
                    )
                    for line in phase_lines[:8]
                ],
            }
        ] if deliverable_lines or phase_lines else [],
        "submission_documents": [
            _evidence(line, document=first_document, section="Documentos da proposta")
            for line in deliverable_lines[:10]
        ],
        "post_award_documents": [
            _evidence(line, document=first_document, section="Habilitacao")
            for line in _lines_matching(_source_text_values(source_texts), ["habilitação", "habilitacao", "adjudicatário"], 10)
        ],
        "financial_conditions": {
            "payments": [
                _evidence(line, document=first_document, section="Pagamentos")
                for line in _lines_matching(_source_text_values(source_texts), ["pagamento", "preço", "preco", "caução"], 10)
            ]
        },
        "exclusion_risks": [
            _evidence(line, document=first_document, section="Riscos de exclusao")
            for line in exclusion_lines
        ],
        "technical_constraints": [
            _evidence(line, document=first_document, section="Condicionantes tecnicas")
            for line in constraint_lines
        ],
        "evidence": [],
        "document_alerts": [
            _evidence(
                "Apenas foi encontrado o anuncio BASE; nao foram localizadas pecas oficiais publicas aceites pelo reader.",
                document="manifesto de fontes",
                section="Manifest",
                confidence=1.0,
                status="por validar",
            )
        ] if not source_texts and announcement else [
            _evidence(
                "Nenhum documento oficial aceite pelo reader.",
                document="manifesto de fontes",
                section="Manifest",
                confidence=1.0,
                status="por validar",
            )
        ] if not source_texts else [],
        "sources": _source_summary(source_texts),
    }
    result["document_quality"] = _document_quality(source_texts, announcement)
    result["official_source_audit"] = _manifest_source_audit(
        manifest,
        read_status,
    )
    filled, missing = _fields_status(result)
    result["fields_filled"] = filled
    result["fields_missing"] = missing
    result["announcement_metadata"] = announcement or {}
    return result
