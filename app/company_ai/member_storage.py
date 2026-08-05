from __future__ import annotations

import json
from contextlib import closing
from typing import Any

from ..database import abrir_conexao
from .models import MemberProfile


def _carregar_json(valor: str | None) -> dict[str, Any]:
    if not valor:
        return {}

    try:
        dados = json.loads(valor)
    except json.JSONDecodeError:
        return {}

    return dados if isinstance(dados, dict) else {}


def _perfil_vazio(member_id: int) -> MemberProfile:
    return MemberProfile(member_id=member_id)


def _normalizar_member_profile(linha: Any) -> MemberProfile:
    return MemberProfile.model_validate(
        {
            "id": linha["id"],
            "member_id": linha["member_id"],
            "identity": _carregar_json(linha["identity_json"]),
            "experience": _carregar_json(linha["experience_json"]),
            "competences": _carregar_json(linha["competences_json"]),
            "preferences": _carregar_json(linha["preferences_json"]),
            "goals": _carregar_json(linha["goals_json"]),
            "visibility": _carregar_json(linha["visibility_json"]),
        }
    )


def obter_member_profile(member_id: int) -> MemberProfile:
    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT *
            FROM member_profiles
            WHERE member_id = ?
            LIMIT 1
            """,
            (member_id,),
        ).fetchone()

    if linha is None:
        return _perfil_vazio(member_id)

    return _normalizar_member_profile(linha)


def guardar_member_profile(
    member_id: int,
    profile: MemberProfile,
) -> MemberProfile:
    perfil = profile.model_copy(deep=True)
    perfil.member_id = member_id

    identidade_json = json.dumps(
        perfil.identity.model_dump(),
        ensure_ascii=False,
    )
    experiencia_json = json.dumps(
        perfil.experience.model_dump(),
        ensure_ascii=False,
    )
    competences_json = json.dumps(
        perfil.competences.model_dump(),
        ensure_ascii=False,
    )
    preferences_json = json.dumps(
        perfil.preferences.model_dump(),
        ensure_ascii=False,
    )
    goals_json = json.dumps(
        perfil.goals.model_dump(),
        ensure_ascii=False,
    )
    visibility_json = json.dumps(
        perfil.visibility.model_dump(),
        ensure_ascii=False,
    )

    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")

        existente = conexao.execute(
            """
            SELECT id
            FROM member_profiles
            WHERE member_id = ?
            LIMIT 1
            """,
            (member_id,),
        ).fetchone()

        if existente is None:
            conexao.execute(
                """
                INSERT INTO member_profiles (
                    member_id,
                    identity_json,
                    experience_json,
                    competences_json,
                    preferences_json,
                    goals_json,
                    visibility_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member_id,
                    identidade_json,
                    experiencia_json,
                    competences_json,
                    preferences_json,
                    goals_json,
                    visibility_json,
                ),
            )
        else:
            conexao.execute(
                """
                UPDATE member_profiles
                SET identity_json = ?,
                    experience_json = ?,
                    competences_json = ?,
                    preferences_json = ?,
                    goals_json = ?,
                    visibility_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE member_id = ?
                """,
                (
                    identidade_json,
                    experiencia_json,
                    competences_json,
                    preferences_json,
                    goals_json,
                    visibility_json,
                    member_id,
                ),
            )

        conexao.commit()

    return obter_member_profile(member_id)


def criar_member_profile(member_id: int) -> MemberProfile:
    perfil_existente = obter_member_profile(member_id)

    if perfil_existente.id is not None:
        return perfil_existente

    return guardar_member_profile(
        member_id,
        MemberProfile(member_id=member_id),
    )
