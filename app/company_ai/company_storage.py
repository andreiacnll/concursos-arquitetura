from __future__ import annotations

from contextlib import closing
from typing import Any

from ..database import abrir_conexao


def _linha_para_dicionario(linha) -> dict[str, Any]:
    return dict(linha)


def _obter_empresa_por_id(
    conexao,
    company_id: int,
) -> dict[str, Any] | None:
    linha = conexao.execute(
        """
        SELECT *
        FROM companies
        WHERE id = ?
        """,
        (company_id,),
    ).fetchone()
    return _linha_para_dicionario(linha) if linha else None


def obter_empresa_utilizador(user_id: str) -> dict[str, Any] | None:
    if not user_id:
        return None

    with closing(abrir_conexao()) as conexao:
        linha = conexao.execute(
            """
            SELECT c.*
            FROM companies c
            LEFT JOIN company_members m
                ON m.company_id = c.id
               AND m.user_id = ?
            WHERE c.owner_user_id = ?
               OR m.user_id = ?
            ORDER BY
                CASE
                    WHEN c.owner_user_id = ? THEN 0
                    ELSE 1
                END,
                c.id DESC
            LIMIT 1
            """,
            (user_id, user_id, user_id, user_id),
        ).fetchone()

    return _linha_para_dicionario(linha) if linha else None


def criar_empresa(
    user_id: str,
    name: str,
    website: str | None = None,
) -> dict[str, Any]:
    nome = str(name or "").strip()
    if not nome:
        raise ValueError("O nome da empresa é obrigatório.")

    site = str(website or "").strip() or None

    with closing(abrir_conexao()) as conexao:
        conexao.execute("BEGIN IMMEDIATE")

        existente = conexao.execute(
            """
            SELECT *
            FROM companies
            WHERE owner_user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if existente is not None:
            conexao.commit()
            return _linha_para_dicionario(existente)

        cursor = conexao.execute(
            """
            INSERT INTO companies (
                owner_user_id,
                name,
                website
            )
            VALUES (?, ?, ?)
            """,
            (user_id, nome, site),
        )

        company_id = cursor.lastrowid

        conexao.execute(
            """
            INSERT INTO company_members (
                company_id,
                user_id,
                role,
                status
            )
            VALUES (?, ?, 'owner', 'active')
            """,
            (company_id, user_id),
        )

        conexao.commit()

        return _obter_empresa_por_id(conexao, company_id) or {
            "id": company_id,
            "owner_user_id": user_id,
            "name": nome,
            "website": site,
        }


def adicionar_membro(
    company_id: int,
    user_id: str,
    role: str = "member",
) -> dict[str, Any]:
    papeis_validos = str(role or "member").strip() or "member"

    with closing(abrir_conexao()) as conexao:
        conexao.execute(
            """
            INSERT OR IGNORE INTO company_members (
                company_id,
                user_id,
                role,
                status
            )
            VALUES (?, ?, ?, 'active')
            """,
            (company_id, user_id, papeis_validos),
        )

        conexao.commit()

        linha = conexao.execute(
            """
            SELECT *
            FROM company_members
            WHERE company_id = ?
              AND user_id = ?
            LIMIT 1
            """,
            (company_id, user_id),
        ).fetchone()

    return _linha_para_dicionario(linha)


def listar_membros(company_id: int) -> list[dict[str, Any]]:
    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT *
            FROM company_members
            WHERE company_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (company_id,),
        ).fetchall()

    return [
        _linha_para_dicionario(linha)
        for linha in linhas
    ]
