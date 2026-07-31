from __future__ import annotations

import json
from contextlib import closing
from typing import Any

from ..database import abrir_conexao


def _linha_para_dicionario(linha) -> dict[str, Any]:
    return dict(linha)


def _parse_json(valor: Any) -> Any:
    if valor in (None, ""):
        return None

    if isinstance(valor, (dict, list, int, float, bool)):
        return valor

    try:
        return json.loads(valor)
    except (TypeError, ValueError, json.JSONDecodeError):
        return valor


def create_interview_session(company_id: int) -> dict[str, Any]:
    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO company_interview_sessions (
                company_id,
                status
            )
            VALUES (?, 'active')
            """,
            (company_id,),
        )
        conexao.commit()

        linha = conexao.execute(
            """
            SELECT *
            FROM company_interview_sessions
            WHERE id = ?
            LIMIT 1
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _linha_para_dicionario(linha)


def get_active_interview_session(
    company_id: int,
) -> dict[str, Any] | None:
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT *
            FROM company_interview_sessions
            WHERE company_id = ?
              AND status = 'active'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (company_id,),
        ).fetchone()

    return _linha_para_dicionario(linha) if linha else None


def save_question(
    session_id: int,
    question: Any,
) -> dict[str, Any]:
    options = getattr(question, "options", [])
    question_source = str(
        getattr(question, "question_source", "discovery")
    ).strip() or "discovery"
    knowledge_fact_id = getattr(question, "knowledge_fact_id", None)
    source = str(getattr(question, "source", "")).strip()
    evidence = str(getattr(question, "evidence", "")).strip()
    confidence = float(getattr(question, "confidence", 0.0) or 0.0)
    suggested_answer = getattr(question, "suggested_answer", None)
    options_json = json.dumps(
        [
            option.model_dump() if hasattr(option, "model_dump") else option
            for option in options
        ],
        ensure_ascii=False,
    )

    with closing(abrir_conexao()) as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO company_interview_questions (
                session_id,
                field,
                question,
                question_type,
                priority,
                options_json,
                question_source,
                knowledge_fact_id,
                source,
                evidence,
                confidence,
                suggested_answer_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                str(getattr(question, "field", "")).strip(),
                str(getattr(question, "question", "")).strip(),
                str(getattr(question, "type", "")).strip(),
                str(getattr(question, "priority", "")).strip(),
                options_json,
                question_source,
                knowledge_fact_id,
                source or None,
                evidence or None,
                confidence,
                json.dumps(suggested_answer, ensure_ascii=False),
            ),
        )
        conexao.commit()

        linha = conexao.execute(
            """
            SELECT *
            FROM company_interview_questions
            WHERE id = ?
            LIMIT 1
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _linha_para_dicionario(linha)


def save_answer(
    question_id: int,
    answer: Any,
) -> dict[str, Any]:
    with closing(abrir_conexao()) as conexao:
        conexao.execute(
            """
            INSERT INTO company_interview_answers (
                question_id,
                answer_json
            )
            VALUES (?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                answer_json = excluded.answer_json
            """,
            (
                question_id,
                json.dumps(answer, ensure_ascii=False),
            ),
        )
        conexao.commit()

        linha = conexao.execute(
            """
            SELECT *
            FROM company_interview_answers
            WHERE question_id = ?
            LIMIT 1
            """,
            (question_id,),
        ).fetchone()

    return _linha_para_dicionario(linha)


def get_question_answer(
    question_id: int,
) -> dict[str, Any] | None:
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT
                id,
                question_id,
                answer_json,
                created_at
            FROM company_interview_answers
            WHERE question_id = ?
            LIMIT 1
            """,
            (question_id,),
        ).fetchone()

    if linha is None:
        return None

    resposta = _linha_para_dicionario(linha)
    resposta["answer"] = _parse_json(resposta.pop("answer_json", None))
    return resposta


def get_session_questions(session_id: int) -> list[dict[str, Any]]:
    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT
                q.id,
                q.session_id,
                q.field,
                q.question,
                q.question_type,
                q.priority,
                q.options_json,
                q.question_source,
                q.knowledge_fact_id,
                q.source,
                q.evidence,
                q.confidence,
                q.suggested_answer_json,
                q.created_at,
                a.id AS answer_id,
                a.answer_json,
                a.created_at AS answer_created_at
            FROM company_interview_questions q
            LEFT JOIN company_interview_answers a
                ON a.question_id = q.id
            WHERE q.session_id = ?
            ORDER BY q.created_at ASC, q.id ASC
            """,
            (session_id,),
        ).fetchall()

    return [
        {
            "id": linha["id"],
            "session_id": linha["session_id"],
            "field": linha["field"],
            "question": linha["question"],
            "question_type": linha["question_type"],
            "priority": linha["priority"],
            "options": _parse_json(linha["options_json"]) or [],
            "question_source": linha["question_source"] or "discovery",
            "knowledge_fact_id": linha["knowledge_fact_id"],
            "source": linha["source"],
            "evidence": linha["evidence"],
            "confidence": linha["confidence"],
            "suggested_answer": _parse_json(linha["suggested_answer_json"]),
            "created_at": linha["created_at"],
            "answer": _parse_json(linha["answer_json"]),
            "answer_created_at": linha["answer_created_at"],
            "answer_id": linha["answer_id"],
        }
        for linha in linhas
    ]


def get_question_context(
    question_id: int,
) -> dict[str, Any] | None:
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT
                q.id AS question_id,
                q.session_id,
                q.field,
                q.question,
                q.question_type,
                q.priority,
                q.options_json,
                q.question_source,
                q.knowledge_fact_id,
                q.source,
                q.evidence,
                q.confidence,
                q.suggested_answer_json,
                s.company_id,
                s.status
            FROM company_interview_questions q
            JOIN company_interview_sessions s
                ON s.id = q.session_id
            WHERE q.id = ?
            LIMIT 1
            """,
            (question_id,),
        ).fetchone()

    if linha is None:
        return None

    contexto = _linha_para_dicionario(linha)
    contexto["options"] = _parse_json(contexto.pop("options_json", None)) or []
    contexto["question_source"] = contexto.get("question_source") or "discovery"
    contexto["suggested_answer"] = _parse_json(
        contexto.pop("suggested_answer_json", None)
    )
    return contexto
