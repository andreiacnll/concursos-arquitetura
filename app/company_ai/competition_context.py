from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CompetitionContext(BaseModel):
    competition_id: int | None = None
    title: str = ""
    location: str = ""
    typologies: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    competences: list[str] = Field(default_factory=list)
    specializations: list[str] = Field(default_factory=list)
    scale: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    source_data: dict[str, Any] = Field(default_factory=dict)


def _texto_limpo(valor: Any) -> str:
    return " ".join(str(valor or "").strip().split())


def _lista_unica(valores: list[Any]) -> list[str]:
    vistos: set[str] = set()
    resultado: list[str] = []

    for valor in valores:
        texto = _texto_limpo(valor)
        if not texto:
            continue
        chave = texto.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(texto)

    return resultado


def _coletar_lista(*valores: Any) -> list[str]:
    itens: list[Any] = []
    for valor in valores:
        if isinstance(valor, dict):
            for item in valor.values():
                if isinstance(item, list):
                    itens.extend(item)
                elif item not in (None, ""):
                    itens.append(item)
        elif isinstance(valor, list):
            itens.extend(valor)
        elif valor not in (None, ""):
            itens.append(valor)
    return _lista_unica(itens)


def _extrair_dict(analysis_data: Any) -> dict[str, Any]:
    if analysis_data is None:
        return {}
    if hasattr(analysis_data, "model_dump"):
        return analysis_data.model_dump()
    if isinstance(analysis_data, dict):
        return dict(analysis_data)
    return {}


def _dicionario_seguro(valor: Any) -> dict[str, Any]:
    if isinstance(valor, dict):
        return dict(valor)
    return {}


def build_competition_context(
    analysis_data,
) -> CompetitionContext:
    """
    Normaliza a ficha de análise existente para um formato estável.

    Futuro:
    - matching engine;
    - compatibility scoring;
    - recommendation system.
    """
    data = _extrair_dict(analysis_data)

    identificacao = _dicionario_seguro(data.get("identificacao"))
    programa = _dicionario_seguro(data.get("programa"))
    programa_funcional = _dicionario_seguro(data.get("programa_funcional"))
    localizacao = _dicionario_seguro(data.get("localizacao"))
    entregaveis = _dicionario_seguro(data.get("entregaveis"))
    especialidades = _dicionario_seguro(data.get("especialidades"))
    requisitos = _dicionario_seguro(data.get("requisitos"))
    equipa = _dicionario_seguro(data.get("equipa"))
    estrategia = _dicionario_seguro(data.get("estrategia"))
    decisao = _dicionario_seguro(data.get("decisao"))
    investimento = _dicionario_seguro(data.get("investimento"))
    economia = _dicionario_seguro(data.get("economia"))

    title = (
        _texto_limpo(identificacao.get("titulo"))
        or _texto_limpo(data.get("titulo"))
    )
    location = (
        _texto_limpo(
            identificacao.get("localizacao")
            or identificacao.get("local")
            or localizacao.get("local")
            or localizacao.get("municipio")
            or localizacao.get("freguesia")
        )
    )

    typologies = _coletar_lista(
        programa.get("tipo"),
        programa.get("areas"),
        programa.get("usos"),
        especialidades.get("lista"),
        data.get("tipologias"),
    )

    requirements = _coletar_lista(
        programa.get("requisitos"),
        programa.get("condicionantes"),
        programa_funcional.get("requisitos"),
        requisitos.get("obrigatorios"),
        requisitos.get("requisitos"),
    )

    competences = _coletar_lista(
        equipa.get("competencias"),
        equipa.get("competences"),
        equipa.get("especialidades"),
        requisitos.get("competencias"),
        requisitos.get("competences"),
    )

    specializations = _coletar_lista(
        especialidades.get("lista"),
        equipa.get("especialidades"),
        equipa.get("subfatores"),
    )

    constraints = _coletar_lista(
        requisitos.get("riscos_participacao"),
        requisitos.get("restricoes"),
        programa.get("condicionantes"),
        decisao.get("riscos"),
    )

    scale = {
        "investment": {
            "value_obra": _texto_limpo(investimento.get("valor_obra")),
            "prazo_projeto": _texto_limpo(investimento.get("prazo_projeto")),
        },
        "economy": {
            "value_procedimento": _texto_limpo(
                economia.get("valor_procedimento")
            ),
            "value_estimado_obra": _texto_limpo(
                economia.get("valor_estimado_obra")
            ),
        },
        "decision": {
            "score": decisao.get("score"),
            "classificacao": _texto_limpo(decisao.get("classificacao")),
        },
    }

    source_data = {
        "identificacao": identificacao,
        "programa": programa,
        "programa_funcional": programa_funcional,
        "localizacao": localizacao,
        "investimento": investimento,
        "economia": economia,
        "criterios": data.get("criterios") or {},
        "documentos": data.get("documentos") or {},
        "entregaveis": entregaveis,
        "especialidades": especialidades,
        "requisitos": requisitos,
        "equipa": equipa,
        "estrategia": estrategia,
        "decisao": decisao,
        "analise_ai": data.get("analise_ai") or {},
    }

    return CompetitionContext(
        competition_id=identificacao.get("concurso_id") or data.get("competition_id"),
        title=title,
        location=location,
        typologies=typologies,
        requirements=requirements,
        competences=competences,
        specializations=specializations,
        scale=scale,
        constraints=constraints,
        source_data=source_data,
    )
