from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import threading
import time
import unicodedata
from contextlib import suppress
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile

import requests
from pypdf import PdfReader

from app.analise.classificador import classificar_documento
from app.analise.criterios import analisar_criterios
from app.analise.document_ai import analisar_documentos_ai
from app.analise.equipa import analisar_equipa
from app.analise.gerador import gerar_perfil_concurso
from app.analise.normalizador_equipa import normalizar_subfatores
from app.database import (
    analise_job_esta_cancelado,
    atualizar_analise_job,
    atualizar_localizacao_concurso,
    concurso_por_id,
    guardar_analise,
    reivindicar_proximo_analise_job,
)
from app.localizacao import resolver_localizacao


BASE_DIR = Path(__file__).resolve().parents[2]
ANALISES_DIR = BASE_DIR / "analise_documentos"
JOBS_TEMP_DIR = ANALISES_DIR / ".jobs"

POLL_INTERVALO = float(os.getenv("CNLL_ANALISE_WORKER_POLL", "6"))
INTERVALO_DOWNLOADS = float(
    os.getenv("CNLL_ANALISE_DOWNLOAD_INTERVALO", "8")
)
TIMEOUT_DOWNLOAD = int(os.getenv("CNLL_ANALISE_DOWNLOAD_TIMEOUT", "90"))

_download_lock = threading.Lock()
_ultimo_download = 0.0
logger = logging.getLogger(__name__)


class JobCancelado(Exception):
    pass


class WorkerErro(Exception):
    pass


def _id_base(link: str | None) -> str | None:
    if not link:
        return None
    resultado = re.search(r"[?&]id=(\d+)", link)
    return resultado.group(1) if resultado else None


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


def _verificar_cancelamento(job_id: int) -> None:
    if analise_job_esta_cancelado(job_id):
        raise JobCancelado()


def _aguardar_download() -> None:
    global _ultimo_download

    with _download_lock:
        agora = time.monotonic()
        espera = INTERVALO_DOWNLOADS - (agora - _ultimo_download)
        if _ultimo_download and espera > 0:
            time.sleep(espera)
        _ultimo_download = time.monotonic()


def _validar_url_download(url: str) -> None:
    partes = urlparse(url)
    if partes.scheme.lower() not in {"http", "https"}:
        raise WorkerErro("URL de documentos invalida.")
    if not partes.netloc:
        raise WorkerErro("URL de documentos sem dominio.")


def _nome_download(conteudo: bytes, content_type: str) -> str:
    tipo = content_type.lower()
    if conteudo.startswith(b"PK") or "zip" in tipo:
        return "pecas.zip"
    if conteudo.startswith(b"%PDF") or "pdf" in tipo:
        return "documento.pdf"
    return "documentos.bin"


def _descarregar(url: str, destino: Path) -> Path:
    _validar_url_download(url)
    _aguardar_download()

    resposta = requests.get(
        url,
        timeout=TIMEOUT_DOWNLOAD,
        allow_redirects=True,
        headers={
            "User-Agent": (
                "CNLL/1.0 "
                "(analise moderada de documentos oficiais)"
            ),
            "Accept": "*/*",
        },
    )
    resposta.raise_for_status()

    conteudo = resposta.content
    if not conteudo:
        raise WorkerErro("Download de documentos vazio.")

    nome = _nome_download(
        conteudo,
        resposta.headers.get("content-type", ""),
    )
    caminho = destino / nome
    caminho.write_bytes(conteudo)

    if nome == "documentos.bin":
        raise WorkerErro(
            "A resposta dos documentos nao parece ZIP nem PDF."
        )

    return caminho


def _extrair_zip_seguro(ficheiro_zip: Path, destino: Path) -> None:
    destino_resolvido = destino.resolve()

    with ZipFile(ficheiro_zip) as zip_file:
        for membro in zip_file.infolist():
            alvo = (destino / membro.filename).resolve()
            if (
                alvo != destino_resolvido
                and destino_resolvido not in alvo.parents
            ):
                raise WorkerErro(
                    f"ZIP contem caminho inseguro: {membro.filename}"
                )
        zip_file.extractall(destino)


def _extrair_archivos_recursivo(origem: Path, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)

    if origem.suffix.lower() == ".pdf":
        shutil.copy2(origem, destino / origem.name)
        return

    try:
        _extrair_zip_seguro(origem, destino)
    except BadZipFile as erro:
        raise WorkerErro("O pacote de documentos nao e um ZIP valido.") from erro

    vistos: set[Path] = set()
    while True:
        zips = [
            ficheiro
            for ficheiro in destino.rglob("*.zip")
            if ficheiro not in vistos
        ]
        if not zips:
            break

        for zip_interno in zips:
            vistos.add(zip_interno)
            nova_pasta = zip_interno.parent / zip_interno.stem
            nova_pasta.mkdir(exist_ok=True)
            try:
                _extrair_zip_seguro(zip_interno, nova_pasta)
            except BadZipFile:
                continue


def _extrair_texto_pdf(caminho: Path) -> str:
    try:
        leitor = PdfReader(str(caminho))
    except Exception as erro:
        logger.warning("Nao foi possivel abrir PDF %s: %s", caminho, erro)
        return ""

    paginas = []
    for pagina in leitor.pages:
        with suppress(Exception):
            paginas.append(pagina.extract_text() or "")
    return "\n".join(paginas).strip()


def _extrair_textos(pasta: Path) -> dict[str, str]:
    textos: dict[str, str] = {}
    for pdf in pasta.rglob("*.pdf"):
        texto = _extrair_texto_pdf(pdf)
        if texto:
            textos[str(pdf.relative_to(pasta))] = texto
    return textos


def _classificar_documentos(pasta: Path) -> tuple[list[dict], dict]:
    resumo = {
        "total_documentos": 0,
        "programa_procedimento": False,
        "caderno_encargos": False,
        "programa_preliminar": False,
        "levantamento": False,
        "pecas_desenhadas": False,
        "cartografia": False,
        "mapa_quantidades": False,
        "elementos_prediais": False,
        "condicoes_tecnicas": False,
    }
    documentos = []
    vistos: set[str] = set()

    for ficheiro in pasta.rglob("*"):
        if not ficheiro.is_file():
            continue
        if ficheiro.suffix.lower() in {".zip"}:
            continue

        nome = str(ficheiro.relative_to(pasta))
        if nome in vistos:
            continue
        vistos.add(nome)

        tipos = classificar_documento(ficheiro.name)
        resumo["total_documentos"] += 1
        for tipo in tipos:
            if tipo in resumo:
                resumo[tipo] = True

        documentos.append(
            {
                "nome": nome,
                "tipos": tipos,
            }
        )

    return documentos, resumo


def _extrair_valor(texto: str) -> str | None:
    resultado = re.search(
        r"(\d[\d\s.]{2,}(?:,\d{2})?)\s*(?:EUR|€)",
        texto,
        re.IGNORECASE,
    )
    if not resultado:
        return None
    return f"{resultado.group(1).strip()} €"


def _extrair_areas(texto: str) -> dict[str, str]:
    areas: dict[str, str] = {}
    for indice, area in enumerate(
        re.findall(r"(\d[\d\s.,]{1,})\s*m[²2]", texto, re.IGNORECASE),
        start=1,
    ):
        if indice > 8:
            break
        areas[f"area_{indice}"] = f"{_texto_limpo(area)} m²"
    return areas


def _extrair_tipo_intervencao(texto: str, titulo: str) -> list[str]:
    base = _sem_acentos(f"{titulo} {texto}".lower())
    regras = [
        ("reabilitacao", "Reabilitacao"),
        ("revitalizacao", "Revitalizacao"),
        ("modernizacao", "Modernizacao"),
        ("construcao", "Construcao"),
        ("ampliacao", "Ampliacao"),
        ("remodelacao", "Remodelacao"),
        ("requalificacao", "Requalificacao"),
        ("paisagismo", "Paisagismo"),
    ]
    tipos = [nome for termo, nome in regras if termo in base]
    return tipos or ["Intervencao geral"]


def _extrair_funcoes(texto: str, titulo: str) -> list[str]:
    base = _sem_acentos(f"{titulo} {texto}".lower())
    regras = [
        ("mercado", "Mercado Municipal"),
        ("escola", "Equipamento educativo"),
        ("habitacao", "Habitacao"),
        ("museu", "Cultura"),
        ("auditorio", "Auditorio"),
        ("espaco publico", "Espaco publico"),
        ("jardim", "Espaco exterior"),
        ("centro de saude", "Saude"),
        ("edificio", "Edificio"),
    ]
    funcoes = []
    for termo, nome in regras:
        if termo in base and nome not in funcoes:
            funcoes.append(nome)
    return funcoes


def _frases_com_termos(
    texto: str,
    termos: tuple[str, ...],
    limite: int = 8,
) -> list[str]:
    encontrados: list[str] = []
    vistos: set[str] = set()
    frases = re.split(r"(?<=[.;:])\s+|\n+", texto)
    termos_normais = tuple(_sem_acentos(termo.lower()) for termo in termos)

    for frase in frases:
        limpa = _texto_limpo(frase)
        if len(limpa) < 18 or len(limpa) > 260:
            continue
        base = _sem_acentos(limpa.lower())
        if not any(termo in base for termo in termos_normais):
            continue
        chave = base[:120]
        if chave in vistos:
            continue
        vistos.add(chave)
        encontrados.append(limpa)
        if len(encontrados) >= limite:
            break

    return encontrados


def _extrair_entregaveis(texto: str, concurso: dict) -> list[str]:
    entregaveis_db = _texto_limpo(concurso.get("entregaveis"))
    if entregaveis_db:
        return [
            item.strip(" -•;")
            for item in re.split(r";|\n|,", entregaveis_db)
            if item.strip(" -•;")
        ][:12]

    termos = (
        "projeto de arquitetura",
        "projeto do espaço exterior",
        "estudo prévio",
        "projeto de execução",
        "memória descritiva",
        "mapa de quantidades",
        "estimativa orçamental",
        "peças desenhadas",
        "plano de acessibilidades",
        "plano de segurança",
        "telas finais",
    )
    return _frases_com_termos(texto, termos, limite=12)


def _extrair_especialidades(texto: str) -> list[str]:
    regras = (
        ("arquitetura paisagista", "Arquitetura paisagista"),
        ("arquitetura", "Arquitetura"),
        ("estabilidade", "Estabilidade / estruturas"),
        ("engenharia civil", "Engenharia civil"),
        ("instalações elétricas", "Instalações elétricas"),
        ("instalacoes eletricas", "Instalações elétricas"),
        ("telecomunicações", "Telecomunicações"),
        ("avac", "AVAC"),
        ("climatização", "Climatização"),
        ("comportamento térmico", "Comportamento térmico"),
        ("comportamento termico", "Comportamento térmico"),
        ("acústico", "Acústica"),
        ("acustico", "Acústica"),
        ("segurança contra incêndios", "Segurança contra incêndios"),
        ("seguranca contra incendios", "Segurança contra incêndios"),
        ("águas residuais", "Águas e águas residuais"),
        ("aguas residuais", "Águas e águas residuais"),
        ("rede de abastecimento", "Redes de água"),
        ("gás", "Gás"),
        ("gas", "Gás"),
        ("sinalética", "Sinalética"),
        ("sinaletica", "Sinalética"),
    )
    base = _sem_acentos(texto.lower())
    especialidades: list[str] = []
    for termo, nome in regras:
        if _sem_acentos(termo) in base and nome not in especialidades:
            especialidades.append(nome)
    return especialidades


def _extrair_requisitos(texto: str) -> dict:
    obrigatorios = _frases_com_termos(
        texto,
        (
            "obrigatório",
            "obrigatoria",
            "habilitação",
            "habilitacao",
            "termo de responsabilidade",
            "inscrição válida",
            "inscricao valida",
            "certificação",
            "certificacao",
            "experiência comprovada",
            "experiencia comprovada",
        ),
        limite=10,
    )
    riscos = _frases_com_termos(
        texto,
        (
            "exclusão",
            "exclusao",
            "caducidade",
            "não apresentação",
            "nao apresentacao",
            "falta",
            "insuficiência",
            "insuficiencia",
        ),
        limite=8,
    )
    return {
        "obrigatorios": obrigatorios,
        "riscos_participacao": riscos,
    }


def _lista_texto(valor: object, limite: int = 14) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, str):
        candidatos = re.split(r";|\n|,|\u2022", valor)
    elif isinstance(valor, list):
        candidatos = valor
    else:
        return []

    resultado: list[str] = []
    vistos: set[str] = set()
    for item in candidatos:
        texto = _texto_limpo(item).strip(" -\u2022;")
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


def _juntar_listas(*listas: list[str], limite: int = 18) -> list[str]:
    resultado: list[str] = []
    vistos: set[str] = set()
    for lista in listas:
        for item in lista:
            texto = _texto_limpo(item).strip(" -\u2022;")
            if len(texto) < 3:
                continue
            chave = _sem_acentos(texto.lower())[:160]
            if chave in vistos:
                continue
            vistos.add(chave)
            resultado.append(texto)
            if len(resultado) >= limite:
                return resultado
    return resultado


def _areas_para_programa(
    areas_regex: dict[str, str],
    areas_ai: list[str],
) -> dict[str, str]:
    if areas_regex:
        return areas_regex
    return {
        f"area_{indice}": area
        for indice, area in enumerate(areas_ai[:12], start=1)
    }


def _enriquecer_requisitos(
    requisitos: dict,
    programa_funcional: dict,
    equipa_ai: dict,
) -> dict:
    obrigatorios = _juntar_listas(
        requisitos.get("obrigatorios", []),
        _lista_texto(programa_funcional.get("requisitos")),
        _lista_texto(equipa_ai.get("tecnicos_exigidos")),
        limite=18,
    )
    riscos = _juntar_listas(
        requisitos.get("riscos_participacao", []),
        _lista_texto(programa_funcional.get("condicionantes")),
        limite=14,
    )
    return {
        "obrigatorios": obrigatorios,
        "riscos_participacao": riscos,
    }


def _observacoes_programa(programa_funcional: dict) -> str:
    partes = []
    relacoes = _lista_texto(programa_funcional.get("relacoes_funcionais"))
    requisitos = _lista_texto(programa_funcional.get("requisitos"))
    condicionantes = _lista_texto(programa_funcional.get("condicionantes"))

    if relacoes:
        partes.append(
            "Relações funcionais identificadas: "
            + "; ".join(relacoes[:4])
        )
    if requisitos:
        partes.append(
            "Requisitos programáticos/técnicos: "
            + "; ".join(requisitos[:4])
        )
    if condicionantes:
        partes.append(
            "Condicionantes com impacto arquitetónico: "
            + "; ".join(condicionantes[:4])
        )

    if partes:
        return " ".join(partes)
    return (
        "Análise gerada automaticamente pelo worker CNLL com base nos "
        "documentos extraídos, dados do concurso e localização identificada "
        "quando disponível."
    )


def _sintese_programa(texto: str, titulo: str, funcoes: list[str]) -> str:
    frases = _frases_com_termos(
        texto,
        (
            "objeto",
            "âmbito",
            "ambito",
            "elaboração do projeto",
            "elaboracao do projeto",
            "intervenção",
            "intervencao",
            "reabilitação",
            "reabilitacao",
            "execução de arquitetura",
            "execucao de arquitetura",
        ),
        limite=2,
    )
    if frases:
        return " ".join(frases)

    if funcoes:
        return (
            f"Análise do programa associado a {', '.join(funcoes).lower()} "
            f"no âmbito do concurso {titulo}."
        )
    return f"Análise do programa preliminar e técnico do concurso {titulo}."


def _criterios_do_concurso(concurso: dict, texto: str) -> dict:
    resumo = _texto_limpo(concurso.get("criterio_resumo"))
    detalhe = _texto_limpo(concurso.get("criterio_detalhe"))
    if resumo or detalhe:
        criterio_texto = f"{resumo} {detalhe}".strip()
        analisado = analisar_criterios(criterio_texto)
        analisado["resumo"] = resumo
        analisado["detalhe"] = detalhe
        return analisado

    analisado = analisar_criterios(texto)
    preco = analisado.get("preco_percentagem")
    qualidade = analisado.get("qualidade_percentagem")
    partes = []
    if qualidade:
        partes.append(f"Qualidade {qualidade}%")
    if preco:
        partes.append(f"Preco {preco}%")
    analisado["resumo"] = " • ".join(partes)
    analisado["detalhe"] = analisado["resumo"]
    return analisado


def _calcular_score(
    resumo_documentos: dict,
    criterios: dict,
    equipa: list,
) -> int:
    pontos = 45
    pesos_documentos = {
        "programa_preliminar": 10,
        "programa_procedimento": 8,
        "caderno_encargos": 8,
        "pecas_desenhadas": 7,
        "levantamento": 5,
        "mapa_quantidades": 5,
    }
    pontos += sum(
        peso
        for chave, peso in pesos_documentos.items()
        if resumo_documentos.get(chave)
    )
    if criterios.get("qualidade_percentagem"):
        pontos += 8
    if criterios.get("preco_percentagem"):
        pontos += 4
    if equipa:
        pontos += min(8, len(equipa))
    return max(0, min(100, pontos))


def _gerar_ficha(
    *,
    concurso: dict,
    job: dict,
    textos: dict[str, str],
    documentos: list[dict],
    resumo_documentos: dict,
    analise_documental: dict,
) -> tuple[dict, int]:
    texto_total = "\n".join(textos.values())
    if not isinstance(analise_documental, dict):
        analise_documental = {}
    programa_funcional = (
        analise_documental.get("programa_funcional", {})
        if isinstance(analise_documental.get("programa_funcional"), dict)
        else {}
    )
    equipa_ai = (
        analise_documental.get("equipa", {})
        if isinstance(analise_documental.get("equipa"), dict)
        else {}
    )
    criterios = _criterios_do_concurso(concurso, texto_total)
    equipa_bruta = analisar_equipa(texto_total)
    equipa = normalizar_subfatores(
        equipa_bruta.get("subfatores_equipa", [])
    )
    estrategia = gerar_perfil_concurso(criterios, equipa)
    score = _calcular_score(resumo_documentos, criterios, equipa)
    localizacao = resolver_localizacao(concurso, texto_total)
    if localizacao.get("contexto_urbano"):
        estrategia.setdefault("pontos_decisivos", [])
        estrategia["pontos_decisivos"].append(
            "Enquadramento urbano e condicionantes do local"
        )
        estrategia["resumo"] = " ".join(
            parte
            for parte in (
                _texto_limpo(estrategia.get("resumo")),
                localizacao.get("contexto_urbano"),
            )
            if parte
        )

    titulo = _texto_limpo(concurso.get("titulo")) or "Concurso sem titulo"
    valor = (
        _texto_limpo(concurso.get("valor_obra"))
        or _texto_limpo(concurso.get("preco_base"))
        or _extrair_valor(texto_total)
    )
    prazo = (
        _texto_limpo(concurso.get("data_entrega_propostas"))
        or _texto_limpo(concurso.get("data_limite"))
    )
    espacos_ai = _lista_texto(
        programa_funcional.get("espacos_principais")
    )
    funcoes = _juntar_listas(
        _extrair_funcoes(texto_total, titulo),
        espacos_ai,
        limite=16,
    )
    areas_ai = _lista_texto(programa_funcional.get("areas"))
    areas = _areas_para_programa(_extrair_areas(texto_total), areas_ai)
    entregaveis = _juntar_listas(
        _lista_texto(analise_documental.get("entregaveis")),
        _extrair_entregaveis(texto_total, concurso),
        limite=18,
    )
    especialidades = _juntar_listas(
        _extrair_especialidades(texto_total),
        _lista_texto(equipa_ai.get("especialidades")),
        limite=18,
    )
    requisitos = _enriquecer_requisitos(
        _extrair_requisitos(texto_total),
        programa_funcional,
        equipa_ai,
    )
    sintese_programa = (
        _texto_limpo(programa_funcional.get("sintese"))
        or _sintese_programa(texto_total, titulo, funcoes)
    )
    if len(sintese_programa) < 220:
        sintese_programa = _sintese_programa(texto_total, titulo, funcoes)
    programa_funcional = {
        "sintese": sintese_programa,
        "espacos_principais": espacos_ai or funcoes,
        "areas": areas_ai or list(areas.values()),
        "relacoes_funcionais": _lista_texto(
            programa_funcional.get("relacoes_funcionais")
        ),
        "requisitos": _lista_texto(programa_funcional.get("requisitos")),
        "condicionantes": _lista_texto(
            programa_funcional.get("condicionantes")
        ),
    }

    ficha = {
        "identificacao": {
            "titulo": titulo,
            "entidade": _texto_limpo(concurso.get("entidade")),
            "local": (
                localizacao.get("morada")
                or localizacao.get("freguesia")
                or localizacao.get("municipio")
            ),
            "localizacao": (
                localizacao.get("morada")
                or localizacao.get("freguesia")
                or localizacao.get("municipio")
            ),
            "tipo_procedimento": _texto_limpo(
                concurso.get("tipo_procedimento")
            ),
            "url_base": concurso.get("link"),
            "concurso_id": concurso.get("id"),
            "job_id": job.get("id"),
        },
        "programa": {
            "descricao": sintese_programa,
            "resumo": sintese_programa,
            "sintese_programa_preliminar": sintese_programa,
            "tipo": _extrair_tipo_intervencao(texto_total, titulo),
            "funcoes": funcoes,
            "usos": funcoes,
            "espacos_principais": programa_funcional["espacos_principais"],
            "relacoes_funcionais": programa_funcional[
                "relacoes_funcionais"
            ],
            "requisitos": programa_funcional["requisitos"],
            "condicionantes": programa_funcional["condicionantes"],
            "areas": areas,
            "observacoes_ai": _observacoes_programa(programa_funcional),
        },
        "programa_funcional": programa_funcional,
        "localizacao": localizacao,
        "investimento": {
            "valor_obra": valor,
            "prazo_projeto": prazo,
        },
        "economia": {
            "valor_procedimento": valor,
            "valor_estimado_obra": valor,
        },
        "criterios": {
            "criterio_adjudicacao": (
                _texto_limpo(concurso.get("criterio_tipo"))
                or "Nao identificado"
            ),
            "resumo": criterios.get("resumo"),
            "detalhe": criterios.get("detalhe"),
            "percentagens": [
                {
                    "criterio": "Qualidade",
                    "percentagem": (
                        f"{criterios['qualidade_percentagem']}%"
                        if criterios.get("qualidade_percentagem")
                        else None
                    ),
                },
                {
                    "criterio": "Preco",
                    "percentagem": (
                        f"{criterios['preco_percentagem']}%"
                        if criterios.get("preco_percentagem")
                        else None
                    ),
                },
            ],
        },
        "documentos": {
            **resumo_documentos,
            "lista": documentos,
        },
        "entregaveis": {
            "principais": entregaveis,
        },
        "especialidades": {
            "lista": especialidades,
        },
        "requisitos": requisitos,
        "equipa": equipa,
        "estrategia": estrategia,
        "decisao": {
            "score": score,
            "classificacao": (
                "Muito interessante"
                if score >= 80
                else "Interessante"
                if score >= 65
                else "A avaliar"
            ),
            "elegibilidade": {
                "estado": (
                    "Requer verificacao"
                    if equipa_bruta.get("alertas")
                    else "Sem barreiras criticas identificadas"
                ),
                "motivos": equipa_bruta.get("alertas", []),
            },
            "oportunidades": [
                item
                for item in (
                    "Documentos oficiais recolhidos",
                    "Localizacao do concurso contextualizada"
                    if localizacao.get("contexto_urbano")
                    else None,
                    "Criterios de adjudicacao identificados"
                    if criterios.get("resumo")
                    else None,
                    "Equipa tecnica analisada"
                    if equipa
                    else None,
                )
                if item
            ],
            "riscos": criterios.get("barreiras", []),
        },
        "analise_ai": {
            "score": score,
            "gerada_em": datetime.utcnow().isoformat() + "Z",
            "origem": "worker_backend_cnll",
            "interpretacao_documental": analise_documental.get("origem"),
        },
    }

    return ficha, score


def _pasta_final(concurso: dict, job_id: int) -> Path:
    identificador = _id_base(concurso.get("link")) or str(concurso["id"])
    direta = ANALISES_DIR / identificador
    if (direta / "ficha.json").exists():
        return direta / "jobs" / str(job_id)
    return direta


def _guardar_resultados(
    *,
    pasta: Path,
    textos: dict[str, str],
    documentos: list[dict],
    resumo_documentos: dict,
    ficha: dict,
) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "textos.json").write_text(
        json.dumps(textos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (pasta / "analise.json").write_text(
        json.dumps(
            {
                "preparacao": ficha.get("decisao", {}),
                "resumo": resumo_documentos,
                "documentos": documentos,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    destino = pasta / "ficha.json"
    destino.write_text(
        json.dumps(ficha, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destino


def _copiar_documentos_existentes(
    concurso: dict,
    destino: Path,
) -> bool:
    identificador = _id_base(concurso.get("link")) or str(concurso["id"])
    origem = ANALISES_DIR / identificador
    if not origem.exists():
        return False

    pdfs = list(origem.rglob("*.pdf"))
    textos = origem / "textos.json"
    if not pdfs and not textos.exists():
        return False

    destino.mkdir(parents=True, exist_ok=True)
    for pdf in pdfs:
        alvo = destino / pdf.relative_to(origem)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf, alvo)

    if textos.exists():
        shutil.copy2(textos, destino / "textos.json")

    return True


def _fase_extracao(job: dict, concurso: dict, pasta_job: Path) -> Path:
    job_id = job["id"]
    _verificar_cancelamento(job_id)

    pasta_download = pasta_job / "download"
    pasta_extraida = pasta_job / "extraido"
    pasta_download.mkdir(parents=True, exist_ok=True)

    if _copiar_documentos_existentes(concurso, pasta_extraida):
        return pasta_extraida

    link_pecas = _texto_limpo(concurso.get("link_pecas"))
    if not link_pecas:
        raise WorkerErro(
            "O concurso nao tem link de pecas do procedimento."
        )

    ficheiro = _descarregar(link_pecas, pasta_download)
    _verificar_cancelamento(job_id)
    _extrair_archivos_recursivo(ficheiro, pasta_extraida)
    return pasta_extraida


def _fase_processamento(job: dict, pasta_extraida: Path) -> tuple[dict, list, dict]:
    job_id = job["id"]
    _verificar_cancelamento(job_id)

    textos_existentes = pasta_extraida / "textos.json"
    if textos_existentes.exists():
        try:
            textos = json.loads(
                textos_existentes.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            textos = {}
    else:
        textos = _extrair_textos(pasta_extraida)

    documentos, resumo_documentos = _classificar_documentos(pasta_extraida)

    if not textos:
        raise WorkerErro(
            "Nao foi possivel extrair texto pesquisavel dos documentos."
        )

    return textos, documentos, resumo_documentos


def limpar_temporarios_job(job_id: int) -> None:
    pasta = (JOBS_TEMP_DIR / str(job_id)).resolve()
    raiz = JOBS_TEMP_DIR.resolve()
    if pasta.exists() and raiz in pasta.parents:
        shutil.rmtree(pasta)


def processar_job(job: dict) -> bool:
    job_id = job["id"]
    concurso_id = job["concurso_id"]
    pasta_job = JOBS_TEMP_DIR / str(job_id)

    try:
        concurso = concurso_por_id(concurso_id)
        if concurso is None:
            raise WorkerErro("Concurso nao encontrado.")

        atualizar_analise_job(job_id, "extracao", 25)
        pasta_extraida = _fase_extracao(job, concurso, pasta_job)

        atualizar_analise_job(job_id, "processamento", 50)
        textos, documentos, resumo_documentos = _fase_processamento(
            job,
            pasta_extraida,
        )
        _verificar_cancelamento(job_id)
        analise_documental = analisar_documentos_ai(
            textos=textos,
            documentos=documentos,
            titulo=_texto_limpo(concurso.get("titulo"))
            or "Concurso sem titulo",
        )

        atualizar_analise_job(job_id, "geracao", 75)
        _verificar_cancelamento(job_id)
        ficha, score = _gerar_ficha(
            concurso=concurso,
            job=job,
            textos=textos,
            documentos=documentos,
            resumo_documentos=resumo_documentos,
            analise_documental=analise_documental,
        )
        atualizar_localizacao_concurso(
            concurso_id,
            ficha.get("localizacao", {}),
        )
        destino = _guardar_resultados(
            pasta=_pasta_final(concurso, job_id),
            textos=textos,
            documentos=documentos,
            resumo_documentos=resumo_documentos,
            ficha=ficha,
        )

        resultado = guardar_analise(
            concurso_id=concurso_id,
            nivel="AI",
            resumo=ficha["decisao"]["classificacao"],
            dados_json=json.dumps(ficha, ensure_ascii=False),
            user_id=job["user_id"],
            job_id=job_id,
            score=score,
            ficheiro_ficha=destino.relative_to(BASE_DIR).as_posix(),
        )
        if not resultado:
            raise JobCancelado()

        limpar_temporarios_job(job_id)
        return True

    except JobCancelado:
        limpar_temporarios_job(job_id)
        return False
    except Exception as erro:
        logger.exception("Erro ao processar analise job %s", job_id)
        atualizar_analise_job(job_id, "erro", 0, str(erro)[:1000])
        limpar_temporarios_job(job_id)
        return False


def processar_proximo_job() -> bool:
    job = reivindicar_proximo_analise_job()
    if job is None:
        return False
    processar_job(job)
    return True


async def executar_worker(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        houve_job = await asyncio.to_thread(processar_proximo_job)
        if houve_job:
            continue

        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=POLL_INTERVALO,
            )
