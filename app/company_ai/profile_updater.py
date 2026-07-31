from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import CompanyIdentity, CompanyProfile


_STRATEGY_KEYS = (
    "priority_areas",
    "secondary_areas",
    "avoid_areas",
    "future_goals",
)


def _texto_limpo(valor: Any) -> str:
    return str(valor or "").strip()


def _lista_de_texto(valor: Any) -> list[str]:
    if valor is None:
        return []

    if isinstance(valor, str):
        texto = valor.strip()
        return [texto] if texto else []

    if isinstance(valor, dict):
        resultado: list[str] = []
        for item in valor.values():
            resultado.extend(_lista_de_texto(item))
        return resultado

    if isinstance(valor, Iterable):
        resultado: list[str] = []
        for item in valor:
            resultado.extend(_lista_de_texto(item))
        return resultado

    texto = _texto_limpo(valor)
    return [texto] if texto else []


def _listas_unicas(*listas: Iterable[str]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []

    for lista in listas:
        for item in lista:
            texto = _texto_limpo(item)
            if not texto or texto in vistos:
                continue
            vistos.add(texto)
            resultado.append(texto)

    return resultado


def _mesclar_texto_existente(valor_atual: str, novo_valor: Any) -> str:
    texto_novo = _texto_limpo(novo_valor)
    if not texto_novo:
        return valor_atual

    texto_atual = _texto_limpo(valor_atual)
    if not texto_atual:
        return texto_novo

    if texto_novo.lower() in texto_atual.lower():
        return texto_atual

    return f"{texto_atual}; {texto_novo}"


def _aplicar_company_identity(
    identidade: CompanyIdentity,
    answer: Any,
) -> CompanyIdentity:
    dados = identidade.model_dump()

    if isinstance(answer, dict):
        for chave in ("company_name", "description", "location", "website"):
            novo_valor = _texto_limpo(answer.get(chave))
            if novo_valor:
                dados[chave] = (
                    _mesclar_texto_existente(dados.get(chave, ""), novo_valor)
                    if chave == "description"
                    else novo_valor
                )
    else:
        dados["description"] = _mesclar_texto_existente(
            dados.get("description", ""),
            answer,
        )

    return CompanyIdentity.model_validate(dados)


def _aplicar_company_services(
    serviços_existentes: list[str],
    answer: Any,
) -> list[str]:
    return _listas_unicas(
        serviços_existentes,
        _lista_de_texto(answer),
    )


def _aplicar_company_strategy(
    strategy: dict[str, list[str]],
    answer: Any,
) -> dict[str, list[str]]:
    resultado = {
        chave: _listas_unicas(strategy.get(chave, []))
        for chave in _STRATEGY_KEYS
    }

    if isinstance(answer, dict):
        for chave in _STRATEGY_KEYS:
            if chave in answer:
                resultado[chave] = _listas_unicas(
                    resultado[chave],
                    _lista_de_texto(answer.get(chave)),
                )
        return resultado

    resultado["priority_areas"] = _listas_unicas(
        resultado["priority_areas"],
        _lista_de_texto(answer),
    )
    return resultado


def _aplicar_team_competences(
    competences_existentes: list[str],
    answer: Any,
) -> list[str]:
    return _listas_unicas(
        competences_existentes,
        _lista_de_texto(answer),
    )


def apply_answer_to_profile(
    company_id: int,
    field: str,
    answer: Any,
) -> CompanyProfile:
    """
    Aplica uma resposta de entrevista ao profile da empresa.

    Esta camada é determinística e apenas faz merge de dados já
    estruturados. A persistência fica a cargo da camada chamadora.
    """
    from .profile_storage import obter_company_profile

    profile = obter_company_profile(company_id).model_copy(deep=True)

    if field == "company.identity":
        profile.identity = _aplicar_company_identity(profile.identity, answer)
    elif field == "company.services":
        profile.services = _aplicar_company_services(profile.services, answer)
    elif field == "company.strategy":
        profile.strategy = _aplicar_company_strategy(profile.strategy, answer)
    elif field == "team.competences":
        profile.competences = _aplicar_team_competences(
            profile.competences,
            answer,
        )

    return profile
