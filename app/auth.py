from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent.parent

# Em produção prevalecem sempre as variáveis do ambiente. Em
# desenvolvimento local, o frontend e a API partilham a configuração
# Supabase já existente no projeto.
load_dotenv(BASE_DIR / ".env", override=False, encoding="utf-8-sig")
load_dotenv(
    BASE_DIR / "frontend" / ".env.local",
    override=False,
    encoding="utf-8-sig",
)


class UtilizadorAutenticado(BaseModel):
    id: str
    email: str | None = None


bearer_scheme = HTTPBearer(auto_error=False)


def _configuracao_supabase() -> tuple[str, str]:
    def env(nome: str) -> str:
        return (
            os.getenv(nome)
            or os.getenv(f"\ufeff{nome}")
            or ""
        ).strip()

    url = (
        env("SUPABASE_URL")
        or env("NEXT_PUBLIC_SUPABASE_URL")
    )
    chave = (
        env("SUPABASE_PUBLISHABLE_KEY")
        or env("SUPABASE_ANON_KEY")
        or env("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )

    if not url or not chave:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A validação de utilizadores não está configurada.",
        )

    return url.rstrip("/"), chave


def obter_utilizador_atual(
    credenciais: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> UtilizadorAutenticado:
    if (
        credenciais is None
        or credenciais.scheme.lower() != "bearer"
        or not credenciais.credentials
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase_url, supabase_key = _configuracao_supabase()

    try:
        resposta = requests.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "apikey": supabase_key,
                "Authorization": (
                    f"Bearer {credenciais.credentials}"
                ),
            },
            timeout=10,
        )
    except requests.RequestException as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível validar a sessão.",
        ) from erro

    if resposta.status_code in (401, 403):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if resposta.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O serviço de autenticação está indisponível.",
        )

    try:
        dados = resposta.json()
    except ValueError as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resposta inválida do serviço de autenticação.",
        ) from erro

    user_id = str(dados.get("id") or "").strip()

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão sem utilizador válido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UtilizadorAutenticado(
        id=user_id,
        email=dados.get("email"),
    )
