from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CompatibilityResult(BaseModel):
    matches: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


def _extrair_dict(valor: Any) -> dict[str, Any]:
    if valor is None:
        return {}
    if hasattr(valor, "model_dump"):
        return valor.model_dump()
    if isinstance(valor, dict):
        return dict(valor)
    return {}


def _texto_limpo(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def _normalizar(valor: Any) -> str:
    return _texto_limpo(valor).casefold()


def _lista_unica(valores: list[Any]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []

    for valor in valores:
        texto = _texto_limpo(valor)
        if not texto:
            continue
        chave = _normalizar(texto)
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(texto)

    return resultado


def _normalizar_lista(valor: Any) -> list[str]:
    if valor is None:
        return []

    if isinstance(valor, list):
        itens: list[Any] = []
        for item in valor:
            if isinstance(item, dict):
                for subvalor in item.values():
                    if isinstance(subvalor, list):
                        itens.extend(subvalor)
                    elif subvalor not in (None, ""):
                        itens.append(subvalor)
            elif item not in (None, ""):
                itens.append(item)
        return _lista_unica(itens)

    if isinstance(valor, dict):
        itens: list[Any] = []
        for subvalor in valor.values():
            if isinstance(subvalor, list):
                itens.extend(subvalor)
            elif subvalor not in (None, ""):
                itens.append(subvalor)
        return _lista_unica(itens)

    texto = _texto_limpo(valor)
    return [texto] if texto else []


def _contar_matches(
    company_values: list[str],
    competition_values: list[str],
) -> tuple[list[str], list[str]]:
    company_norm = {_normalizar(valor): valor for valor in company_values}
    competition_norm = {_normalizar(valor): valor for valor in competition_values}
    comuns = sorted(set(company_norm) & set(competition_norm))
    return [company_norm[chave] for chave in comuns], [
        competition_norm[chave] for chave in comuns
    ]


def _adicionar_evidencia(
    evidence: list[dict[str, Any]],
    *,
    field: str,
    company_values: list[str],
    competition_values: list[str],
    source: str,
) -> None:
    evidence.append(
        {
            "field": field,
            "company_values": list(company_values),
            "competition_values": list(competition_values),
            "source": source,
        }
    )


def _analise_lista(
    *,
    result: CompatibilityResult,
    field: str,
    company_values: list[str],
    competition_values: list[str],
    company_source: str,
    competition_source: str,
) -> None:
    if not competition_values:
        result.unknowns.append(f"competition.{field}")
        return

    if not company_values:
        result.unknowns.append(f"company.{field}")
        return

    matches_company, matches_competition = _contar_matches(
        company_values,
        competition_values,
    )
    if matches_company:
        result.matches.append(
            {
                "field": field,
                "company_values": matches_company,
                "competition_values": matches_competition,
                "status": "compatible",
            }
        )
        _adicionar_evidencia(
            result.evidence,
            field=field,
            company_values=matches_company,
            competition_values=matches_competition,
            source=f"{company_source} -> {competition_source}",
        )
        return

    result.gaps.append(
        {
            "field": field,
            "company_values": list(company_values),
            "competition_values": list(competition_values),
            "status": "no_evidence",
        }
    )
    _adicionar_evidencia(
        result.evidence,
        field=field,
        company_values=company_values,
        competition_values=competition_values,
        source=f"{company_source} vs {competition_source}",
    )


def _extrair_company_profile(company_context: dict[str, Any]) -> dict[str, Any]:
    company = company_context.get("company") or {}
    if isinstance(company, dict) and "profile" in company:
        profile = company.get("profile") or {}
        return profile if isinstance(profile, dict) else {}
    return company if isinstance(company, dict) else {}


def analyze_compatibility(
    company_context,
    competition_context,
) -> CompatibilityResult:
    """
    Compara contexto empresarial e contexto de concurso de forma
    determinística e explicável, sem calcular score.

    Futuro:
    - matching engine;
    - compatibility scoring;
    - recommendation system.
    """
    company_data = _extrair_dict(company_context)
    competition_data = _extrair_dict(competition_context)
    company_profile = _extrair_company_profile(company_data)
    company_intelligence = company_data.get("company", {}).get("intelligence", {})

    result = CompatibilityResult()

    company_competences = _normalizar_lista(company_profile.get("competences"))
    competition_competences = _normalizar_lista(
        competition_data.get("competences")
    )
    _analise_lista(
        result=result,
        field="competences",
        company_values=company_competences,
        competition_values=competition_competences,
        company_source="company.profile.competences",
        competition_source="competition.competences",
    )

    company_preferences = _normalizar_lista(
        (company_profile.get("preferences") or {}).get("typologies")
    )
    competition_typologies = _normalizar_lista(
        competition_data.get("typologies")
    )
    _analise_lista(
        result=result,
        field="preferences.typologies",
        company_values=company_preferences,
        competition_values=competition_typologies,
        company_source="company.profile.preferences.typologies",
        competition_source="competition.typologies",
    )

    project_experience = []
    for project in company_profile.get("project_experience") or []:
        if isinstance(project, dict):
            typology = _texto_limpo(project.get("typology"))
            if typology:
                project_experience.append(typology)
        else:
            typology = _texto_limpo(getattr(project, "typology", ""))
            if typology:
                project_experience.append(typology)
    project_experience = _lista_unica(project_experience)
    _analise_lista(
        result=result,
        field="project_experience.typologies",
        company_values=project_experience,
        competition_values=competition_typologies,
        company_source="company.profile.project_experience",
        competition_source="competition.typologies",
    )

    company_location = _texto_limpo(
        (company_profile.get("identity") or {}).get("location")
    )
    competition_location = _texto_limpo(competition_data.get("location"))
    if not competition_location:
        result.unknowns.append("competition.location")
    elif not company_location:
        result.unknowns.append("company.location")
    elif _normalizar(company_location) == _normalizar(competition_location):
        result.matches.append(
            {
                "field": "location",
                "company_values": [company_location],
                "competition_values": [competition_location],
                "status": "compatible",
            }
        )
        _adicionar_evidencia(
            result.evidence,
            field="location",
            company_values=[company_location],
            competition_values=[competition_location],
            source="company.profile.identity.location -> competition.location",
        )
    else:
        result.gaps.append(
            {
                "field": "location",
                "company_values": [company_location],
                "competition_values": [competition_location],
                "status": "no_match",
            }
        )
        _adicionar_evidencia(
            result.evidence,
            field="location",
            company_values=[company_location],
            competition_values=[competition_location],
            source="company.profile.identity.location vs competition.location",
        )

    # Informação contextual preservada para futuro uso em comparação
    # sem alterar a lógica determinística da análise atual.
    if company_intelligence:
        result.evidence.append(
            {
                "field": "company_intelligence",
                "company_values": [],
                "competition_values": [],
                "source": "company_context.company.intelligence",
            }
        )

    return result
