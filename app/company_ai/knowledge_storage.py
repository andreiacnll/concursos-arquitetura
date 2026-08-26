from __future__ import annotations

import json
import re
from contextlib import closing
from typing import Any

from ..database import abrir_conexao
from .models import KnowledgeFact


def _valor_para_json(valor: Any) -> str:
    if hasattr(valor, "model_dump"):
        valor = valor.model_dump()
    return json.dumps(valor, ensure_ascii=False)


def _parse_json(valor: str | None) -> Any:
    if valor in (None, ""):
        return None

    try:
        return json.loads(valor)
    except (TypeError, ValueError, json.JSONDecodeError):
        return valor


def _linha_para_facto(linha) -> KnowledgeFact:
    return KnowledgeFact.model_validate(
        {
            "id": linha["id"],
            "field": linha["field"],
            "value": _parse_json(linha["value_json"]),
            "source": linha["source"] or "",
            "source_type": linha["source_type"] or "",
            "url": linha["url"] or "" if "url" in linha.keys() else "",
            "section": linha["section"] or "" if "section" in linha.keys() else "",
            "evidence_text": (
                linha["evidence_text"] or ""
                if "evidence_text" in linha.keys()
                else ""
            ),
            "confidence": linha["confidence"] or 0.0,
            "status": linha["status"] or "unknown",
        }
    )


def _normalizar_texto(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split()).lower()


def _desembrulhar_resposta(answer: Any) -> Any:
    if isinstance(answer, dict):
        for chave in ("answer", "value", "text", "response"):
            if chave in answer:
                return answer[chave]
    return answer


def _classificar_resposta_validacao(answer: Any) -> str | None:
    resposta = _desembrulhar_resposta(answer)

    if isinstance(resposta, bool):
        return "confirmed" if resposta else "rejected"

    if isinstance(resposta, (int, float)):
        if resposta > 0:
            return "confirmed"
        if resposta < 0:
            return "rejected"
        return None

    if isinstance(resposta, list):
        texto = " ".join(_normalizar_texto(item) for item in resposta)
    elif isinstance(resposta, dict):
        texto = " ".join(_normalizar_texto(item) for item in resposta.values())
    else:
        texto = _normalizar_texto(resposta)

    if not texto:
        return None

    confirmacoes = (
        "sim",
        "confirmo",
        "confirmado",
        "certo",
        "correto",
        "verdadeiro",
        "ok",
    )
    rejeicoes = (
        "nao",
        "não",
        "negativo",
        "rejeito",
        "rejeitado",
        "errado",
        "incorreto",
        "corrigir",
        "correcao",
        "correção",
    )

    if any(
        re.search(rf"\b{re.escape(token)}\b", texto)
        for token in confirmacoes
    ):
        return "confirmed"
    if any(
        re.search(rf"\b{re.escape(token)}\b", texto)
        for token in rejeicoes
    ):
        return "rejected"
    return None


def save_knowledge_fact(
    company_id: int,
    field: str,
    value: Any,
    source: str = "",
    source_type: str = "",
    url: str = "",
    section: str = "",
    evidence_text: str = "",
    confidence: float = 0,
    status: str = "unknown",
) -> KnowledgeFact:
    """
    Guarda um facto empresarial sem apagar históricos anteriores.

    Futuro:
    - validation;
    - conflict resolution;
    - LLM retrieval.
    """
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO company_knowledge_memory (
                company_id,
                field,
                value_json,
                source,
                source_type,
                url,
                section,
                evidence_text,
                confidence,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                str(field or "").strip(),
                _valor_para_json(value),
                str(source or "").strip() or None,
                str(source_type or "").strip() or None,
                str(url or "").strip() or None,
                str(section or "").strip() or None,
                str(evidence_text or "").strip()[:2000] or None,
                float(confidence or 0),
                str(status or "unknown").strip() or "unknown",
            ),
        )
        conexao.commit()

        linha = conexao.execute(
            """
            SELECT *
            FROM company_knowledge_memory
            WHERE id = ?
            LIMIT 1
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _linha_para_facto(linha)


def save_company_source_raw_text(
    company_id: int,
    source: str,
    source_type: str,
    url: str,
    raw_text: str,
) -> None:
    texto = str(raw_text or "").strip()
    if not texto:
        return

    with closing(abrir_conexao()) as conexao:
        conexao.execute(
            """
            INSERT INTO company_source_raw_texts (
                company_id,
                source,
                source_type,
                url,
                raw_text
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(company_id, source)
            DO UPDATE SET
                source_type = excluded.source_type,
                url = excluded.url,
                raw_text = excluded.raw_text,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                company_id,
                str(source or "").strip(),
                str(source_type or "").strip() or None,
                str(url or "").strip() or None,
                texto,
            ),
        )
        conexao.commit()


def get_company_knowledge(company_id: int) -> list[KnowledgeFact]:
    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT *
            FROM company_knowledge_memory
            WHERE company_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (company_id,),
        ).fetchall()

    return [_linha_para_facto(linha) for linha in linhas]


def get_knowledge_by_field(
    company_id: int,
    field: str,
) -> list[KnowledgeFact]:
    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT *
            FROM company_knowledge_memory
            WHERE company_id = ?
              AND field = ?
            ORDER BY created_at ASC, id ASC
            """,
            (
                company_id,
                str(field or "").strip(),
            ),
        ).fetchall()

    return [_linha_para_facto(linha) for linha in linhas]


def apply_validation_answer(
    knowledge_fact_id: int,
    answer: Any,
) -> KnowledgeFact | None:
    """
    Atualiza um facto de conhecimento com base numa resposta de validação.

    Regras determinísticas:
    - confirmação aumenta a confiança e marca como confirmed;
    - negação marca como rejected;
    - resposta ambígua não altera nada.
    """
    classificacao = _classificar_resposta_validacao(answer)
    if classificacao is None:
        return None

    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT *
            FROM company_knowledge_memory
            WHERE id = ?
            LIMIT 1
            """,
            (knowledge_fact_id,),
        ).fetchone()

        if linha is None:
            return None

        facto_atual = _linha_para_facto(linha)
        if classificacao == "confirmed":
            novo_status = "confirmed"
            nova_confidence = min(
                1.0,
                max(float(facto_atual.confidence or 0.0), 0.85) + 0.05,
            )
        elif classificacao == "rejected":
            novo_status = "rejected"
            nova_confidence = min(float(facto_atual.confidence or 0.0), 0.2)
        else:
            return facto_atual

        conexao.execute(
            """
            UPDATE company_knowledge_memory
            SET status = ?,
                confidence = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                novo_status,
                nova_confidence,
                knowledge_fact_id,
            ),
        )
        conexao.commit()

        linha_atualizada = conexao.execute(
            """
            SELECT *
            FROM company_knowledge_memory
            WHERE id = ?
            LIMIT 1
            """,
            (knowledge_fact_id,),
        ).fetchone()

    return _linha_para_facto(linha_atualizada) if linha_atualizada else None

# CNLL_CV_ANALYSIS_V17_2
def upsert_knowledge_fact(
    company_id: int,
    field: str,
    value: Any,
    source: str = "",
    source_type: str = "",
    url: str = "",
    section: str = "",
    evidence_text: str = "",
    confidence: float = 0,
    status: str = "unknown",
) -> KnowledgeFact:
    """Mantém um único facto corrente por (empresa, campo)."""
    normalized_field = str(field or "").strip()
    if not normalized_field:
        raise ValueError("field é obrigatório")

    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")
        rows = conexao.execute(
            """
            SELECT id
            FROM company_knowledge_memory
            WHERE company_id = ? AND field = ?
            ORDER BY updated_at DESC, created_at DESC, id DESC
            """,
            (company_id, normalized_field),
        ).fetchall()

        if rows:
            keep_id = int(rows[0]["id"])
            conexao.execute(
                """
                UPDATE company_knowledge_memory
                SET value_json = ?,
                    source = ?,
                    source_type = ?,
                    url = ?,
                    section = ?,
                    evidence_text = ?,
                    confidence = ?,
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    _valor_para_json(value),
                    str(source or "").strip() or None,
                    str(source_type or "").strip() or None,
                    str(url or "").strip() or None,
                    str(section or "").strip() or None,
                    str(evidence_text or "").strip()[:2000] or None,
                    float(confidence or 0),
                    str(status or "unknown").strip() or "unknown",
                    keep_id,
                ),
            )
            duplicate_ids = [int(row["id"]) for row in rows[1:]]
            if duplicate_ids:
                placeholders = ",".join("?" for _ in duplicate_ids)
                conexao.execute(
                    f"DELETE FROM company_knowledge_memory WHERE id IN ({placeholders})",
                    duplicate_ids,
                )
        else:
            cursor = conexao.execute(
                """
                INSERT INTO company_knowledge_memory (
                    company_id, field, value_json, source, source_type,
                    url, section, evidence_text, confidence, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    normalized_field,
                    _valor_para_json(value),
                    str(source or "").strip() or None,
                    str(source_type or "").strip() or None,
                    str(url or "").strip() or None,
                    str(section or "").strip() or None,
                    str(evidence_text or "").strip()[:2000] or None,
                    float(confidence or 0),
                    str(status or "unknown").strip() or "unknown",
                ),
            )
            keep_id = int(cursor.lastrowid)

        conexao.commit()
        row = conexao.execute(
            "SELECT * FROM company_knowledge_memory WHERE id = ? LIMIT 1",
            (keep_id,),
        ).fetchone()

    return _linha_para_facto(row)


def delete_knowledge_by_field(company_id: int, field: str) -> int:
    normalized_field = str(field or "").strip()
    if not normalized_field:
        return 0
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            DELETE FROM company_knowledge_memory
            WHERE company_id = ? AND field = ?
            """,
            (company_id, normalized_field),
        )
        conexao.commit()
        return int(cursor.rowcount or 0)
