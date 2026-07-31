from __future__ import annotations

from typing import Any

from .company_extractor import CompanyExtractionResult, ExtractedFact
from .models import CompanyIdentity, CompanyProfile, CompanyProjectExperience


_FACTOS_VALIDOS = {"confirmed"}


def _texto_limpo(valor: Any) -> str:
    return str(valor or "").strip()


def _normalizar_texto(valor: Any) -> str:
    return " ".join(_texto_limpo(valor).split())


def _lista_unica(valores: list[str]) -> list[str]:
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


def _formatar_lista_legivel(valores: list[str]) -> str:
    itens = _lista_unica(valores)
    if not itens:
        return ""
    if len(itens) == 1:
        return itens[0]
    if len(itens) == 2:
        return f"{itens[0]} e {itens[1]}"
    return ", ".join(itens[:-1]) + f" e {itens[-1]}"


def _limitar_palavras(texto: str, minimo: int = 60, maximo: int = 120) -> str:
    palavras = _normalizar_texto(texto).split()
    if not palavras:
        return ""

    if len(palavras) > maximo:
        palavras = palavras[:maximo]
        resultado = " ".join(palavras).rstrip(",; ")
        if resultado and resultado[-1] not in ".!?":
            resultado += "."
        return resultado

    if len(palavras) < minimo:
        return " ".join(palavras)

    return " ".join(palavras)


def _valor_em_lista(fact: ExtractedFact) -> list[str]:
    valor = fact.value
    if isinstance(valor, list):
        return [_texto_limpo(item) for item in valor if _texto_limpo(item)]
    if isinstance(valor, tuple):
        return [_texto_limpo(item) for item in valor if _texto_limpo(item)]
    if isinstance(valor, set):
        return [_texto_limpo(item) for item in valor if _texto_limpo(item)]
    texto = _texto_limpo(valor)
    return [texto] if texto else []


def _modelo_empresa_identity(valor: Any) -> CompanyIdentity:
    if isinstance(valor, dict):
        dados = CompanyIdentity().model_dump()
        for chave in ("company_name", "description", "location", "website"):
            texto = _texto_limpo(valor.get(chave))
            if texto:
                dados[chave] = texto
        return CompanyIdentity.model_validate(dados)

    return CompanyIdentity()


def _mesclar_identity(
    atual: CompanyIdentity,
    novo_valor: Any,
) -> CompanyIdentity:
    dados = atual.model_dump()
    novo = _modelo_empresa_identity(novo_valor).model_dump()

    for chave, valor in novo.items():
        if chave == "description":
            continue

        texto = _texto_limpo(valor)
        if not texto:
            continue

        atual_texto = _texto_limpo(dados.get(chave))
        if not atual_texto:
            dados[chave] = texto
            continue
        if texto.lower() in atual_texto.lower():
            continue
        dados[chave] = texto

    return CompanyIdentity.model_validate(dados)


def _adicionar_lista_existente(
    existente: list[str],
    novos: list[str],
) -> list[str]:
    return _lista_unica([*existente, *novos])


def _adicionar_project_typologies(
    existentes: list[CompanyProjectExperience],
    typologies: list[str],
) -> list[CompanyProjectExperience]:
    resultados = [item.model_copy(deep=True) for item in existentes]
    vistos = {
        _texto_limpo(item.typology).lower()
        for item in resultados
        if _texto_limpo(item.typology)
    }

    for typology in typologies:
        texto = _texto_limpo(typology)
        if not texto:
            continue
        chave = texto.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        resultados.append(
            CompanyProjectExperience(
                name=texto,
                typology=texto,
            )
        )

    return resultados


def _adicionar_project_names(
    existentes: list[CompanyProjectExperience],
    project_names: list[str],
) -> list[CompanyProjectExperience]:
    resultados = [item.model_copy(deep=True) for item in existentes]
    vistos = {
        _texto_limpo(item.name).lower()
        for item in resultados
        if _texto_limpo(item.name)
    }

    for name in project_names:
        texto = _texto_limpo(name)
        if not texto:
            continue
        chave = texto.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        resultados.append(CompanyProjectExperience(name=texto))

    return resultados


def _sintetizar_identidade_institucional(perfil: CompanyProfile) -> str:
    nome = _texto_limpo(perfil.identity.company_name) or "A empresa"
    localizacao = _texto_limpo(perfil.identity.location)

    servicos = _formatar_lista_legivel(perfil.services[:4])
    competences = _formatar_lista_legivel(perfil.competences[:4])

    tipologias = _lista_unica(
        [
            project.typology
            for project in perfil.project_experience
            if _texto_limpo(project.typology)
        ]
    )
    tipologias_texto = _formatar_lista_legivel(tipologias[:4])

    prioridade_areas = _formatar_lista_legivel(
        list(perfil.preferences.typologies)[:3]
    )
    future_goals = _formatar_lista_legivel(
        list(perfil.strategy.get("future_goals", []))[:3]
    )

    frases: list[str] = []

    if localizacao:
        frases.append(f"{nome} atua a partir de {localizacao}.")
    else:
        frases.append(f"{nome} atua no setor da arquitetura e do projeto.")

    if servicos:
        frases.append(f"Desenvolve servicos de {servicos}.")
    else:
        frases.append(
            "Desenvolve projetos de arquitetura, urbanismo e areas relacionadas."
        )

    if tipologias_texto:
        frases.append(f"Intervem em {tipologias_texto}.")
    elif prioridade_areas:
        frases.append(f"Foca-se em concursos e tipologias como {prioridade_areas}.")
    else:
        frases.append(
            "Atua em programas de diferentes escalas, desde intervencoes localizadas ate contextos mais amplos."
        )

    if competences:
        frases.append(f"Reune competencias em {competences}.")
    else:
        frases.append(
            "A sua pratica destaca coordenacao tecnica, integracao multidisciplinar e resposta estruturada a diferentes escalas."
        )

    if future_goals:
        posicionamento = (
            f"privilegiando {future_goals} e uma abordagem multidisciplinar"
        )
    elif prioridade_areas:
        posicionamento = f"com enfoque em {prioridade_areas} e rigor tecnico"
    else:
        posicionamento = (
            "com uma abordagem multidisciplinar, rigor tecnico e orientacao "
            "para solucoes consistentes"
        )

    frases.append(
        "O posicionamento e "
        + posicionamento
        + ", orientado para encomendas publicas e privadas e para solucoes adaptadas a programas, escalas e contextos distintos."
    )

    texto = _limitar_palavras(" ".join(frases))

    if len(texto.split()) < 60:
        texto = _limitar_palavras(
            texto
            + " A sua atividade privilegia respostas ajustadas a requisitos tecnicos, objetivos funcionais e contextos de colaboracao, mantendo uma leitura coerente do perfil institucional.",
        )

    return texto


def _facto_tem_apoio(fact: ExtractedFact) -> bool:
    return fact.status in _FACTOS_VALIDOS


def _atualizar_descricao_sintetica(perfil: CompanyProfile) -> CompanyProfile:
    atualizado = perfil.model_copy(deep=True)
    atualizado.identity.description = _sintetizar_identidade_institucional(
        atualizado
    )
    return atualizado


def apply_extraction_to_profile(
    profile,
    extraction_result: CompanyExtractionResult,
):
    """
    Transforma factos extraidos em CompanyProfile.

    A camada mantem-se deterministica e conservadora:
    - apenas aceita factos confirmados;
    - faz merge sem apagar dados anteriores;
    - evita duplicados;
    - sintetiza a identidade institucional antes da persistencia.
    """
    perfil = profile.model_copy(deep=True)
    if not isinstance(extraction_result, CompanyExtractionResult):
        return perfil

    for fact in extraction_result.facts:
        if not _facto_tem_apoio(fact):
            continue

        if fact.field == "company.identity":
            perfil.identity = _mesclar_identity(perfil.identity, fact.value)
        elif fact.field == "company.services":
            perfil.services = _adicionar_lista_existente(
                perfil.services,
                _valor_em_lista(fact),
            )
        elif fact.field == "company.competences":
            perfil.competences = _adicionar_lista_existente(
                perfil.competences,
                _valor_em_lista(fact),
            )
        elif fact.field == "projects.typologies":
            perfil.project_experience = _adicionar_project_typologies(
                perfil.project_experience,
                _valor_em_lista(fact),
            )
        elif fact.field == "projects.items":
            perfil.project_experience = _adicionar_project_names(
                perfil.project_experience,
                _valor_em_lista(fact),
            )

    perfil = _atualizar_descricao_sintetica(perfil)

    return perfil
