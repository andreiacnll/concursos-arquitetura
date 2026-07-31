from __future__ import annotations

import json
from contextlib import closing
from typing import Any

from .models import CompanyMemory, CompanyProfile, CompanyPreferences
from ..database import abrir_conexao


def _perfil_vazio(company_id: int) -> CompanyProfile:
    return CompanyProfile(company_id=company_id)


def _carregar_json(valor: str | None) -> dict[str, Any]:
    if not valor:
        return {}

    try:
        dados = json.loads(valor)
    except json.JSONDecodeError:
        return {}

    return dados if isinstance(dados, dict) else {}


def _normalizar_perfil(
    company_id: int,
    perfil: dict[str, Any],
    strategy_json: str | None,
    ai_memory_json: str | None,
) -> CompanyProfile:
    dados = dict(perfil)
    dados["company_id"] = company_id
    dados["strategy"] = _carregar_json(strategy_json) or dados.get(
        "strategy",
        {
            "priority_areas": [],
            "secondary_areas": [],
            "avoid_areas": [],
            "future_goals": [],
        },
    )
    dados["ai_memory"] = _carregar_json(ai_memory_json) or dados.get(
        "ai_memory",
        CompanyMemory().model_dump(),
    )

    if "preferences" in dados and not isinstance(
        dados["preferences"],
        dict,
    ):
        dados["preferences"] = CompanyPreferences().model_dump()

    return CompanyProfile.model_validate(dados)


def obter_company_profile(company_id: int) -> CompanyProfile:
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT *
            FROM company_profiles
            WHERE company_id = ?
            LIMIT 1
            """,
            (company_id,),
        ).fetchone()

    if linha is None:
        return _perfil_vazio(company_id)

    dados_principais = _carregar_json(linha["profile_json"])
    return _normalizar_perfil(
        company_id,
        dados_principais,
        linha["strategy_json"],
        linha["ai_memory_json"],
    )


def guardar_company_profile(
    company_id: int,
    profile: CompanyProfile,
) -> CompanyProfile:
    perfil = profile.model_copy(deep=True)
    perfil.company_id = company_id

    dados_principais = perfil.model_dump(
        exclude={"strategy", "ai_memory"},
        exclude_none=True,
    )
    strategy_json = json.dumps(
        perfil.strategy,
        ensure_ascii=False,
    )
    ai_memory_json = json.dumps(
        perfil.ai_memory.model_dump(),
        ensure_ascii=False,
    )

    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")

        existente = conexao.execute(
            """
            SELECT id
            FROM company_profiles
            WHERE company_id = ?
            LIMIT 1
            """,
            (company_id,),
        ).fetchone()

        if existente is None:
            conexao.execute(
                """
                INSERT INTO company_profiles (
                    company_id,
                    profile_json,
                    strategy_json,
                    ai_memory_json,
                    completion_score
                )
                VALUES (?, ?, ?, ?, 0)
                """,
                (
                    company_id,
                    json.dumps(dados_principais, ensure_ascii=False),
                    strategy_json,
                    ai_memory_json,
                ),
            )
        else:
            conexao.execute(
                """
                UPDATE company_profiles
                SET profile_json = ?,
                    strategy_json = ?,
                    ai_memory_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE company_id = ?
                """,
                (
                    json.dumps(dados_principais, ensure_ascii=False),
                    strategy_json,
                    ai_memory_json,
                    company_id,
                ),
            )

        conexao.commit()

    return obter_company_profile(company_id)
