from __future__ import annotations

import json
from contextlib import closing
from typing import Any

from ..database import abrir_conexao
from .models import CompanyProfile
from .profile_storage import guardar_company_profile, obter_company_profile


def _parse_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _source_label(source_type: str) -> str:
    if source_type == "website":
        return "Website"
    if source_type == "portfolio":
        return "Portfolio"
    if source_type == "document":
        return "Documentos institucionais"
    if source_type == "interview":
        return "Entrevista"
    return source_type or "Fonte"


def _source_name(source: str, source_type: str) -> str:
    prefix = f"{source_type}:"
    if source.startswith(prefix):
        return source[len(prefix) :].strip() or source
    if ":" in source:
        return source.split(":", 1)[1].strip() or source
    return source or _source_label(source_type)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _value_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _values_for_rows(rows: list[Any]) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    for row in rows:
        field = str(row["field"] or "").strip()
        parsed = _parse_json(row["value_json"])
        values.setdefault(field, set()).update(
            _value_key(item) for item in _as_list(parsed)
        )
    return values


def _remove_unsupported_values(
    current: list[str],
    removed: set[str],
    still_supported: set[str],
) -> list[str]:
    result: list[str] = []
    for value in current:
        key = _value_key(value)
        if key in removed and key not in still_supported:
            continue
        result.append(value)
    return result


def _remove_source_values_from_profile(
    company_id: int,
    removed_rows: list[Any],
) -> CompanyProfile:
    with closing(abrir_conexao()) as conexao:
        remaining_rows = conexao.execute(
            """
            SELECT field, value_json
            FROM company_knowledge_memory
            WHERE company_id = ?
              AND COALESCE(status, '') != 'rejected'
            """,
            (company_id,),
        ).fetchall()

    removed = _values_for_rows(removed_rows)
    remaining = _values_for_rows(remaining_rows)
    profile = obter_company_profile(company_id).model_copy(deep=True)

    profile.services = _remove_unsupported_values(
        profile.services,
        removed.get("company.services", set()),
        remaining.get("company.services", set()),
    )
    profile.competences = _remove_unsupported_values(
        profile.competences,
        removed.get("company.competences", set()),
        remaining.get("company.competences", set()),
    )

    removed_projects = removed.get("projects.items", set())
    supported_projects = remaining.get("projects.items", set())
    removed_typologies = removed.get("projects.typologies", set())
    supported_typologies = remaining.get("projects.typologies", set())
    profile.project_experience = [
        project
        for project in profile.project_experience
        if not (
            (
                _value_key(project.name) in removed_projects
                and _value_key(project.name) not in supported_projects
            )
            or (
                _value_key(project.typology) in removed_typologies
                and _value_key(project.typology) not in supported_typologies
            )
        )
    ]

    return guardar_company_profile(company_id, profile)


def list_company_sources(company_id: int) -> list[dict[str, Any]]:
    with closing(abrir_conexao()) as conexao:
        rows = conexao.execute(
            """
            SELECT
                source_type,
                source,
                field,
                value_json,
                MIN(created_at) AS submitted_at,
                COUNT(*) AS facts_count
            FROM company_knowledge_memory
            WHERE company_id = ?
              AND COALESCE(status, '') != 'rejected'
              AND COALESCE(source_type, '') != ''
            GROUP BY source_type, source, field, value_json
            ORDER BY submitted_at ASC
            """,
            (company_id,),
        ).fetchall()

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        source_type = str(row["source_type"] or "").strip()
        source = str(row["source"] or "").strip()
        if not source_type or not source:
            continue
        key = (source_type, source)
        item = grouped.setdefault(
            key,
            {
                "key": f"{source_type}:{source}",
                "label": _source_label(source_type),
                "source_type": source_type,
                "source": source,
                "name": _source_name(source, source_type),
                "origin": source,
                "status": "processed",
                "submitted_at": row["submitted_at"],
                "facts_count": 0,
                "projects_count": 0,
                "projects_found": [],
                "services_found": [],
                "competences_found": [],
                "warnings": [],
            },
        )
        item["facts_count"] += int(row["facts_count"] or 0)
        value = _parse_json(row["value_json"])
        if row["field"] == "projects.items":
            projects = _as_list(value)
            item["projects_found"].extend(projects)
            item["projects_count"] = len(
                {project.lower() for project in item["projects_found"]}
            )
        elif row["field"] == "company.services":
            item["services_found"].extend(_as_list(value))
        elif row["field"] == "company.competences":
            item["competences_found"].extend(_as_list(value))

    for item in grouped.values():
        for field_name in ("projects_found", "services_found", "competences_found"):
            seen: set[str] = set()
            unique: list[str] = []
            for value in item[field_name]:
                text = str(value or "").strip()
                key = text.lower()
                if not text or key in seen:
                    continue
                seen.add(key)
                unique.append(text)
            item[field_name] = unique
        if item["facts_count"] <= 0:
            item["status"] = "no_results"

    return list(grouped.values())


def delete_company_source(
    company_id: int,
    source_type: str,
    source: str,
) -> int:
    with closing(abrir_conexao()) as conexao:
        removed_rows = conexao.execute(
            """
            SELECT field, value_json
            FROM company_knowledge_memory
            WHERE company_id = ?
              AND source_type = ?
              AND source = ?
            """,
            (
                company_id,
                str(source_type or "").strip(),
                str(source or "").strip(),
            ),
        ).fetchall()
        cursor = conexao.execute(
            """
            DELETE FROM company_knowledge_memory
            WHERE company_id = ?
              AND source_type = ?
              AND source = ?
            """,
            (
                company_id,
                str(source_type or "").strip(),
                str(source or "").strip(),
            ),
        )
        conexao.execute(
            """
            DELETE FROM company_source_raw_texts
            WHERE company_id = ?
              AND source = ?
            """,
            (
                company_id,
                str(source or "").strip(),
            ),
        )
        conexao.commit()
        deleted = int(cursor.rowcount or 0)

    _remove_source_values_from_profile(company_id, removed_rows)
    return deleted
