from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from typing import Any

import requests


logger = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODELO_PADRAO = os.getenv("CNLL_AI_MODEL", "gpt-4o-mini")
TIMEOUT_AI = int(os.getenv("CNLL_AI_TIMEOUT", "90"))
MAX_CHARS_DOCUMENTOS = int(os.getenv("CNLL_AI_MAX_CHARS", "36000"))

DOCUMENTOS_PRIORITARIOS = (
    "programa preliminar",
    "programa funcional",
    "programa base",
    "caderno de encargos",
    "termos de referencia",
    "termos de referência",
    "memoria descritiva",
    "memória descritiva",
    "anexo tecnico",
    "anexo técnico",
)

TERMOS_ADMINISTRATIVOS = (
    "plataforma eletronica",
    "plataforma eletrónica",
    "acingov",
    "assinatura digital",
    "certificado digital",
    "codigo de acesso",
    "código de acesso",
    "proposta devera mencionar",
    "proposta deverá mencionar",
    "concorrente",
    "formulario",
    "formulário",
    "equipa de projeto",
    "coordenador do projeto",
    "devera ser nomeado",
    "deverá ser nomeado",
)


def _texto_limpo(valor: object) -> str:
    if valor is None:
        return ""
    return " ".join(str(valor).strip().split())


def _sem_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(
        c
        for c in normalizado
        if not unicodedata.combining(c)
    )


def _normalizar_lista(valor: Any, limite: int = 14) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, str):
        partes = re.split(r"\n|;|•|- (?=[A-ZÁÂÃÉÍÓÚÇ])", valor)
    elif isinstance(valor, list):
        partes = valor
    else:
        partes = []

    resultado: list[str] = []
    vistos: set[str] = set()
    for item in partes:
        texto = _texto_limpo(item)
        if len(texto) < 3:
            continue
        chave = _sem_acentos(texto.lower())[:160]
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(texto)
        if len(resultado) >= limite:
            break
    return resultado


def _frases_com_termos(
    texto: str,
    termos: tuple[str, ...],
    *,
    limite: int = 8,
    max_chars: int = 360,
    ignorar: tuple[str, ...] = (),
) -> list[str]:
    encontrados: list[str] = []
    vistos: set[str] = set()
    termos_normais = tuple(_sem_acentos(t.lower()) for t in termos)
    ignorar_normais = tuple(_sem_acentos(t.lower()) for t in ignorar)

    for frase in re.split(r"(?<=[.;:])\s+|\n+", texto):
        limpa = _texto_limpo(frase)
        limpa = re.sub(r"^#+\s*DOCUMENTO:.*?\s+", "", limpa)
        if len(limpa) < 22 or len(limpa) > max_chars:
            continue
        base = _sem_acentos(limpa.lower())
        if ignorar_normais and any(t in base for t in ignorar_normais):
            continue
        if not any(termo in base for termo in termos_normais):
            continue
        chave = base[:180]
        if chave in vistos:
            continue
        vistos.add(chave)
        encontrados.append(limpa)
        if len(encontrados) >= limite:
            break
    return encontrados


def _pontuar_documento(nome: str, texto: str) -> int:
    base = _sem_acentos(f"{nome} {texto[:1200]}".lower())
    pontos = 0
    for indice, termo in enumerate(DOCUMENTOS_PRIORITARIOS):
        if _sem_acentos(termo.lower()) in base:
            pontos += max(2, 18 - indice)
    if "programa" in base:
        pontos += 8
    if "caderno" in base or "encargos" in base:
        pontos += 6
    if "criterio" in base or "adjudicacao" in base:
        pontos += 4
    return pontos


def _selecionar_texto_prioritario(textos: dict[str, str]) -> str:
    ordenados = sorted(
        textos.items(),
        key=lambda item: _pontuar_documento(item[0], item[1]),
        reverse=True,
    )
    partes: list[str] = []
    total = 0
    for nome, texto in ordenados:
        limpo = texto.strip()
        if not limpo:
            continue
        restante = MAX_CHARS_DOCUMENTOS - total
        if restante <= 0:
            break
        excerto = limpo[:restante]
        partes.append(f"\n\n### DOCUMENTO: {nome}\n{excerto}")
        total += len(excerto)
    return "".join(partes).strip()


def _extrair_areas_contexto(texto: str) -> list[str]:
    areas: list[str] = []
    vistos: set[str] = set()
    for match in re.finditer(
        r"([A-ZÁÂÃÉÍÓÚÇa-záâãéíóúç0-9 /.,;:-]{0,80}?"
        r"\d[\d\s.,]{1,}\s*m[²2])",
        texto,
    ):
        item = _texto_limpo(match.group(1))
        chave = _sem_acentos(item.lower())
        if len(item) < 5 or chave in vistos:
            continue
        vistos.add(chave)
        areas.append(item)
        if len(areas) >= 12:
            break
    return areas


def _texto_narrativo_util(texto: str) -> bool:
    limpo = _texto_limpo(texto)
    base = _sem_acentos(limpo.lower())
    if len(limpo) < 50:
        return False
    if limpo.startswith(("•", "-", "–")):
        return False
    if base.endswith((" de", " da", " do", " das", " dos", " para")):
        return False
    if any(_sem_acentos(t.lower()) in base for t in TERMOS_ADMINISTRATIVOS):
        return False
    if any(t in base for t in ("declaracao", "coordenador")):
        return False
    return True


def _inferir_espacos(texto: str) -> list[str]:
    base = _sem_acentos(texto.lower())
    catalogo = (
        ("rececao", "Receção / atendimento"),
        ("atendimento", "Atendimento ao público"),
        ("sala", "Salas de trabalho / atividade"),
        ("gabinete", "Gabinetes"),
        ("auditorio", "Auditório / sala polivalente"),
        ("biblioteca", "Biblioteca / mediateca"),
        ("mercado", "Mercado / bancas comerciais"),
        ("loja", "Lojas / unidades comerciais"),
        ("cozinha", "Cozinha / copa"),
        ("instalacoes sanitarias", "Instalações sanitárias"),
        ("balneario", "Balneários"),
        ("arrumos", "Arrumos"),
        ("arquivo", "Arquivo"),
        ("zona tecnica", "Zonas técnicas"),
        ("estacionamento", "Estacionamento"),
        ("espaco exterior", "Espaço exterior"),
        ("jardim", "Jardim / espaço verde"),
        ("circulacao", "Circulações"),
    )
    resultado: list[str] = []
    for termo, nome in catalogo:
        if termo in base and nome not in resultado:
            resultado.append(nome)
    return resultado[:12]


def _sintese_deterministica(
    *,
    titulo: str,
    texto: str,
    espacos: list[str],
    areas: list[str],
    relacoes: list[str],
    requisitos: list[str],
    condicionantes: list[str],
) -> str:
    objetivo = _frases_com_termos(
        texto,
        (
            "objeto",
            "objetivo",
            "âmbito",
            "ambito",
            "destina-se",
            "pretende",
            "programa",
            "intervenção",
            "intervencao",
            "reabilitação",
            "reabilitacao",
            "construção",
            "construcao",
        ),
        limite=2,
        max_chars=520,
        ignorar=TERMOS_ADMINISTRATIVOS,
    )

    partes = [
        f"O programa preliminar associado a {titulo} define uma base de "
        "trabalho para o desenvolvimento arquitetónico a partir das peças "
        "oficiais analisadas, articulando objetivos funcionais, requisitos "
        "técnicos e condicionantes de implementação."
    ]

    objetivo_util = [
        frase
        for frase in objetivo
        if _texto_narrativo_util(frase)
    ]
    if objetivo_util:
        partes.append(f"Os documentos indicam que {objetivo_util[0]}")

    if espacos:
        partes.append(
            "O programa identifica como componentes funcionais principais "
            f"{', '.join(espacos[:8]).lower()}."
        )
    if areas:
        partes.append(
            "As áreas e referências dimensionais extraídas incluem "
            f"{'; '.join(areas[:6])}."
        )
    relacoes_sintese = [
        item for item in relacoes if _texto_narrativo_util(item)
    ]
    requisitos_sintese = [
        item for item in requisitos if _texto_narrativo_util(item)
    ]
    condicionantes_sintese = [
        item for item in condicionantes if _texto_narrativo_util(item)
    ]

    if relacoes_sintese:
        partes.append(
            "A organização funcional deverá atender às relações entre "
            f"{' '.join(relacoes_sintese[:2])}"
        )
    if requisitos_sintese:
        partes.append(
            "Entre os requisitos relevantes contam-se "
            f"{' '.join(requisitos_sintese[:2])}"
        )
    if condicionantes_sintese:
        partes.append(
            "Foram ainda identificadas condicionantes com impacto na "
            "estratégia arquitetónica: "
            f"{' '.join(condicionantes_sintese[:2])}"
        )

    sintese = " ".join(partes)
    if len(sintese) < 280:
        sintese += (
            " A síntese deverá ser lida como base de trabalho para avaliar "
            "a complexidade funcional, a articulação com a envolvente, a "
            "equipa técnica necessária e a estratégia de candidatura CNLL."
        )
    return sintese


def _analise_deterministica(textos: dict[str, str], titulo: str) -> dict:
    texto = _selecionar_texto_prioritario(textos)
    if not texto:
        texto = "\n".join(textos.values())

    espacos = _inferir_espacos(texto)
    areas = _extrair_areas_contexto(texto)
    relacoes = _frases_com_termos(
        texto,
        (
            "articulação",
            "articulacao",
            "fluxo",
            "circulação",
            "circulacao",
            "ligação",
            "ligacao",
            "zonamento",
            "compatibilização",
            "compatibilizacao",
        ),
        limite=8,
        ignorar=TERMOS_ADMINISTRATIVOS,
    )
    requisitos = _frases_com_termos(
        texto,
        (
            "deverá",
            "devera",
            "garantir",
            "cumprir",
            "acessibilidade",
            "segurança",
            "seguranca",
            "sustentabilidade",
            "eficiência",
            "eficiencia",
            "conforto",
            "licenciamento",
        ),
        limite=10,
        ignorar=TERMOS_ADMINISTRATIVOS,
    )
    condicionantes = _frases_com_termos(
        texto,
        (
            "condicionante",
            "restrição",
            "restricao",
            "servidão",
            "servidao",
            "património",
            "patrimonio",
            "edifício existente",
            "edificio existente",
            "topografia",
            "ruído",
            "ruido",
            "ambiental",
            "envolvente",
        ),
        limite=8,
        ignorar=TERMOS_ADMINISTRATIVOS,
    )

    return {
        "programa_funcional": {
            "sintese": _sintese_deterministica(
                titulo=titulo,
                texto=texto,
                espacos=espacos,
                areas=areas,
                relacoes=relacoes,
                requisitos=requisitos,
                condicionantes=condicionantes,
            ),
            "espacos_principais": espacos,
            "areas": areas,
            "relacoes_funcionais": relacoes,
            "requisitos": requisitos,
            "condicionantes": condicionantes,
        },
        "criterios": {},
        "entregaveis": [],
        "equipa": {
            "especialidades": [],
            "tecnicos_exigidos": [],
        },
        "origem": "extracao_documental_local",
    }


def _prompt_documental(titulo: str, texto: str) -> list[dict[str, str]]:
    schema = {
        "programa_funcional": {
            "sintese": "parágrafo completo, arquitetónico e detalhado",
            "espacos_principais": [],
            "areas": [],
            "relacoes_funcionais": [],
            "requisitos": [],
            "condicionantes": [],
        },
        "criterios": {
            "preco": None,
            "qualidade": None,
            "ponderacoes": [],
        },
        "entregaveis": [],
        "equipa": {
            "especialidades": [],
            "tecnicos_exigidos": [],
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "És um analista de concursos públicos de arquitetura. "
                "Lê documentos oficiais e extrai informação estruturada "
                "sem inventar dados. Privilegia informação completa, "
                "programática e arquitetónica, não resumos curtos."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Concurso: {titulo}\n\n"
                "Analisa os documentos seguintes e devolve apenas JSON válido "
                "com esta estrutura:\n"
                f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
                "Regras para programa_funcional.sintese: mínimo um parágrafo "
                "completo; explicar objetivo, tipo de equipamento, organização "
                "funcional, espaços principais e requisitos relevantes; nunca "
                "usar frases genéricas como 'Resumo disponível' ou "
                "'Construção de equipamento público'. Se um dado não existir, "
                "deixa a lista vazia ou o valor null.\n\n"
                f"DOCUMENTOS EXTRAÍDOS:\n{texto}"
            ),
        },
    ]


def _chamar_openai(titulo: str, texto: str) -> dict | None:
    chave = os.getenv("OPENAI_API_KEY")
    if not chave:
        return None

    payload = {
        "model": MODELO_PADRAO,
        "messages": _prompt_documental(titulo, texto),
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        resposta = requests.post(
            OPENAI_URL,
            headers={
                "Authorization": f"Bearer {chave}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=TIMEOUT_AI,
        )
        resposta.raise_for_status()
        conteudo = resposta.json()["choices"][0]["message"]["content"]
        dados = json.loads(conteudo)
        if isinstance(dados, dict):
            dados["origem"] = "openai_document_analysis"
            return dados
    except Exception as erro:
        logger.warning("Falha na análise AI documental: %s", erro)
    return None


def _validar_programa_funcional(dados: dict, fallback: dict) -> dict:
    programa = dados.get("programa_funcional")
    if not isinstance(programa, dict):
        programa = {}

    fallback_programa = fallback["programa_funcional"]
    sintese = _texto_limpo(programa.get("sintese"))
    sintese_invalida = {
        "resumo disponível",
        "resumo disponivel",
        "construção de equipamento público",
        "construcao de equipamento publico",
    }
    if (
        len(sintese) < 220
        or _sem_acentos(sintese.lower()) in sintese_invalida
    ):
        sintese = fallback_programa["sintese"]

    return {
        "sintese": sintese,
        "espacos_principais": (
            _normalizar_lista(programa.get("espacos_principais"))
            or fallback_programa["espacos_principais"]
        ),
        "areas": (
            _normalizar_lista(programa.get("areas"))
            or fallback_programa["areas"]
        ),
        "relacoes_funcionais": (
            _normalizar_lista(programa.get("relacoes_funcionais"))
            or fallback_programa["relacoes_funcionais"]
        ),
        "requisitos": (
            _normalizar_lista(programa.get("requisitos"))
            or fallback_programa["requisitos"]
        ),
        "condicionantes": (
            _normalizar_lista(programa.get("condicionantes"))
            or fallback_programa["condicionantes"]
        ),
    }


def analisar_documentos_ai(
    *,
    textos: dict[str, str],
    documentos: list[dict],
    titulo: str,
) -> dict:
    """Interpreta textos extraídos antes da geração da ficha CNLL.

    Esta função é chamada pelo worker existente, depois da extração de texto
    PDF e antes de escrever ficha.json. Quando OPENAI_API_KEY está disponível,
    usa AI para estruturar o conteúdo; caso contrário mantém o worker funcional
    com extração local, sem criar uma pipeline paralela.
    """

    del documentos  # reservado para evolução: versões/tipos/documentos fonte

    fallback = _analise_deterministica(textos, titulo)
    texto_prioritario = _selecionar_texto_prioritario(textos)
    dados_ai = _chamar_openai(titulo, texto_prioritario) or {}

    programa_funcional = _validar_programa_funcional(dados_ai, fallback)

    return {
        "programa_funcional": programa_funcional,
        "criterios": dados_ai.get("criterios")
        if isinstance(dados_ai.get("criterios"), dict)
        else fallback.get("criterios", {}),
        "entregaveis": _normalizar_lista(dados_ai.get("entregaveis"))
        or fallback.get("entregaveis", []),
        "equipa": dados_ai.get("equipa")
        if isinstance(dados_ai.get("equipa"), dict)
        else fallback.get("equipa", {}),
        "origem": dados_ai.get("origem") or fallback["origem"],
    }
