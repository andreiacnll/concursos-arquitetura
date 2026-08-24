from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from .company_storage import listar_membros
from .member_storage import obter_member_profile
from .profile_storage import obter_company_profile
from .taxonomy import TYPOLOGY_TAXONOMY, normalize_concept


def _lista_unica(valores: list[str]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []

    for valor in valores:
        texto = str(valor).strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        resultado.append(texto)

    return resultado


def _texto_limpo(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def _normalizar_tipologia(valor: Any) -> str:
    tipologia = _texto_limpo(
        normalize_concept(valor, TYPOLOGY_TAXONOMY)
    )
    if tipologia.casefold() in CANONICAL_TYPOLOGY_KEYS:
        return tipologia
    return ""


def _chave_projeto(
    nome: Any,
    localizacao: Any,
    tipologia: Any,
) -> str:
    return "|".join(
        [
            _texto_limpo(nome).casefold(),
            _texto_limpo(localizacao).casefold(),
            _normalizar_tipologia(tipologia).casefold(),
        ]
    )


CANONICAL_TYPOLOGY_KEYS = {
    key.casefold()
    for key in TYPOLOGY_TAXONOMY
}

PROJECT_NOISE_PATTERNS = [
    r"back to top",
    r"\bnews\b",
    r"\bprofile\b",
    r"\bpublications?\b",
    r"\bhome\b",
    r"\bmenu\b",
    r"\bcontact\b",
    r"\bsearch\b",
    r"\bgo\b",
    r"more on",
    r"find more",
    r"saiba mais",
    r"click here to learn more",
    r"in architecture - da representacao ao projeto",
    r"the sensorial architect",
    r"nuno lacerda",
    r"architecture & design",
]


def _esta_ruido_projeto(texto: str) -> bool:
    texto_normalizado = _texto_limpo(texto).casefold()
    if not texto_normalizado:
        return True
    return any(
        re.search(pattern, texto_normalizado)
        for pattern in PROJECT_NOISE_PATTERNS
    )


def _is_placeholder_project(
    nome: Any,
    tipologia: Any,
    localizacao: Any,
    skills: list[str],
) -> bool:
    nome_texto = _texto_limpo(nome)
    tipologia_texto = _texto_limpo(tipologia)
    if not nome_texto and not tipologia_texto:
        return True
    if _esta_ruido_projeto(nome_texto):
        return True
    if nome_texto and tipologia_texto:
        if _texto_limpo(nome_texto).casefold() == _texto_limpo(tipologia_texto).casefold():
            if not _texto_limpo(localizacao) and not skills:
                return True
    if _texto_limpo(nome_texto).casefold() in CANONICAL_TYPOLOGY_KEYS:
        if not _texto_limpo(localizacao) and not skills:
            return True
    return False


def _inferir_tipologia_projeto(*valores: Any) -> str:
    for valor in valores:
        tipologia = _normalizar_tipologia(valor)
        if tipologia and tipologia.casefold() in CANONICAL_TYPOLOGY_KEYS:
            return tipologia
    return ""


def _separar_valores_tipologia(valor: Any) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set)):
        resultado: list[str] = []
        for item in valor:
            resultado.extend(_separar_valores_tipologia(item))
        return resultado
    texto = _texto_limpo(valor)
    if not texto:
        return []
    return [
        parte.strip()
        for parte in re.split(r"[,;/+|]|\s+ e \s+", texto)
        if parte.strip()
    ] or [texto]


def _inferir_tipologias_projeto(*valores: Any) -> list[str]:
    tipologias: list[str] = []
    for valor in valores:
        for candidato in _separar_valores_tipologia(valor):
            tipologia = _inferir_tipologia_projeto(candidato)
            if tipologia:
                tipologias.append(tipologia)
    return _lista_unica(tipologias)


def classificar_tipologia_projeto(*valores: Any) -> str:
    return _inferir_tipologia_projeto(*valores)


def _iterar_projetos_reais(company_profile, members):
    for project in company_profile.project_experience:
        skills = list(getattr(project, "skills_demonstrated", []) or [])
        nome = getattr(project, "name", "")
        tipologia_original = getattr(project, "typology", "")
        localizacao = getattr(project, "location", "")
        tipologias = _inferir_tipologias_projeto(
            getattr(project, "normalized_typology", ""),
            tipologia_original,
            getattr(project, "original_typology", ""),
            nome,
            skills,
        )
        if _is_placeholder_project(nome, tipologia_original, localizacao, skills):
            continue
        if not tipologias:
            continue

        for tipologia in tipologias:
            yield {
                "name": _texto_limpo(nome),
                "typology": tipologia,
                "original_typology": _texto_limpo(tipologia_original),
                "normalized_typology": tipologia,
                "location": _texto_limpo(localizacao),
                "skills_demonstrated": skills,
                "source": "company_profile",
            }

    for member in members:
        member_profile = obter_member_profile(member["id"])
        for project_name in member_profile.experience.projects:
            nome = _texto_limpo(project_name)
            tipologias = _inferir_tipologias_projeto(nome)
            if _is_placeholder_project(nome, "", "", []):
                continue
            if not tipologias:
                continue
            for tipologia in tipologias:
                yield {
                    "name": nome,
                    "typology": tipologia,
                    "original_typology": "",
                    "normalized_typology": tipologia,
                    "location": "",
                    "skills_demonstrated": [],
                    "source": "member_profile",
                    "member_id": member["id"],
                    "user_id": member["user_id"],
                }


def _esta_vazio_texto(valor: Any) -> bool:
    return not str(valor or "").strip()


def _calcular_confianca(total: int, preenchidos: int) -> float:
    if total <= 0:
        return 0.0
    return round(max(0.0, min(1.0, preenchidos / total)), 2)


def _perfil_empresa_vazio(company_profile) -> bool:
    identidade = company_profile.identity.model_dump()
    return (
        all(_esta_vazio_texto(valor) for valor in identidade.values())
        and not company_profile.services
        and not company_profile.competences
        and not getattr(company_profile, "specializations", [])
        and not company_profile.project_experience
        and not any(company_profile.strategy.values())
    )


def _resumir_identidade_empresa(company_profile) -> dict[str, Any]:
    return company_profile.identity.model_dump()


def _resumir_estrategia(company_profile) -> dict[str, Any]:
    return {
        "priority_areas": _lista_unica(
            list(company_profile.strategy.get("priority_areas", []))
        ),
        "secondary_areas": _lista_unica(
            list(company_profile.strategy.get("secondary_areas", []))
        ),
        "avoid_areas": _lista_unica(
            list(company_profile.strategy.get("avoid_areas", []))
        ),
        "future_goals": _lista_unica(
            list(company_profile.strategy.get("future_goals", []))
        ),
    }


def _resumir_projetos(company_profile, members) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    typologies: list[str] = []
    vistos: set[str] = set()

    for project in _iterar_projetos_reais(company_profile, members):
        typology = _normalizar_tipologia(project.get("normalized_typology") or project.get("typology"))
        chave = _chave_projeto(
            project.get("name"),
            project.get("location"),
            typology,
        )
        if chave in vistos:
            continue
        vistos.add(chave)
        if typology:
            typologies.append(typology)

        items.append(
            {
                "name": project.get("name"),
                "typology": typology or _texto_limpo(project.get("typology")),
                "original_typology": _texto_limpo(project.get("original_typology")),
                "normalized_typology": typology,
                "location": project.get("location"),
                "skills_demonstrated": list(project.get("skills_demonstrated") or []),
                "source": project.get("source") or "company_profile",
            }
        )

    return items, _lista_unica(typologies)


def _nivel_experiencia(project_count: int) -> tuple[str, int]:
    if project_count >= 20:
        return "Especialista", 5
    if project_count >= 10:
        return "Forte", 4
    if project_count >= 4:
        return "Consistente", 3
    if project_count >= 1:
        return "Pontual", 2
    return "Not Found", 0


def _resumir_experiencia_projetos(
    company_profile,
    members,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    counters: dict[str, int] = defaultdict(int)
    evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_projects: set[str] = set()

    for project in _iterar_projetos_reais(company_profile, members):
        typology = _normalizar_tipologia(project.get("normalized_typology") or project.get("typology"))
        if not typology:
            continue
        key = typology.lower()
        project_key = _chave_projeto(
            project.get("name"),
            project.get("location"),
            typology,
        )
        if project_key in seen_projects:
            continue
        seen_projects.add(project_key)
        counters[key] += 1
        evidence[key].append(
            {
                "name": _texto_limpo(project.get("name")),
                "location": _texto_limpo(project.get("location")),
                "source": project.get("source") or "company_profile",
                "normalized_typology": typology,
                "original_typology": _texto_limpo(project.get("original_typology")),
                "skills_demonstrated": list(project.get("skills_demonstrated") or []),
            }
        )

    summary: list[dict[str, Any]] = []
    for key, count in sorted(counters.items(), key=lambda item: (-item[1], item[0])):
        level, level_score = _nivel_experiencia(count)
        summary.append(
            {
                "typology": key,
                "project_count": count,
                "experience_level": level,
                "experience_level_score": level_score,
                "origins": _lista_unica(
                    [item["source"] for item in evidence.get(key, []) if item.get("source")]
                ) or ["company_profile"],
                "confidence": min(0.95, 0.45 + (count * 0.03)),
                "projects": evidence.get(key, []),
            }
        )

    return summary, dict(counters)


def _resumir_equipa(members, company_profile=None) -> dict[str, Any]:
    team_competences: list[str] = []
    team_experience: list[dict[str, Any]] = []
    specializations: list[str] = []

    if company_profile is not None:
        specializations.extend(
            getattr(company_profile, "specializations", []) or []
        )

    for member in members:
        member_profile = obter_member_profile(member["id"])

        competencias = _lista_unica(
            [
                *member_profile.competences.technical,
                *member_profile.competences.software,
                *member_profile.competences.methodologies,
            ]
        )
        if competencias:
            team_competences.extend(competencias)

        experiencia = _lista_unica(
            [
                *member_profile.experience.projects,
                *member_profile.experience.typologies,
                *member_profile.experience.sectors,
                *member_profile.experience.responsibilities,
            ]
        )
        if experiencia:
            team_experience.append(
                {
                    "member_id": member["id"],
                    "user_id": member["user_id"],
                    "role": member["role"],
                    "experience": experiencia,
                }
            )

        especializacao = str(
            member_profile.identity.specialization or ""
        ).strip()
        if especializacao:
            specializations.append(especializacao)

    return {
        "member_count": len(members),
        "competences": _lista_unica(team_competences),
        "experience": team_experience,
        "specializations": _lista_unica(specializations),
    }


def _calcular_missing_information(
    *,
    company_profile,
    company_block: dict[str, Any],
    team_block: dict[str, Any],
    projects_block: dict[str, Any],
) -> list[str]:
    missing: list[str] = []

    if _perfil_empresa_vazio(company_profile) or not company_block["services"]:
        missing.append("company.services")
    if not company_block["competences"]:
        missing.append("company.competences")
    if all(_esta_vazio_texto(valor) for valor in company_block["identity"].values()):
        missing.append("company.identity")
    if not any(company_block["strategy"].values()):
        missing.append("company.strategy")

    if not team_block["competences"]:
        missing.append("team.competences")
    if not team_block["experience"]:
        missing.append("team.experience")
    if not team_block["specializations"]:
        missing.append("team.specializations")

    if not projects_block["items"]:
        missing.append("projects.items")
    if not projects_block["typologies"]:
        missing.append("projects.typologies")

    return missing


def build_company_intelligence(company_id: int) -> dict[str, Any]:
    """
    Agregação determinística da inteligência da empresa.

    Futuro: esta camada será consumida pelo interviewer, matching engine,
    response generator e knowledge base.
    """
    company_profile = obter_company_profile(company_id)
    members = listar_membros(company_id)

    company_block = {
        "identity": _resumir_identidade_empresa(company_profile),
        "services": _lista_unica(list(company_profile.services)),
        "competences": _lista_unica(list(company_profile.competences)),
        "strategy": _resumir_estrategia(company_profile),
    }

    team_block = _resumir_equipa(members, company_profile)
    projects_items, projects_typologies = _resumir_projetos(
        company_profile,
        members,
    )
    projects_summary, project_counts_by_typology = _resumir_experiencia_projetos(
        company_profile,
        members,
    )

    sources: list[dict[str, Any]] = [
        {
            "type": "company_profile",
            "company_id": company_id,
        }
    ]
    sources.extend(
        {
            "type": "company_member",
            "member_id": member["id"],
            "user_id": member["user_id"],
            "role": member["role"],
        }
        for member in members
    )

    knowledge = {
        "sources": sources,
        "confidence": {
            "company": _calcular_confianca(
                4,
                sum(
                    1
                    for valor in company_block["identity"].values()
                    if not _esta_vazio_texto(valor)
                )
                + int(bool(company_block["services"]))
                + int(bool(company_block["competences"]))
                + int(bool(any(company_block["strategy"].values()))),
            ),
            "team": _calcular_confianca(
                3,
                int(bool(team_block["competences"]))
                + int(bool(team_block["experience"]))
                + int(bool(team_block["specializations"])),
            ),
            "projects": _calcular_confianca(
                2,
                int(bool(projects_items)) + int(bool(projects_typologies)),
            ),
        },
    }
    knowledge["missing_information"] = _calcular_missing_information(
        company_profile=company_profile,
        company_block=company_block,
        team_block=team_block,
        projects_block={
            "items": projects_items,
            "typologies": projects_typologies,
        },
    )

    return {
        "company": {
            "identity": company_block["identity"],
            "services": company_block["services"],
            "competences": company_block["competences"],
            "strategy": company_block["strategy"],
        },
        "team": team_block,
        "projects": {
            "items": projects_items,
            "typologies": projects_typologies,
            "summary": projects_summary,
            "counts_by_typology": project_counts_by_typology,
        },
        "knowledge": knowledge,
    }
