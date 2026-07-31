from __future__ import annotations

import re
import unicodedata
from contextlib import closing
from typing import Any
from urllib.parse import urlparse

from ..database import abrir_conexao


SUFIXOS_JURIDICOS = {
    "lda",
    "limitada",
    "unipessoal",
    "sociedade unipessoal",
    "sa",
    "s a",
    "ltd",
    "limited",
}


def _linha_para_dicionario(linha) -> dict[str, Any]:
    return dict(linha)


def normalizar_nome_pesquisa(valor: str | None) -> str:
    texto = str(valor or "").strip().lower()
    texto = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caractere)
    )
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    partes = [parte for parte in texto.split() if parte]

    while partes:
        sufixo_1 = partes[-1]
        sufixo_2 = " ".join(partes[-2:]) if len(partes) >= 2 else ""
        if sufixo_2 in SUFIXOS_JURIDICOS:
            partes = partes[:-2]
            continue
        if sufixo_1 in SUFIXOS_JURIDICOS:
            partes = partes[:-1]
            continue
        break

    return " ".join(partes)


def normalizar_dominio(valor: str | None) -> str:
    texto = str(valor or "").strip().lower()
    if not texto:
        return ""

    if "://" not in texto:
        texto = f"https://{texto}"

    dominio = urlparse(texto).netloc.lower()
    if dominio.startswith("www."):
        dominio = dominio[4:]
    return dominio


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


def obter_role_utilizador_empresa(
    company_id: int,
    user_id: str,
) -> str | None:
    if not user_id:
        return None

    with closing(abrir_conexao()) as conexao:
        empresa = conexao.execute(
            """
            SELECT owner_user_id
            FROM companies
            WHERE id = ?
            LIMIT 1
            """,
            (company_id,),
        ).fetchone()
        if empresa is None:
            return None

        if empresa["owner_user_id"] == user_id:
            return "owner"

        membro = conexao.execute(
            """
            SELECT role, status
            FROM company_members
            WHERE company_id = ?
              AND user_id = ?
            LIMIT 1
            """,
            (company_id, user_id),
        ).fetchone()

    if membro is None or membro["status"] != "active":
        return None
    return str(membro["role"] or "member").strip() or "member"


def utilizador_pode_gerir_membros(
    company_id: int,
    user_id: str,
) -> bool:
    return obter_role_utilizador_empresa(company_id, user_id) in {
        "owner",
        "admin",
    }


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


def pesquisar_empresas(
    query: str | None,
    website: str | None = None,
    user_id: str | None = None,
    limite: int = 10,
) -> list[dict[str, Any]]:
    chave_nome = normalizar_nome_pesquisa(query)
    dominio = normalizar_dominio(website)
    if not chave_nome and not dominio:
        return []

    with closing(abrir_conexao()) as conexao:
        linhas = conexao.execute(
            """
            SELECT
                c.id,
                c.name,
                c.website,
                c.owner_user_id,
                m.role AS requester_role,
                m.status AS requester_status
            FROM companies c
            LEFT JOIN company_members m
                ON m.company_id = c.id
               AND m.user_id = ?
            ORDER BY c.created_at DESC, c.id DESC
            """,
            (user_id or "",),
        ).fetchall()

    resultados: list[dict[str, Any]] = []
    vistos: set[int] = set()
    for linha in linhas:
        nome_empresa = str(linha["name"] or "")
        website_empresa = str(linha["website"] or "")
        nome_empresa_chave = normalizar_nome_pesquisa(nome_empresa)
        dominio_empresa = normalizar_dominio(website_empresa)

        nome_compativel = (
            bool(chave_nome)
            and (
                chave_nome == nome_empresa_chave
                or chave_nome in nome_empresa_chave
                or nome_empresa_chave in chave_nome
            )
        )
        dominio_compativel = bool(dominio) and dominio == dominio_empresa

        if not nome_compativel and not dominio_compativel:
            continue
        if int(linha["id"]) in vistos:
            continue

        estado = "not_associated"
        if linha["owner_user_id"] == user_id:
            estado = "owner"
        elif linha["requester_status"] == "active":
            estado = "member"

        resultados.append(
            {
                "id": linha["id"],
                "name": nome_empresa,
                "website": website_empresa,
                "association_status": estado,
            }
        )
        vistos.add(int(linha["id"]))
        if len(resultados) >= max(1, min(limite, 25)):
            break

    return resultados


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
) -> tuple[dict[str, Any], bool]:
    papeis_validos = str(role or "member").strip() or "member"

    with closing(abrir_conexao()) as conexao:
        existente = conexao.execute(
            """
            SELECT *
            FROM company_members
            WHERE company_id = ?
              AND user_id = ?
            LIMIT 1
            """,
            (company_id, user_id),
        ).fetchone()

        if existente is not None:
            return _linha_para_dicionario(existente), False

        cursor = conexao.execute(
            """
            INSERT INTO company_members (
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
            WHERE id = ?
            LIMIT 1
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _linha_para_dicionario(linha), True


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
