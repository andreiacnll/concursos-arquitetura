from __future__ import annotations

import asyncio
import hashlib
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

import py7zr
import requests
from pypdf import PdfReader

from app.analise.classificador import classificar_documento
from app.analise.criterios import analisar_criterios, analisar_criterios_documentos
from app.analise.document_ai import analisar_documentos_ai
from app.analise.equipa import analisar_equipa, analisar_equipa_documentos
from app.analise.gerador import gerar_perfil_concurso
from app.analise.normalizador_equipa import normalizar_subfatores
from app.analise.platform_documents import (
    detect_platform,
    discover_public_documents,
    download_public_documents,
    load_cached_platform_documents,
    save_platform_metadata,
    sha256_file,
)
from app.analise.reader import (
    SPREADSHEET_EXTENSIONS,
    create_source_manifest,
    extract_spreadsheet_text,
    read_architecture_documents,
)
from app.company_ai.company_context import build_company_context
from app.company_ai.competition_context import build_competition_context
from app.company_ai.compatibility_analysis import analyze_compatibility
from app.company_ai.recommendation_engine import generate_recommendation
from app.database import (
    analise_job_esta_cancelado,
    atualizar_analise_job,
    atualizar_dados_concurso,
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


def _nome_download(
    conteudo: bytes,
    content_type: str,
) -> str:
    tipo = content_type.casefold()

    if conteudo.startswith(b"7z\xbc\xaf'\x1c"):
        return "pecas.7z"

    if (
        conteudo.startswith(b"PK")
        or "zip" in tipo
    ):
        return "pecas.zip"

    if (
        conteudo.startswith(b"%PDF")
        or "pdf" in tipo
    ):
        return "documento.pdf"

    return "documentos.bin"


def _limites_download_direto() -> tuple[int, int]:
    max_documento = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_DOCUMENTO_MB",
                "550",
            )
        )
        * 1024
        * 1024
    )

    max_pacote = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_PACOTE_MB",
                "4096",
            )
        )
        * 1024
        * 1024
    )

    return max_documento, max_pacote


def _descarregar(url: str, destino: Path) -> Path:
    _validar_url_download(url)
    _aguardar_download()

    max_documento, max_pacote = _limites_download_direto()

    resposta = requests.get(
        url,
        timeout=TIMEOUT_DOWNLOAD,
        allow_redirects=True,
        stream=True,
        headers={
            "User-Agent": (
                "CNLL/1.0 "
                "(analise moderada de documentos oficiais)"
            ),
            "Accept": "*/*",
        },
    )

    resposta.raise_for_status()

    iterator = resposta.iter_content(
        chunk_size=1024 * 1024,
    )

    primeiro = b""

    try:
        for chunk in iterator:
            if chunk:
                primeiro = chunk
                break

        if not primeiro:
            raise WorkerErro(
                "Download de documentos vazio."
            )

        content_type = resposta.headers.get(
            "content-type",
            "",
        )

        nome = _nome_download(
            primeiro[:16],
            content_type,
        )

        if nome == "documentos.bin":
            raise WorkerErro(
                "A resposta dos documentos nao parece ZIP, 7z nem PDF."
            )

        eh_pacote = nome.endswith(
            (".zip", ".7z")
        )

        limite = (
            max_pacote
            if eh_pacote
            else max_documento
        )

        declared_raw = resposta.headers.get(
            "content-length",
            "",
        ).strip()

        if declared_raw:
            try:
                declared = int(declared_raw)
            except (TypeError, ValueError):
                declared = 0

            if declared > limite:
                raise WorkerErro(
                    "O download excede o limite configurado "
                    f"({declared / 1024 / 1024:.1f} MB > "
                    f"{limite / 1024 / 1024:.1f} MB)."
                )

        destino.mkdir(
            parents=True,
            exist_ok=True,
        )

        caminho = destino / nome
        total = 0

        try:
            with caminho.open("wb") as handle:
                total += len(primeiro)

                if total > limite:
                    raise WorkerErro(
                        "O download excede o limite configurado."
                    )

                handle.write(primeiro)

                for chunk in iterator:
                    if not chunk:
                        continue

                    total += len(chunk)

                    if total > limite:
                        raise WorkerErro(
                            "O download excede o limite configurado."
                        )

                    handle.write(chunk)

        except Exception:
            caminho.unlink(
                missing_ok=True,
            )
            raise

        return caminho

    finally:
        resposta.close()


def _validar_membros_arquivo(
    nomes: list[str],
    destino: Path,
) -> None:
    destino_resolvido = destino.resolve()
    for nome in nomes:
        alvo = (destino / nome).resolve()
        if (
            alvo != destino_resolvido
            and destino_resolvido not in alvo.parents
        ):
            raise WorkerErro(
                f"Arquivo contém caminho inseguro: {nome}"
            )


def _limites_extracao() -> tuple[int, int, int, int, int, int, int]:
    max_membro = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_MEMBRO_EXTRAIDO_MB",
                "550",
            )
        )
        * 1024
        * 1024
    )
    max_total = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_TOTAL_EXTRAIDO_MB",
                "1600",
            )
        )
        * 1024
        * 1024
    )
    max_ficheiros = max(
        1,
        int(
            os.getenv(
                "CNLL_ANALISE_MAX_FICHEIROS_EXTRAIDOS",
                "300",
            )
        ),
    )
    max_profundidade = max(
        0,
        int(
            os.getenv(
                "CNLL_ANALISE_MAX_PROFUNDIDADE_ARQUIVOS",
                "5",
            )
        ),
    )
    max_arquivo_interno = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_ARQUIVO_INTERNO_MB",
                "4096",
            )
        )
        * 1024
        * 1024
    )
    max_total_arquivos_internos = int(
        float(
            os.getenv(
                "CNLL_ANALISE_MAX_TOTAL_ARQUIVOS_INTERNOS_MB",
                "8192",
            )
        )
        * 1024
        * 1024
    )
    max_arquivos_internos = max(
        1,
        int(
            os.getenv(
                "CNLL_ANALISE_MAX_ARQUIVOS_INTERNOS",
                "50",
            )
        ),
    )

    return (
        max_membro,
        max_total,
        max_ficheiros,
        max_profundidade,
        max_arquivo_interno,
        max_total_arquivos_internos,
        max_arquivos_internos,
    )


def _novo_orcamento_extracao() -> dict[str, int]:
    (
        max_membro,
        max_total,
        max_ficheiros,
        max_profundidade,
        max_arquivo_interno,
        max_total_arquivos_internos,
        max_arquivos_internos,
    ) = _limites_extracao()

    return {
        "max_membro": max_membro,
        "max_total": max_total,
        "max_ficheiros": max_ficheiros,
        "max_profundidade": max_profundidade,
        "max_arquivo_interno": max_arquivo_interno,
        "max_total_arquivos_internos": max_total_arquivos_internos,
        "max_arquivos_internos": max_arquivos_internos,
        "total_extraido": 0,
        "ficheiros_extraidos": 0,
        "total_arquivos_internos": 0,
        "arquivos_internos_extraidos": 0,
    }


def _extensoes_analisaveis_arquivo() -> set[str]:
    from app.analise.common_project_extractor import (
        DOCX_EXTENSIONS,
    )

    return {
        ".pdf",
        ".txt",
        ".zip",
        ".7z",
        *{
            str(ext).casefold()
            for ext in DOCX_EXTENSIONS
        },
        *{
            str(ext).casefold()
            for ext in SPREADSHEET_EXTENSIONS
        },
    }


def _normalizar_nome_prioridade(nome: str) -> str:
    import unicodedata

    normalizado = unicodedata.normalize(
        "NFKD",
        nome.casefold(),
    )
    return "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(caractere)
    )


def _prioridade_membro_arquivo(nome: str) -> int:
    probe = _normalizar_nome_prioridade(nome)

    marcadores = (
        (100, "programa"),
        (100, "caderno"),
        (100, "regulamento"),
        (100, "criter"),
        (100, "adjudic"),
        (100, "requisit"),
        (70, "proposta"),
        (70, "condic"),
        (70, "termos"),
        (70, "esclarec"),
        (70, "cronograma"),
        (50, "prazo"),
        (40, "quadro"),
        (40, "mapa"),
        (40, "areas"),
        (30, "memoria"),
        (10, "anexo"),
    )

    return sum(
        peso
        for peso, marcador in marcadores
        if marcador in probe
    )


def _consumir_orcamento_extracao(
    orcamento: dict[str, int],
    tamanho: int,
    ficheiros: int = 1,
) -> None:
    orcamento["total_extraido"] += max(0, tamanho)
    orcamento["ficheiros_extraidos"] += max(0, ficheiros)


def _consumir_orcamento_arquivo_interno(
    orcamento: dict[str, int],
    tamanho: int,
) -> None:
    orcamento["total_arquivos_internos"] += max(
        0,
        tamanho,
    )
    orcamento["arquivos_internos_extraidos"] += 1


def _ficheiro_cabe_no_orcamento(
    orcamento: dict[str, int],
    nome: str,
    tamanho: int,
) -> bool:
    if tamanho < 0:
        return False

    if tamanho > orcamento["max_membro"]:
        logger.warning(
            "Ficheiro ignorado por exceder limite individual: "
            "%s (%.1f MB)",
            nome,
            tamanho / (1024 * 1024),
        )
        return False

    if (
        orcamento["ficheiros_extraidos"]
        >= orcamento["max_ficheiros"]
    ):
        logger.warning(
            "Limite global de %s ficheiros extraidos atingido.",
            orcamento["max_ficheiros"],
        )
        return False

    if (
        orcamento["total_extraido"] + tamanho
        > orcamento["max_total"]
    ):
        logger.warning(
            "Ficheiro ignorado para respeitar limite global "
            "extraido: %s (%.1f MB)",
            nome,
            tamanho / (1024 * 1024),
        )
        return False

    return True


def _selecionar_membros_extraiveis(
    membros: list[tuple[str, int]],
    orcamento: dict[str, int],
) -> list[tuple[str, int]]:
    extensoes = _extensoes_analisaveis_arquivo()

    candidatos = [
        (nome, tamanho)
        for nome, tamanho in membros
        if (
            Path(nome).suffix.casefold() in extensoes
            and tamanho >= 0
        )
    ]

    candidatos.sort(
        key=lambda item: (
            -_prioridade_membro_arquivo(item[0]),
            item[1],
            item[0].casefold(),
        )
    )

    selecionados: list[tuple[str, int]] = []

    total_documentos_planeado = 0
    documentos_planeados = 0

    total_arquivos_planeado = 0
    arquivos_planeados = 0

    for nome, tamanho in candidatos:
        suffix = Path(nome).suffix.casefold()
        eh_arquivo = suffix in {".zip", ".7z"}

        if eh_arquivo:
            if tamanho > orcamento["max_arquivo_interno"]:
                logger.warning(
                    "Arquivo interno ignorado por exceder limite: "
                    "%s (%.1f MB)",
                    nome,
                    tamanho / (1024 * 1024),
                )
                continue

            if (
                orcamento["arquivos_internos_extraidos"]
                + arquivos_planeados
                >= orcamento["max_arquivos_internos"]
            ):
                logger.warning(
                    "Limite global de arquivos internos atingido."
                )
                break

            if (
                orcamento["total_arquivos_internos"]
                + total_arquivos_planeado
                + tamanho
                > orcamento["max_total_arquivos_internos"]
            ):
                logger.warning(
                    "Arquivo interno ignorado para respeitar "
                    "limite temporario: %s (%.1f MB)",
                    nome,
                    tamanho / (1024 * 1024),
                )
                continue

            selecionados.append((nome, tamanho))
            total_arquivos_planeado += tamanho
            arquivos_planeados += 1
            continue

        if tamanho > orcamento["max_membro"]:
            logger.warning(
                "Membro ignorado por exceder limite individual: "
                "%s (%.1f MB)",
                nome,
                tamanho / (1024 * 1024),
            )
            continue

        if (
            orcamento["ficheiros_extraidos"]
            + documentos_planeados
            >= orcamento["max_ficheiros"]
        ):
            break

        if (
            orcamento["total_extraido"]
            + total_documentos_planeado
            + tamanho
            > orcamento["max_total"]
        ):
            logger.warning(
                "Membro ignorado para respeitar limite global "
                "extraido: %s (%.1f MB)",
                nome,
                tamanho / (1024 * 1024),
            )
            continue

        selecionados.append((nome, tamanho))
        total_documentos_planeado += tamanho
        documentos_planeados += 1

    return selecionados


def _zip_info_eh_symlink(info) -> bool:
    modo = (info.external_attr >> 16) & 0o170000
    return modo == 0o120000


def _extrair_zip_seguro(
    ficheiro_zip: Path,
    destino: Path,
    orcamento: dict[str, int],
) -> list[Path]:
    internos: list[Path] = []

    with ZipFile(ficheiro_zip) as zip_file:
        infos = zip_file.infolist()

        _validar_membros_arquivo(
            [
                membro.filename
                for membro in infos
            ],
            destino,
        )

        membros = [
            (
                membro.filename,
                int(membro.file_size or 0),
            )
            for membro in infos
            if (
                not membro.is_dir()
                and not _zip_info_eh_symlink(membro)
            )
        ]

        selecionados = _selecionar_membros_extraiveis(
            membros,
            orcamento,
        )

        logger.info(
            "ZIP %s: %s/%s membros selecionados.",
            ficheiro_zip.name,
            len(selecionados),
            len(membros),
        )

        for nome, tamanho in selecionados:
            zip_file.extract(
                nome,
                path=destino,
            )
            extraido = destino / Path(nome)

            if _tipo_arquivo(extraido):
                _consumir_orcamento_arquivo_interno(
                    orcamento,
                    tamanho,
                )
                internos.append(extraido)
            else:
                _consumir_orcamento_extracao(
                    orcamento,
                    tamanho,
                )

    return internos


def _extrair_7z_seguro(
    ficheiro_7z: Path,
    destino: Path,
    orcamento: dict[str, int],
) -> list[Path]:
    try:
        with py7zr.SevenZipFile(
            ficheiro_7z,
            mode="r",
        ) as archive:
            infos = archive.list()

            nomes = [
                info.filename
                for info in infos
            ]

            _validar_membros_arquivo(
                nomes,
                destino,
            )

            membros = [
                (
                    info.filename,
                    int(info.uncompressed or 0),
                )
                for info in infos
                if (
                    info.is_file
                    and not info.is_symlink
                )
            ]

            selecionados = _selecionar_membros_extraiveis(
                membros,
                orcamento,
            )

            logger.info(
                "7Z %s: %s/%s membros selecionados.",
                ficheiro_7z.name,
                len(selecionados),
                len(membros),
            )

            if not selecionados:
                return []

            nomes_selecionados = [
                nome
                for nome, _ in selecionados
            ]

            archive.extract(
                path=destino,
                targets=nomes_selecionados,
            )

            internos: list[Path] = []

            for nome, tamanho in selecionados:
                extraido = destino / Path(nome)

                if _tipo_arquivo(extraido):
                    _consumir_orcamento_arquivo_interno(
                        orcamento,
                        tamanho,
                    )
                    internos.append(extraido)
                else:
                    _consumir_orcamento_extracao(
                        orcamento,
                        tamanho,
                    )

            return internos

    except py7zr.Bad7zFile as erro:
        raise WorkerErro(
            "O pacote de documentos nao e um 7z valido."
        ) from erro


def _tipo_arquivo(caminho: Path) -> str:
    suffix = caminho.suffix.casefold()

    # Office Open XML usa ZIP internamente, mas deve continuar
    # a ser tratado como documento logico.
    if suffix in {
        ".docx", ".docm",
        ".xlsx", ".xlsm",
        ".pptx", ".pptm",
    }:
        return ""

    try:
        with caminho.open("rb") as ficheiro:
            header = ficheiro.read(8)
    except OSError:
        header = b""

    if header.startswith(b"PK"):
        return "zip"
    if header.startswith(b"7z\xbc\xaf'\x1c"):
        return "7z"

    if suffix == ".zip":
        return "zip"
    if suffix == ".7z":
        return "7z"

    return ""


def _extrair_arquivo_seguro(
    arquivo: Path,
    destino: Path,
    orcamento: dict[str, int],
) -> list[Path]:
    tipo = _tipo_arquivo(arquivo)

    if tipo == "zip":
        try:
            return _extrair_zip_seguro(
                arquivo,
                destino,
                orcamento,
            )
        except BadZipFile as erro:
            raise WorkerErro(
                "O pacote de documentos nao e um ZIP valido."
            ) from erro

    if tipo == "7z":
        return _extrair_7z_seguro(
            arquivo,
            destino,
            orcamento,
        )

    raise WorkerErro(
        "O pacote de documentos nao e ZIP nem 7z."
    )


def _extrair_archivos_recursivo(
    origem: Path,
    destino: Path,
    orcamento: dict[str, int] | None = None,
    profundidade: int = 0,
) -> None:
    destino.mkdir(parents=True, exist_ok=True)

    if orcamento is None:
        orcamento = _novo_orcamento_extracao()

    try:
        with origem.open("rb") as ficheiro:
            header = ficheiro.read(8)
    except OSError:
        header = b""

    if (
        origem.suffix.lower() == ".pdf"
        and header.startswith(b"%PDF")
    ):
        tamanho = origem.stat().st_size

        if not _ficheiro_cabe_no_orcamento(
            orcamento,
            origem.name,
            tamanho,
        ):
            return

        shutil.copy2(
            origem,
            destino / origem.name,
        )
        _consumir_orcamento_extracao(
            orcamento,
            tamanho,
        )
        return

    internos = _extrair_arquivo_seguro(
        origem,
        destino,
        orcamento,
    )

    if profundidade >= orcamento["max_profundidade"]:
        if internos:
            logger.warning(
                "Profundidade maxima de arquivos atingida em %s.",
                origem.name,
            )
        return

    for arquivo_interno in internos:
        nova_pasta = (
            arquivo_interno.parent
            / arquivo_interno.stem
        )
        nova_pasta.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            _extrair_archivos_recursivo(
                arquivo_interno,
                nova_pasta,
                orcamento,
                profundidade + 1,
            )
        except WorkerErro as erro:
            logger.warning(
                "Nao foi possivel extrair arquivo interno %s: %s",
                arquivo_interno,
                erro,
            )


def _extrair_texto_pdf(caminho: Path) -> str:
    try:
        leitor = PdfReader(str(caminho))
    except Exception as erro:
        logger.warning("Nao foi possivel abrir PDF %s: %s", caminho, erro)
        return ""

    # Avoid retaining one string per page before producing the final document text.
    texto_extraido = ""
    primeira_pagina = True
    for pagina in leitor.pages:
        try:
            texto_pagina = pagina.extract_text() or ""
        except Exception:
            continue
        if not primeira_pagina:
            texto_extraido += "\n"
        texto_extraido += texto_pagina
        primeira_pagina = False
    return texto_extraido.strip()


def _extrair_textos(pasta: Path) -> dict[str, str]:
    from app.analise.common_project_extractor import (
        DOCX_EXTENSIONS,
        extract_docx_text,
    )

    textos: dict[str, str] = {}
    for pdf in pasta.rglob("*.pdf"):
        texto = _extrair_texto_pdf(pdf)
        if texto:
            textos[str(pdf.relative_to(pasta))] = texto

    for ficheiro in pasta.rglob("*"):
        if not ficheiro.is_file():
            continue

        suffix = ficheiro.suffix.casefold()
        relative = str(ficheiro.relative_to(pasta))

        if suffix in DOCX_EXTENSIONS:
            texto = extract_docx_text(ficheiro)
            if texto:
                textos[relative] = texto
            continue

        if suffix not in SPREADSHEET_EXTENSIONS:
            continue

        try:
            texto, structured = extract_spreadsheet_text(
                ficheiro,
                display_name=relative,
            )
        except Exception as erro:
            logger.warning(
                "Nao foi possivel ler folha de calculo %s: %s",
                ficheiro,
                erro,
            )
            continue
        if texto and (structured.get("tables") or []):
            textos[relative] = texto
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
        if ficheiro.suffix.lower() in {".zip", ".7z"}:
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


def _iterar_frases(texto):
    documentos = (texto,) if isinstance(texto, str) else texto
    delimitadores = re.compile(r"(?<=[.;:])\s+|\n+")
    for documento in documentos:
        documento = str(documento or "")
        inicio = 0
        for delimitador in delimitadores.finditer(documento):
            yield documento[inicio:delimitador.start()]
            inicio = delimitador.end()
        yield documento[inicio:]

def _frases_com_termos(
    texto: str,
    termos: tuple[str, ...],
    limite: int = 8,
) -> list[str]:
    encontrados: list[str] = []
    vistos: set[str] = set()
    frases = _iterar_frases(texto)
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


def _lista_unica_contexto(valores: object, limite: int = 20) -> list[str]:
    if valores is None:
        return []
    if isinstance(valores, dict):
        candidatos = []
        for valor in valores.values():
            candidatos.extend(_lista_unica_contexto(valor, limite=limite))
    elif isinstance(valores, list):
        candidatos = valores
    else:
        candidatos = [valores]

    resultado: list[str] = []
    vistos: set[str] = set()
    for valor in candidatos:
        texto = _texto_limpo(valor)
        if not texto:
            continue
        chave = _sem_acentos(texto.lower())
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(texto)
        if len(resultado) >= limite:
            break
    return resultado


def _texto_contexto_concurso(competition_context: dict) -> str:
    return _sem_acentos(
        json.dumps(competition_context, ensure_ascii=False).lower()
    )


def _filtrar_relevantes(
    valores_empresa: list[str],
    competition_context: dict,
    limite: int = 10,
) -> list[str]:
    texto_concurso = _texto_contexto_concurso(competition_context)
    relevantes = []
    for valor in valores_empresa:
        normalizado = _sem_acentos(valor.lower())
        if len(normalizado) >= 3 and normalizado in texto_concurso:
            relevantes.append(valor)
        if len(relevantes) >= limite:
            break
    return relevantes


def _fontes_company_context(company_context: dict) -> list[dict]:
    knowledge = company_context.get("knowledge", {})
    memory = knowledge.get("memory", []) if isinstance(knowledge, dict) else []
    fontes = []
    for fact in memory:
        if not isinstance(fact, dict):
            continue
        fontes.append(
            {
                "field": fact.get("field"),
                "source": fact.get("source"),
                "source_type": fact.get("source_type"),
                "status": fact.get("status"),
                "confidence": fact.get("confidence"),
                "url": fact.get("url"),
            }
        )
    return fontes


def _extrair_projectos_relevantes(
    company_profile: dict,
    competition_context: dict,
) -> list[dict]:
    projetos = []
    texto_concurso = _texto_contexto_concurso(competition_context)
    for projeto in company_profile.get("project_experience") or []:
        if not isinstance(projeto, dict):
            continue
        campos = _lista_unica_contexto(
            [
                projeto.get("name"),
                projeto.get("typology"),
                projeto.get("location"),
                projeto.get("skills_demonstrated"),
            ]
        )
        if not campos:
            continue
        if any(
            len(_sem_acentos(campo.lower())) >= 3
            and _sem_acentos(campo.lower()) in texto_concurso
            for campo in campos
        ):
            projetos.append(
                {
                    "name": projeto.get("name"),
                    "typology": projeto.get("typology"),
                    "location": projeto.get("location"),
                    "skills_demonstrated": projeto.get(
                        "skills_demonstrated",
                        [],
                    ),
                    "source": "CompanyProfile.project_experience",
                }
            )
    return projetos[:8]


def _calcular_score_compatibilidade(
    matches: list[dict],
    gaps: list[dict],
    unknowns: list[str],
) -> int:
    score = 50 + len(matches) * 12 - len(gaps) * 8 - len(unknowns) * 4
    return max(0, min(100, score))


def _decisao_final(score: int, gaps: list[dict], unknowns: list[str]) -> str:
    if score >= 72 and not gaps:
        return "avancar"
    if score >= 55:
        return "avaliar"
    if unknowns and score >= 45:
        return "dados insuficientes"
    return "nao prioritario"


def _resumo_limite_frase(texto: object, limite: int = 280) -> str:
    texto_limpo = _texto_limpo(texto)
    if len(texto_limpo) <= limite:
        return texto_limpo

    janela = texto_limpo[:limite].rstrip()
    fim_frase = max(
        janela.rfind("."),
        janela.rfind("?"),
        janela.rfind("!"),
    )
    if fim_frase < max(60, limite // 3):
        fim_frase = janela.rfind(";")
    if fim_frase < max(60, limite // 3):
        fim_frase = janela.rfind(" ")
    if fim_frase <= 0:
        return janela.rstrip(" ,;:") + "..."
    return janela[: fim_frase + 1].rstrip(" ,;:") + "..."


def _limpar_valor_evidencia(valor: object) -> str:
    texto = _texto_limpo(valor)
    while texto and texto[0] in {'"', "'", "-", "•"}:
        texto = texto[1:].strip()
    while texto and texto[-1] in {'"', "'", ",", ";"}:
        texto = texto[:-1].strip()
    return texto


def _evidence(
    value: object,
    *,
    source_document: str = "Pecas analisadas",
    section: str = "",
    confidence: float = 0.72,
    status: str = "confirmado",
) -> dict:
    text = _limpar_valor_evidencia(value)
    return {
        "value": text or "Nao identificado nas pecas analisadas",
        "source_document": source_document,
        "page": None,
        "section": section,
        "confidence": confidence,
        "status": status if text else "por validar",
        "evidence_excerpt": _resumo_limite_frase(text, 280) if text else "",
    }


def _items_evidence(
    values: object,
    *,
    source_document: str = "Pecas analisadas",
    section: str = "",
    confidence: float = 0.72,
) -> list[dict]:
    return [
        _evidence(
            value,
            source_document=source_document,
            section=section,
            confidence=confidence,
        )
        for value in _lista_unica_contexto(values, limite=30)
    ]


def _document_sources(
    documentos: list[dict],
    resumo_documentos: dict,
) -> list[dict]:
    sources = []
    platform = resumo_documentos.get("source_platform_status") or {}
    platform_docs = platform.get("documents") or []
    for item in platform_docs:
        if not isinstance(item, dict):
            continue
        sources.append(
            {
                "name": item.get("filename") or item.get("external_id"),
                "classification": "peca do procedimento",
                "format": Path(str(item.get("filename") or "")).suffix.lower().lstrip("."),
                "pages": None,
                "status": "analisado",
                "origin": platform.get("platform") or "plataforma",
                "source_url": item.get("source_url"),
                "sha256": item.get("sha256"),
            }
        )
    for item in documentos or []:
        if not isinstance(item, dict):
            continue
        name = item.get("nome") or item.get("name") or item.get("ficheiro")
        if not name:
            continue
        if any(source.get("name") == name for source in sources):
            continue
        sources.append(
            {
                "name": name,
                "classification": item.get("tipo") or item.get("classificacao"),
                "format": Path(str(name)).suffix.lower().lstrip("."),
                "pages": item.get("paginas"),
                "status": "analisado",
                "origin": (
                    "historico"
                    if str(name).startswith("ficha_")
                    else platform.get("platform")
                    or "documento"
                ),
            }
        )
    if not sources:
        sources.append(
            {
                "name": "Ficha estruturada existente",
                "classification": "analise anterior",
                "format": "json",
                "pages": None,
                "status": "analisado",
                "origin": "historico",
            }
        )
    return sources


def _build_document_insights(
    ficha: dict,
    concurso: dict,
    documentos: list[dict],
    resumo_documentos: dict,
) -> dict:
    reader = resumo_documentos.get("architecture_reader")
    if isinstance(reader, dict):
        procedure = reader.get("procedure_identity") or {}
        phases = reader.get("phases_and_deliverables") or []
        document_quality = _document_quality_from_resumo(resumo_documentos)
        audit = _auditoria_documental(resumo_documentos)
        return {
            "document_quality": document_quality,
            "document_audit": audit,
            "limited_documentation_notice": (
                "A analise empresarial foi realizada com informacao documental limitada."
                if document_quality in {"announcement_only", "unavailable", "partial"}
                else ""
            ),
            "procedure_summary": {
                "object": procedure.get("object") or _evidence(
                    concurso.get("titulo"),
                    source_document="Anuncio BASE",
                    section="Objeto",
                    confidence=0.55,
                ),
                "contracting_entity": procedure.get("entity") or _evidence(
                    concurso.get("entidade"),
                    source_document="Anuncio BASE",
                    section="Entidade adjudicante",
                    confidence=0.55,
                ),
                "procedure_type": procedure.get("procedure_type") or _evidence(
                    concurso.get("tipo_procedimento"),
                    source_document="Anuncio BASE",
                    section="Procedimento",
                    confidence=0.55,
                ),
                "base_price": _evidence(
                    concurso.get("preco_base"),
                    source_document="Anuncio BASE",
                    section="Preco base",
                    confidence=0.55,
                ),
                "submission_deadline": _evidence(
                    concurso.get("data_entrega_propostas") or concurso.get("data_limite"),
                    source_document="Anuncio BASE",
                    section="Prazo candidatura",
                    confidence=0.55,
                ),
                "execution_deadline": _evidence(
                    "",
                    source_document="Pecas analisadas",
                    section="Prazo execucao",
                    confidence=0.0,
                ),
                "location": _evidence(
                    concurso.get("morada") or concurso.get("freguesia") or concurso.get("municipio"),
                    source_document="Anuncio BASE",
                    section="Localizacao",
                    confidence=0.55,
                ),
                "platform": _evidence(
                    resumo_documentos.get("source_platform_status", {}).get("platform"),
                    source_document="Manifesto de fontes",
                    section="Plataforma",
                    confidence=0.6,
                ),
                "documents_count": len(reader.get("sources") or []),
                "document_quality": document_quality,
            },
            "timeline": [
                {
                    "type": item.get("section") or "prazo",
                    "value": item.get("value"),
                    "date": item.get("value"),
                    "confirmed": item.get("status") == "confirmado",
                    "evidence": item,
                }
                for phase in phases
                for item in phase.get("timeline", [])
                if isinstance(item, dict)
            ],
            "award_criteria": reader.get("award_strategy", {}).get("criteria") or [],
            "deliverables": [
                {
                    "phase": phase.get("phase") or "fase identificada",
                    "items": phase.get("items") or [],
                    "format": "",
                    "quantity": "",
                    "scale": "",
                    "deadline": "",
                    "validation": "por validar",
                }
                for phase in phases
            ],
            "required_documents": [
                {
                    "group": "proposta",
                    "items": reader.get("submission_documents") or [],
                },
                {
                    "group": "habilitacao",
                    "items": reader.get("post_award_documents") or [],
                },
            ],
            "required_team": reader.get("required_team") or [],
            "financial_conditions": reader.get("financial_conditions") or {},
            "intellectual_property": [],
            "exclusion_risks": reader.get("exclusion_risks") or [],
            "technical_constraints": reader.get("technical_constraints") or [],
            "document_alerts": reader.get("document_alerts") or [],
            "sources": reader.get("sources") or [],
        }

    identificacao = ficha.get("identificacao", {})
    economia = ficha.get("economia", {})
    investimento = ficha.get("investimento", {})
    criterios = ficha.get("criterios", {})
    entregaveis = ficha.get("entregaveis", {})
    equipa_bruta = ficha.get("equipa", {})
    equipa = equipa_bruta if isinstance(equipa_bruta, dict) else {}
    programa = ficha.get("programa", {})
    localizacao = ficha.get("localizacao", {})
    source_doc = "Pecas analisadas"

    award_criteria = []
    for item in criterios.get("percentagens") or []:
        if not isinstance(item, dict):
            continue
        if not _texto_limpo(item.get("criterio")):
            continue
        award_criteria.append(
            {
                "factor": _texto_limpo(item.get("criterio")),
                "weight": _texto_limpo(item.get("percentagem")),
                "subfactors": [],
                "formula": "",
                "tie_breaker": "",
                "abnormally_low_price": "",
                "evidence": _evidence(
                    " ".join(
                        part
                        for part in (
                            _texto_limpo(item.get("criterio")),
                            _texto_limpo(item.get("percentagem")),
                        )
                        if part
                    ),
                    source_document=source_doc,
                    section="Criterios de adjudicacao",
                ),
            }
        )
    if not award_criteria and criterios.get("criterio_adjudicacao"):
        award_criteria.append(
            {
                "factor": _texto_limpo(criterios.get("criterio_adjudicacao")),
                "weight": "",
                "subfactors": [],
                "formula": "",
                "tie_breaker": "",
                "abnormally_low_price": "",
                "evidence": _evidence(
                    criterios.get("criterio_adjudicacao"),
                    source_document=source_doc,
                    section="Criterios de adjudicacao",
                ),
            }
        )

    deliverable_values = (
        entregaveis.get("principais")
        or entregaveis.get("elementos_obrigatorios")
        or entregaveis.get("documentos_escritos")
        or []
    )
    deliverables = [
        {
            "phase": "proposta",
            "items": _items_evidence(
                deliverable_values,
                source_document=source_doc,
                section="Entregaveis",
            ),
            "format": _texto_limpo(entregaveis.get("formato_pecas")),
            "quantity": _texto_limpo(entregaveis.get("numero_paineis")),
            "scale": _texto_limpo(entregaveis.get("escalas_exigidas")),
            "deadline": _texto_limpo(investimento.get("prazo_projeto")),
            "validation": "por validar",
        }
    ] if deliverable_values else []

    timeline = []
    for label, value in (
        ("publicacao", concurso.get("data")),
        ("entrega_proposta", concurso.get("data_entrega_propostas") or concurso.get("data_limite")),
        ("prazo_execucao", investimento.get("prazo_projeto")),
    ):
        text = _texto_limpo(value)
        if text:
            timeline.append(
                {
                    "type": label,
                    "value": text,
                    "date": text,
                    "confirmed": True,
                    "evidence": _evidence(
                        text,
                        source_document=source_doc,
                        section="Calendario",
                    ),
                }
            )

    required_team = []
    especialidades_ficha = []
    if isinstance(ficha.get("especialidades"), dict):
        especialidades_ficha = ficha.get("especialidades", {}).get("lista") or []

    for label, values in (
        ("perfis profissionais", equipa.get("equipa_minima")),
        ("especialidades", equipa.get("especialidades") or especialidades_ficha),
        ("consultores", equipa.get("consultores_obrigatorios")),
        ("habilitacoes", equipa.get("habilitacoes_exigidas")),
    ):
        for item in _lista_unica_contexto(values, limite=20):
            required_team.append(
                {
                    "requirement": item,
                    "category": label,
                    "minimum_count": None,
                    "minimum_years": None,
                    "order_registration": "Ordem" in item,
                    "status": "confirmado",
                    "evidence": _evidence(
                        item,
                        source_document=source_doc,
                        section="Equipa exigida",
                    ),
                }
            )

    financial = {
        key: _evidence(value, source_document=source_doc, section="Condicoes financeiras")
        for key, value in {
            "preco_base": economia.get("valor_procedimento") or concurso.get("preco_base"),
            "honorarios": economia.get("honorarios"),
            "premios": ficha.get("modelo_concurso", {}).get("premios"),
            "caucao": economia.get("caucao"),
            "pagamentos": economia.get("pagamentos"),
            "observacoes": economia.get("observacoes"),
        }.items()
        if _texto_limpo(value)
    }

    technical_constraints = _items_evidence(
        list(programa.get("condicionantes") or [])
        + _lista_unica_contexto(localizacao.get("contexto_urbano")),
        source_document=source_doc,
        section="Condicionantes tecnicas",
    )
    exclusion_risks = _items_evidence(
        ficha.get("analise_ai", {}).get("riscos")
        or ficha.get("requisitos", {}).get("riscos_participacao")
        or [],
        source_document=source_doc,
        section="Riscos de exclusao",
        confidence=0.68,
    )

    return {
        "procedure_summary": {
            "object": _evidence(
                programa.get("descricao")
                or programa.get("resumo")
                or programa.get("resumo_intervencao")
                or identificacao.get("titulo"),
                source_document=source_doc,
                section="Objeto",
            ),
            "contracting_entity": _evidence(
                identificacao.get("entidade") or concurso.get("entidade"),
                source_document=source_doc,
                section="Entidade adjudicante",
            ),
            "procedure_type": _evidence(
                identificacao.get("tipo_procedimento") or concurso.get("tipo_procedimento"),
                source_document=source_doc,
                section="Procedimento",
            ),
            "base_price": _evidence(
                economia.get("valor_procedimento") or concurso.get("preco_base"),
                source_document=source_doc,
                section="Preco base",
            ),
            "submission_deadline": _evidence(
                concurso.get("data_entrega_propostas") or concurso.get("data_limite"),
                source_document=source_doc,
                section="Prazo candidatura",
            ),
            "execution_deadline": _evidence(
                investimento.get("prazo_projeto"),
                source_document=source_doc,
                section="Prazo execucao",
            ),
            "location": _evidence(
                localizacao.get("morada")
                or localizacao.get("freguesia")
                or identificacao.get("localizacao"),
                source_document=source_doc,
                section="Localizacao",
            ),
            "platform": _evidence(
                resumo_documentos.get("source_platform_status", {}).get("platform"),
                source_document=source_doc,
                section="Plataforma",
                confidence=0.6,
            ),
            "documents_count": len(_document_sources(documentos, resumo_documentos)),
        },
        "timeline": timeline,
        "award_criteria": award_criteria,
        "deliverables": deliverables,
        "required_documents": [
            {
                "group": "proposta tecnica",
                "items": _items_evidence(
                    entregaveis.get("documentos_escritos") or deliverable_values,
                    source_document=source_doc,
                    section="Documentos obrigatorios",
                ),
            }
        ] if deliverable_values else [],
        "required_team": required_team,
        "financial_conditions": financial,
        "intellectual_property": [],
        "exclusion_risks": exclusion_risks,
        "technical_constraints": technical_constraints,
        "document_alerts": _items_evidence(
            resumo_documentos.get("avisos") or [],
            source_document=source_doc,
            section="Alertas documentais",
            confidence=0.65,
        ),
        "sources": _document_sources(documentos, resumo_documentos),
    }


def _profile_has_content(profile: dict) -> bool:
    identity = profile.get("identity") or {}
    experience = profile.get("experience") or {}
    competences = profile.get("competences") or {}
    return any(
        _texto_limpo(value)
        for value in (
            identity.get("name"),
            identity.get("role"),
            identity.get("specialization"),
        )
    ) or any(
        _lista_unica_contexto(values)
        for values in (
            experience.get("projects"),
            experience.get("typologies"),
            experience.get("sectors"),
            experience.get("responsibilities"),
            competences.get("technical"),
            competences.get("software"),
            competences.get("methodologies"),
        )
    )


def _team_context_from_company_context(
    company_context: dict,
    competition_context: dict,
) -> tuple[dict, str]:
    team = company_context.get("team") or {}
    members = team.get("members") or []
    relevant_members = []
    specializations = []
    competences = []
    roles = []
    gaps = []

    for item in members:
        if not isinstance(item, dict):
            continue
        profile = item.get("profile") or {}
        if not _profile_has_content(profile):
            continue
        identity = profile.get("identity") or {}
        member_competences = profile.get("competences") or {}
        member_experience = profile.get("experience") or {}
        role = _texto_limpo(identity.get("role"))
        specialization = _texto_limpo(identity.get("specialization"))
        technical = _lista_unica_contexto(member_competences.get("technical"))
        methods = _lista_unica_contexto(member_competences.get("methodologies"))
        member_specializations = _lista_unica_contexto(
            [specialization]
            + list(member_experience.get("typologies") or [])
            + list(member_experience.get("sectors") or [])
        )
        if role:
            roles.append(role)
        specializations.extend(member_specializations)
        competences.extend(technical + methods)
        relevant_members.append(
            {
                "name": _texto_limpo(identity.get("name")) or "Perfil sem nome publico",
                "professional_role": role,
                "specializations": member_specializations[:5],
                "competences": (technical + methods)[:6],
                "coverage": _filtrar_relevantes(
                    member_specializations + technical + methods,
                    competition_context,
                    limite=5,
                ),
            }
        )

    if not relevant_members:
        gaps.append("Nao existem ainda perfis de equipa suficientes para avaliar a cobertura.")
    confidence = 0.35 if not relevant_members else min(0.9, 0.45 + len(relevant_members) * 0.12)
    result = {
        "members_count": int(team.get("member_count") or len(members)),
        "profiled_members_count": len(relevant_members),
        "relevant_members_count": len(
            [member for member in relevant_members if member.get("coverage")]
        ),
        "specializations": _lista_unica_contexto(specializations, limite=20),
        "competences": _lista_unica_contexto(competences, limite=20),
        "roles": _lista_unica_contexto(roles, limite=12),
        "coverage": _lista_unica_contexto(
            [
                coverage
                for member in relevant_members
                for coverage in member.get("coverage", [])
            ],
            limite=20,
        ),
        "gaps": gaps,
        "confidence": round(confidence, 2),
        "relevant_members": relevant_members[:4],
    }
    team_hash = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return result, team_hash


def _factor_texts(values: object, limite: int = 12) -> list[str]:
    result: list[str] = []
    for item in values or []:
        if isinstance(item, dict):
            text = (
                item.get("explanation")
                or item.get("name")
                or item.get("field")
                or item.get("status")
            )
        else:
            text = item
        clean = _limpar_valor_evidencia(text)
        if clean:
            result.append(clean)
        if len(result) >= limite:
            break
    return _lista_unica_contexto(result, limite=limite)


def _enriquecer_ficha_com_empresa(ficha: dict, company_id: int | None) -> dict:
    ficha["analysis_schema_version"] = "2026-08-company-analysis-v2"
    ficha["recommendation_algorithm_version"] = "company-intelligence-award-fit-v15.7"
    ficha["updated_at"] = datetime.utcnow().isoformat() + "Z"
    if company_id is None:
        ficha["company_profile_version"] = None
        ficha["company_profile_hash"] = None
        ficha["company_context"] = {
            "company_id": None,
            "personalizada": False,
            "missing_information": [
                "Nao foi encontrada empresa associada ao utilizador autenticado."
            ],
        }
        ficha["adequacao_empresa"] = {
            "score_compatibilidade": None,
            "informacao_em_falta": ficha["company_context"][
                "missing_information"
            ],
            "limitacoes": [
                "Analise empresarial nao personalizada por falta de company_id."
            ],
        }
        ficha["recomendacao_final"] = {
            "decisao": "dados insuficientes",
            "motivos": [
                "Nao existe contexto empresarial suficiente para recomendar."
            ],
        }
        return ficha

    document_quality = str(ficha.get("document_quality") or "unavailable")
    limited_documentation = document_quality in {
        "partial",
        "announcement_only",
        "unavailable",
    }
    documentation_reason = (
        "A analise empresarial foi realizada com informacao documental limitada."
        if limited_documentation
        else "A analise empresarial usou pecas oficiais aceites pelo reader."
    )
    competition_context = build_competition_context(ficha).model_dump()
    company_context_model = build_company_context(company_id)
    company_context = company_context_model.model_dump()
    company_context_hash = hashlib.sha256(
        json.dumps(
            company_context,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    compatibility = analyze_compatibility(
        company_context,
        competition_context,
    )
    team_context, team_hash = _team_context_from_company_context(
        company_context,
        competition_context,
    )
    recommendation = generate_recommendation(
        company_id,
        competition_context.get("competition_id"),
        compatibility,
    )

    company_profile = (
        company_context.get("company", {}).get("profile", {})
        if isinstance(company_context.get("company"), dict)
        else {}
    )
    services = _lista_unica_contexto(company_profile.get("services"))
    competences = _lista_unica_contexto(company_profile.get("competences"))
    specializations = _lista_unica_contexto(
        company_profile.get("specializations")
    )
    preferences = company_profile.get("preferences") or {}
    strategy = company_profile.get("strategy") or {}
    from app.analise.procedure_analysis import assess_company_award_fit

    award_criteria_fit = assess_company_award_fit(
        ficha.get("procedure_analysis") or {},
        company_profile,
        team_context,
    )
    projetos_relevantes = _extrair_projectos_relevantes(
        company_profile,
        competition_context,
    )

    matches = list(compatibility.matches)
    gaps = list(compatibility.gaps)
    unknowns = list(compatibility.unknowns)
    missing = _lista_unica_contexto(
        list(company_context.get("missing_information") or [])
        + list(compatibility.missing_information)
        + unknowns
    )
    score_compatibilidade = _calcular_score_compatibilidade(
        matches,
        gaps,
        missing,
    )
    if compatibility.score is not None:
        score_compatibilidade = int(compatibility.score)

    score_antes_criterios = score_compatibilidade
    criterio_penalty = int(award_criteria_fit.get("penalty") or 0)
    if criterio_penalty > 0:
        score_compatibilidade = max(0, score_compatibilidade - criterio_penalty)
        gaps.append({
            "field": "Experiência diretamente pontuada",
            "severity": "high" if criterio_penalty >= 18 else "medium",
            "explanation": award_criteria_fit.get("explanation"),
            "source": "procedure_analysis.award_criteria",
        })

    decisao = _decisao_final(score_compatibilidade, gaps, missing)
    recomendacao_exp = dict(compatibility.recommendation or {})
    if recomendacao_exp.get("decision") and criterio_penalty == 0:
        decisao = str(recomendacao_exp["decision"])
    elif criterio_penalty >= 18:
        decisao = "Concorrer apenas com reforço comprovado da equipa ou do portefólio"
    elif criterio_penalty > 0 and score_compatibilidade < 55:
        decisao = "Compatibilidade condicionada pela experiência pontuada"

    adjusted_explanation = _texto_limpo(recomendacao_exp.get("explanation"))
    if award_criteria_fit.get("active"):
        award_explanation = _texto_limpo(award_criteria_fit.get("explanation"))
        adjusted_explanation = " ".join(
            part for part in (adjusted_explanation, award_explanation) if part
        )
    recomendacao_exp["decision"] = decisao
    recomendacao_exp["explanation"] = adjusted_explanation

    ficha["analise_concurso"] = {
        "objeto": ficha.get("programa", {}).get("descricao"),
        "prazo": ficha.get("investimento", {}).get("prazo_projeto"),
        "preco": ficha.get("economia", {}).get("valor_procedimento"),
        "procedimento": ficha.get("identificacao", {}).get(
            "tipo_procedimento"
        ),
        "criterios": ficha.get("criterios"),
        "entregaveis": ficha.get("entregaveis", {}).get("principais", []),
        "requisitos": ficha.get("requisitos", {}).get("obrigatorios", []),
        "riscos_documentais": ficha.get("requisitos", {}).get(
            "riscos_participacao",
            [],
        ),
    }
    ficha["company_context"] = {
        "company_id": company_id,
        "personalizada": True,
        "profile_snapshot": company_profile,
        "knowledge_memory": company_context.get("knowledge", {}).get(
            "memory",
            [],
        ),
        "sources": _fontes_company_context(company_context),
        "missing_information": missing,
    }
    ficha["adequacao_empresa"] = {
        "score_compatibilidade": score_compatibilidade,
        "compatibility_explanation": {
            "score": compatibility.score,
            "confidence": compatibility.confidence,
            "confidence_reasons": list(compatibility.confidence_reasons),
            "positive_factors": list(compatibility.positive_factors),
            "negative_factors": list(compatibility.negative_factors),
            "missing_information": list(compatibility.missing_information),
            "evidence": list(compatibility.evidence),
            "score_explanation": dict(compatibility.score_explanation),
        },
        "confidence": {
            "level": compatibility.confidence,
            "reasons": list(compatibility.confidence_reasons),
        },
        "experience_summary": list(compatibility.experience_summary),
        "award_criteria_fit": {
            **award_criteria_fit,
            "score_before_penalty": score_antes_criterios,
            "score_after_penalty": score_compatibilidade,
        },
        "experiencia_semelhante_encontrada": projetos_relevantes,
        "servicos_compativeis": _filtrar_relevantes(
            services,
            competition_context,
        ),
        "competencias_relevantes": _filtrar_relevantes(
            competences,
            competition_context,
        ),
        "especializacoes_relevantes": _filtrar_relevantes(
            specializations,
            competition_context,
        ),
        "projetos_de_referencia": projetos_relevantes,
        "preferencias_estrategicas": {
            "tipologias": preferences.get("typologies", []),
            "procedimentos": preferences.get("procedures", []),
            "localizacoes": preferences.get("locations", []),
            "escala": preferences.get("project_scale", []),
            "areas_prioritarias": strategy.get("priority_areas", []),
            "areas_secundarias": strategy.get("secondary_areas", []),
            "areas_a_evitar": strategy.get("avoid_areas", []),
            "objetivos_futuros": strategy.get("future_goals", []),
        },
        "matches": matches,
        "lacunas": gaps,
        "requisitos_importantes": list(compatibility.requirements),
        "riscos_identificados": list(compatibility.risks),
        "oportunidades": list(compatibility.opportunities),
        "informacao_em_falta": missing,
        "limitacoes": [
            "A adequacao usa apenas CompanyProfile, Knowledge Memory e fontes validadas/processadas.",
            "Nao assume experiencia nao existente no perfil empresarial.",
        ] + ([documentation_reason] if limited_documentation else []),
        "document_basis": {
            "document_quality": document_quality,
            "limited": limited_documentation,
            "notice": documentation_reason if limited_documentation else "",
            "fields_missing": list(
                (ficha.get("document_audit") or {}).get("fields_missing") or []
            ),
        },
        "possiveis_parceiros_ou_especialidades_necessarias": [
            gap.get("field")
            for gap in gaps
            if isinstance(gap, dict) and gap.get("field")
        ],
        "evidencia": list(compatibility.evidence),
    }
    ficha["company_matching"] = {
        "company_id": company_id,
        "competition_id": competition_context.get("competition_id"),
        "score": score_compatibilidade,
        "source_score": compatibility.score,
        "score_compatibilidade": score_compatibilidade,
        "award_criteria_fit": {
            **award_criteria_fit,
            "score_before_penalty": score_antes_criterios,
            "score_after_penalty": score_compatibilidade,
        },
        "compatibility_breakdown": list(
            compatibility.compatibility_breakdown
        ),
        "matched_projects": list(compatibility.matched_projects),
        "matched_services": list(compatibility.matched_services),
        "matched_competences": list(compatibility.matched_competences),
        "matched_specializations": list(
            compatibility.matched_specializations
        ),
        "strengths": list(compatibility.strengths),
        "weaknesses": list(compatibility.weaknesses),
        "strategic_fit": dict(compatibility.strategic_fit),
        "missing_information": missing,
        "recommendation": recomendacao_exp,
        "confidence": {
            "level": compatibility.confidence,
            "reasons": list(compatibility.confidence_reasons),
        },
        "evidence": list(compatibility.evidence),
        "company_profile_hash": company_context_hash,
        "analysis_schema_version": "company_matching_v15.7",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    ficha["recomendacao_final"] = {
        "decisao": decisao,
        "confianca": (
            "baixa"
            if limited_documentation
            and str(compatibility.confidence).lower() not in {"baixa", "low"}
            else compatibility.confidence
        ),
        "explicacao": adjusted_explanation,
        "riscos_principais": _lista_unica_contexto(
            list(recomendacao_exp.get("main_risks") or [])
            + [
                item.get("name")
                for item in award_criteria_fit.get("missing_requirements") or []
                if isinstance(item, dict) and item.get("name")
            ],
            limite=8,
        ),
        "status_motor_recomendacao": recommendation.status,
        "motivos": recommendation.reasons,
        "dados_insuficientes": missing,
    }
    company_strengths = _lista_unica_contexto(
        _factor_texts(compatibility.positive_factors)
        + services
        + competences
        + specializations,
        limite=8,
    )
    team_strengths = _lista_unica_contexto(
        team_context.get("coverage") or team_context.get("competences"),
        limite=8,
    )
    combined_strengths = _lista_unica_contexto(
        company_strengths + team_strengths,
        limite=10,
    )
    ficha["team_context"] = team_context
    ficha["joint_assessment"] = {
        "company_strengths": company_strengths,
        "team_strengths": team_strengths,
        "combined_strengths": combined_strengths,
        "coverage": _lista_unica_contexto(
            _factor_texts(compatibility.requirements)
            + list(team_context.get("coverage") or []),
            limite=12,
        ),
        "gaps": _lista_unica_contexto(
            list(team_context.get("gaps") or []) + missing,
            limite=12,
        ),
        "summary": " ".join(
            part
            for part in (
                "A empresa apresenta sinais de compatibilidade com o concurso."
                if company_strengths
                else "O perfil empresarial ainda tem informacao insuficiente.",
                "A equipa tem cobertura parcial dos requisitos identificados."
                if team_strengths
                else "Nao existem perfis de equipa suficientes para confirmar cobertura.",
            )
            if part
        ),
    }
    ficha["decision_summary"] = {
        "score": score_compatibilidade,
        "classification": ficha.get("decisao", {}).get("classificacao"),
        "confidence": (
            "baixa"
            if limited_documentation
            and str(compatibility.confidence).lower() not in {"baixa", "low"}
            else compatibility.confidence
        ),
        "recommendation": decisao,
        "top_strengths": combined_strengths[:3],
        "top_risks": _lista_unica_contexto(
            _factor_texts(compatibility.risks)
            + list(ficha.get("decisao", {}).get("riscos") or []),
            limite=3,
        ),
        "top_opportunities": _lista_unica_contexto(
            _factor_texts(compatibility.opportunities)
            + list(ficha.get("decisao", {}).get("oportunidades") or []),
            limite=3,
        ),
    }
    ficha["compatibility_explanation"] = ficha["adequacao_empresa"][
        "compatibility_explanation"
    ]
    ficha["requirements"] = list(compatibility.requirements)
    ficha["risks"] = list(compatibility.risks)
    ficha["opportunities"] = list(compatibility.opportunities)
    ficha["experience_summary"] = list(compatibility.experience_summary)
    ficha["confidence"] = ficha["adequacao_empresa"]["confidence"]
    if limited_documentation:
        ficha["adequacao_empresa"]["confidence"] = {
            **(
                ficha["adequacao_empresa"]["confidence"]
                if isinstance(
                    ficha.get("adequacao_empresa", {}).get("confidence"),
                    dict,
                )
                else {}
            ),
            "level": "baixa",
            "reasons": _lista_unica_contexto(
                list(
                    (
                        ficha.get("adequacao_empresa", {})
                        .get("confidence", {})
                        .get("reasons", [])
                    )
                )
                + [documentation_reason],
                limite=8,
            ),
        }
        ficha["confidence"] = {
            **(
                ficha["confidence"]
                if isinstance(ficha.get("confidence"), dict)
                else {}
            ),
            "level": "baixa",
            "reasons": _lista_unica_contexto(
                list(
                    (
                        ficha.get("adequacao_empresa", {})
                        .get("confidence", {})
                        .get("reasons", [])
                    )
                )
                + [documentation_reason],
                limite=8,
            ),
        }
        ficha["analise_ai"]["document_limited"] = True
        ficha["analise_ai"]["document_quality"] = document_quality
    ficha["evidence"] = list(compatibility.evidence)
    ficha["analise_ai"]["company_id"] = company_id
    ficha["analise_ai"]["personalizada"] = True
    ficha["analise_ai"]["company_context_builder"] = "build_company_context"
    ficha["analise_ai"]["competition_context_builder"] = (
        "build_competition_context"
    )
    ficha["company_profile_version"] = (
        company_profile.get("updated_at")
        or company_context.get("updated_at")
        or company_context.get("generated_at")
    )
    ficha["company_profile_hash"] = company_context_hash
    ficha["team_profile_hash"] = team_hash
    return ficha


def _gerar_ficha(
    *,
    concurso: dict,
    job: dict,
    textos: dict[str, str],
    documentos: list[dict],
    resumo_documentos: dict,
    analise_documental: dict,
) -> tuple[dict, int]:
    documentos_texto = textos.values()
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
    criterios = _criterios_do_concurso_documentos(concurso, documentos_texto)
    equipa_bruta = analisar_equipa_documentos(documentos_texto)
    equipa = normalizar_subfatores(
        equipa_bruta.get("subfatores_equipa", [])
    )
    estrategia = gerar_perfil_concurso(criterios, equipa)
    score = _calcular_score(resumo_documentos, criterios, equipa)
    localizacao = resolver_localizacao(concurso, documentos=documentos_texto)
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
        or _extrair_valor_documentos(documentos_texto)
    )
    prazo = (
        _texto_limpo(concurso.get("data_entrega_propostas"))
        or _texto_limpo(concurso.get("data_limite"))
    )
    espacos_ai = _lista_texto(
        programa_funcional.get("espacos_principais")
    )
    funcoes = _juntar_listas(
        _extrair_funcoes_documentos(documentos_texto, titulo),
        espacos_ai,
        limite=16,
    )
    areas_ai = _lista_texto(programa_funcional.get("areas"))
    areas = _areas_para_programa(_extrair_areas_documentos(documentos_texto), areas_ai)
    entregaveis = _juntar_listas(
        _lista_texto(analise_documental.get("entregaveis")),
        _extrair_entregaveis_textos(documentos_texto, concurso),
        limite=18,
    )
    especialidades = _juntar_listas(
        _extrair_especialidades_documentos(documentos_texto),
        _lista_texto(equipa_ai.get("especialidades")),
        limite=18,
    )
    requisitos = _enriquecer_requisitos(
        _extrair_requisitos_textos(documentos_texto),
        programa_funcional,
        equipa_ai,
    )
    sintese_programa = (
        _texto_limpo(programa_funcional.get("sintese"))
        or _sintese_programa_textos(documentos_texto, titulo, funcoes)
    )
    if len(sintese_programa) < 220:
        sintese_programa = _sintese_programa_textos(documentos_texto, titulo, funcoes)
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
            "tipo": _extrair_tipo_intervencao_documentos(documentos_texto, titulo),
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
    ficha["document_quality"] = _document_quality_from_resumo(
        resumo_documentos
    )
    ficha["document_audit"] = _auditoria_documental(resumo_documentos)
    ficha["document_insights"] = _build_document_insights(
        ficha,
        concurso,
        documentos,
        resumo_documentos,
    )

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

    try:
        from .intervention_program import apply_intervention_program

        intervention_program = apply_intervention_program(
            ficha=ficha,
            textos=textos,
        )
    except Exception as erro:
        intervention_program = {
            "active": False,
            "version": "intervention-program-v1",
            "warnings": [f"{type(erro).__name__}: {erro}"],
        }

    if intervention_program.get("active"):
        resumo_documentos["intervention_program"] = intervention_program

    try:
        from .semantic_product_bridge import (
            attach_semantic_product_data,
        )

        semantic_product = attach_semantic_product_data(
            textos=textos,
            ficha=ficha,
        )
    except Exception as erro:
        semantic_product = {
            "status": "fallback",
            "version": "semantic-product-v0.1",
            "warnings": [
                f"{type(erro).__name__}: {erro}"
            ],
        }

    if semantic_product.get("status") != "disabled":
        resumo_documentos["semantic_product"] = (
            semantic_product
        )

    compact_consolidated = (
        ficha.get("architecture_intelligence", {})
        .get("consolidated")
        if isinstance(
            ficha.get("architecture_intelligence"),
            dict,
        )
        else None
    )
    if isinstance(compact_consolidated, dict):
        (pasta / "consolidated.json").write_text(
            json.dumps(
                compact_consolidated,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    _escrever_textos_json(pasta / "textos.json", textos)
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


def _escrever_textos_json(caminho: Path, textos: dict[str, str]) -> None:
    """Serializa os textos por partes, sem criar uma segunda string global."""
    with caminho.open("w", encoding="utf-8") as ficheiro:
        json.dump(textos, ficheiro, ensure_ascii=False, indent=2)


def _copiar_documentos_existentes(
    concurso: dict,
    destino: Path,
    orcamento: dict[str, int],
) -> bool:
    identificador = (
        _id_base(concurso.get("link"))
        or str(concurso["id"])
    )
    origem = ANALISES_DIR / identificador

    if not origem.exists():
        return False

    extensoes = {
        ".pdf",
        ".txt",
        ".docx",
        ".docm",
        *SPREADSHEET_EXTENSIONS,
    }

    fontes = [
        ficheiro
        for ficheiro in origem.rglob("*")
        if (
            ficheiro.is_file()
            and ficheiro.suffix.casefold() in extensoes
            and not (
                {
                    "jobs",
                    ".jobs",
                    "plataforma_publica",
                }
                & {
                    part.lower()
                    for part in ficheiro.relative_to(origem).parts
                }
            )
        )
    ]

    if not fontes:
        return False

    fontes.sort(
        key=lambda ficheiro: (
            -_prioridade_membro_arquivo(
                str(ficheiro.relative_to(origem))
            ),
            ficheiro.stat().st_size,
            str(ficheiro).casefold(),
        )
    )

    destino.mkdir(
        parents=True,
        exist_ok=True,
    )

    copiados = 0

    for fonte in fontes:
        tamanho = fonte.stat().st_size
        relativo = fonte.relative_to(origem)

        if not _ficheiro_cabe_no_orcamento(
            orcamento,
            str(relativo),
            tamanho,
        ):
            continue

        alvo = destino / relativo
        alvo.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            fonte,
            alvo,
        )
        _consumir_orcamento_extracao(
            orcamento,
            tamanho,
        )
        copiados += 1

    return copiados > 0


def _cache_plataforma_dir(concurso: dict) -> Path:
    identificador = (
        _id_base(concurso.get("link"))
        or str(concurso["id"])
    )
    return (
        ANALISES_DIR
        / identificador
        / "plataforma_publica"
    )


def _extensoes_cache_processada() -> set[str]:
    from app.analise.common_project_extractor import (
        DOCX_EXTENSIONS,
    )

    return {
        ".pdf",
        ".txt",
        *{
            str(ext).casefold()
            for ext in DOCX_EXTENSIONS
        },
        *{
            str(ext).casefold()
            for ext in SPREADSHEET_EXTENSIONS
        },
    }


def _cache_processada_dir(cache_dir: Path) -> Path:
    return cache_dir / "processado"


def _manifesto_cache_processada(cache_dir: Path) -> Path:
    return cache_dir / "processed_manifest.json"


def _guardar_cache_processada(
    origem: Path,
    cache_dir: Path,
) -> int:
    extensoes = _extensoes_cache_processada()

    ignorar = {
        "base_announcement.json",
        "source_manifest.json",
    }

    fontes = [
        ficheiro
        for ficheiro in origem.rglob("*")
        if (
            ficheiro.is_file()
            and ficheiro.name not in ignorar
            and ficheiro.suffix.casefold() in extensoes
        )
    ]

    if not fontes:
        return 0

    fontes.sort(
        key=lambda ficheiro: (
            -_prioridade_membro_arquivo(
                str(ficheiro.relative_to(origem))
            ),
            ficheiro.stat().st_size,
            str(ficheiro).casefold(),
        )
    )

    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destino_final = _cache_processada_dir(cache_dir)
    destino_temp = cache_dir / "processado.tmp"

    if destino_temp.exists():
        shutil.rmtree(
            destino_temp,
            ignore_errors=True,
        )

    destino_temp.mkdir(
        parents=True,
        exist_ok=True,
    )

    documentos: list[dict[str, object]] = []

    try:
        for fonte in fontes:
            relativo = fonte.relative_to(origem)

            alvo = destino_temp / relativo
            alvo.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(fonte, alvo)

            documentos.append(
                {
                    "path": relativo.as_posix(),
                    "size": alvo.stat().st_size,
                    "sha256": sha256_file(alvo),
                }
            )

        if destino_final.exists():
            shutil.rmtree(
                destino_final,
                ignore_errors=True,
            )

        destino_temp.replace(destino_final)

        manifesto = {
            "version": 1,
            "documents": documentos,
        }

        manifesto_path = _manifesto_cache_processada(
            cache_dir
        )

        manifesto_temp = cache_dir / (
            "processed_manifest.json.tmp"
        )

        manifesto_temp.write_text(
            json.dumps(
                manifesto,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        manifesto_temp.replace(
            manifesto_path
        )

        logger.info(
            "Cache processada criada com %s documentos em %s.",
            len(documentos),
            cache_dir,
        )

        return len(documentos)

    except Exception:
        if destino_temp.exists():
            shutil.rmtree(
                destino_temp,
                ignore_errors=True,
            )
        raise


def _carregar_manifesto_cache_processada(
    cache_dir: Path,
) -> list[tuple[Path, Path, int]]:
    manifesto_path = _manifesto_cache_processada(
        cache_dir
    )

    if not manifesto_path.exists():
        return []

    try:
        dados = json.loads(
            manifesto_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []

    if dados.get("version") != 1:
        return []

    processado = _cache_processada_dir(
        cache_dir
    )

    if not processado.exists():
        return []

    documentos: list[
        tuple[Path, Path, int]
    ] = []

    for item in dados.get("documents") or []:
        if not isinstance(item, dict):
            return []

        relativo_raw = item.get("path")
        sha_esperado = str(
            item.get("sha256") or ""
        ).strip()

        try:
            tamanho_esperado = int(
                item.get("size")
            )
        except (
            TypeError,
            ValueError,
        ):
            return []

        if (
            not relativo_raw
            or not sha_esperado
            or tamanho_esperado < 0
        ):
            return []

        relativo = Path(
            str(relativo_raw)
        )

        # O manifesto s? pode apontar para caminhos
        # relativos dentro da cache processada.
        if (
            relativo.is_absolute()
            or ".." in relativo.parts
        ):
            return []

        ficheiro = processado / relativo

        if (
            not ficheiro.is_file()
            or ficheiro.is_symlink()
        ):
            return []

        tamanho = ficheiro.stat().st_size

        if tamanho != tamanho_esperado:
            return []

        if sha256_file(
            ficheiro
        ) != sha_esperado:
            return []

        documentos.append(
            (
                ficheiro,
                relativo,
                tamanho,
            )
        )

    return documentos


def _copiar_cache_processada(
    cache_dir: Path,
    destino: Path,
    orcamento: dict[str, int],
) -> bool:
    documentos = (
        _carregar_manifesto_cache_processada(
            cache_dir
        )
    )

    if not documentos:
        return False

    documentos.sort(
        key=lambda item: (
            -_prioridade_membro_arquivo(
                item[1].as_posix()
            ),
            item[2],
            item[1].as_posix().casefold(),
        )
    )

    copiados = 0

    for fonte, relativo, tamanho in documentos:
        if not _ficheiro_cabe_no_orcamento(
            orcamento,
            relativo.as_posix(),
            tamanho,
        ):
            continue

        alvo = destino / relativo

        alvo.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            fonte,
            alvo,
        )

        _consumir_orcamento_extracao(
            orcamento,
            tamanho,
        )

        copiados += 1

    if copiados:
        logger.info(
            "Cache processada reutilizada: %s documentos.",
            copiados,
        )

    return copiados > 0


def _limpar_cache_bruta_plataforma(
    cache_dir: Path,
) -> None:
    downloads = cache_dir / "downloads"

    if downloads.exists():
        shutil.rmtree(
            downloads,
            ignore_errors=True,
        )

        logger.info(
            "Cache bruta removida apos criacao "
            "da cache processada: %s",
            downloads,
        )


def _copiar_documento_cache(
    documento_path: Path,
    destino: Path,
    orcamento: dict[str, int],
) -> bool:
    destino.mkdir(
        parents=True,
        exist_ok=True,
    )

    antes = orcamento[
        "ficheiros_extraidos"
    ]

    if _tipo_arquivo(documento_path):
        _extrair_archivos_recursivo(
            documento_path,
            destino,
            orcamento,
        )

        return (
            orcamento[
                "ficheiros_extraidos"
            ]
            > antes
        )

    tamanho = documento_path.stat().st_size

    if not _ficheiro_cabe_no_orcamento(
        orcamento,
        documento_path.name,
        tamanho,
    ):
        return False

    alvo = destino / documento_path.name

    shutil.copy2(
        documento_path,
        alvo,
    )

    _consumir_orcamento_extracao(
        orcamento,
        tamanho,
    )

    return True


def _copiar_cache_plataforma(
    cache_dir: Path,
    destino: Path,
    orcamento: dict[str, int],
) -> bool:
    # Preferir sempre a cache leve.
    if _copiar_cache_processada(
        cache_dir,
        destino,
        orcamento,
    ):
        return True

    # Primeira utiliza??o ou compatibilidade com cache antiga.
    documentos = load_cached_platform_documents(
        cache_dir
    )

    if not documentos:
        return False

    copiados = 0

    for documento in documentos:
        if _copiar_documento_cache(
            cache_dir / documento.path,
            destino,
            orcamento,
        ):
            copiados += 1

    if not copiados:
        return False

    try:
        guardados = _guardar_cache_processada(
            destino,
            cache_dir,
        )

        # S? apagamos o bruto se a cache leve foi criada.
        if guardados > 0:
            validados = (
                _carregar_manifesto_cache_processada(
                    cache_dir
                )
            )

            if len(validados) == guardados:
                _limpar_cache_bruta_plataforma(
                    cache_dir
                )
            else:
                logger.warning(
                    "Cache processada nao passou validacao; "
                    "cache bruta preservada em %s.",
                    cache_dir,
                )

    except Exception as erro:
        logger.warning(
            "Nao foi possivel criar cache processada em %s: %s",
            cache_dir,
            erro,
        )

    return True


def _tem_documentos_ou_fallback(pasta: Path) -> bool:
    ignorar = {"base_announcement.json", "source_manifest.json"}
    return any(
        ficheiro.is_file() and ficheiro.name not in ignorar
        for ficheiro in pasta.rglob("*")
    )


def _metadata_plataforma_publica(concurso: dict) -> dict:
    cache_dir = _cache_plataforma_dir(concurso)
    metadata = cache_dir / "metadata.json"
    if not metadata.exists():
        plataforma, platform_url = detect_platform(concurso)
        return {
            "platform": plataforma,
            "platform_url": platform_url,
            "status": "not_checked",
            "documents": [],
            "warnings": [],
        }
    try:
        data = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        plataforma, platform_url = detect_platform(concurso)
        return {
            "platform": plataforma,
            "platform_url": platform_url,
            "status": "metadata_unreadable",
            "documents": [],
            "warnings": [],
        }
    status = data.get("status")
    documents = []
    for item in data.get("documents") or []:
        if not isinstance(item, dict):
            continue
        documents.append(
            {
                "external_id": item.get("external_id"),
                "source_url": item.get("source_url"),
                "filename": item.get("filename"),
                "sha256": item.get("sha256"),
            }
        )
    if not status and not documents and data.get("warnings"):
        joined = " ".join(str(item) for item in data.get("warnings") or [])
        if "Nenhum documento" in joined:
            status = "no_documents"
        elif data.get("requires_login"):
            status = "login_required"
    return {
        "platform": data.get("platform"),
        "platform_url": data.get("platform_url"),
        "status": status,
        "requires_login": bool(data.get("requires_login")),
        "used_playwright": bool(data.get("used_playwright")),
        "documents": documents,
        "warnings": list(data.get("warnings") or []),
    }


def _source_platform_status_para_textos(
    concurso: dict,
    textos: dict[str, str],
    metadata: dict,
) -> dict:
    plataforma, platform_url = detect_platform(concurso)
    if plataforma == "unknown" or metadata.get("documents"):
        return metadata

    nomes = [
        nome
        for nome in textos
        if nome and Path(nome).name.lower() != "dados_concurso.txt"
    ]
    if not nomes:
        return metadata

    warnings = list(metadata.get("warnings") or [])
    if metadata.get("status") in {None, "not_checked", "success"}:
        warnings.append(
            "Documentos processados ja existiam persistidos; "
            "os binarios originais nao foram retransferidos neste job."
        )
    return {
        **metadata,
        "platform": metadata.get("platform") or plataforma,
        "platform_url": metadata.get("platform_url") or platform_url,
        "status": "existing_documents",
        "documents": [
            {
                "external_id": nome,
                "source_url": platform_url,
                "filename": nome,
                "sha256": None,
            }
            for nome in nomes
        ],
        "warnings": warnings,
    }


def _document_quality_from_resumo(resumo_documentos: dict) -> str:
    reader = resumo_documentos.get("architecture_reader")
    if isinstance(reader, dict) and reader.get("document_quality"):
        return str(reader["document_quality"])
    manifest = resumo_documentos.get("source_manifest") or {}
    items = manifest.get("items") or []
    has_reader_doc = any(item.get("accepted_for_reader") for item in items)
    has_announcement = any(
        item.get("source_type") == "official_announcement"
        for item in items
    )
    if has_reader_doc:
        return "partial"
    if has_announcement:
        return "announcement_only"
    return "unavailable"


def _campos_documentais(resumo_documentos: dict) -> tuple[list[str], list[str]]:
    reader = resumo_documentos.get("architecture_reader")
    if isinstance(reader, dict):
        return (
            list(reader.get("fields_filled") or []),
            list(reader.get("fields_missing") or []),
        )
    return [], [
        "criterios",
        "equipa",
        "fases_entregaveis",
        "documentos_proposta",
        "documentos_habilitacao",
        "condicoes_financeiras",
        "riscos_exclusao",
        "condicionantes_tecnicas",
    ]


def _auditoria_documental(resumo_documentos: dict) -> dict:
    manifest = resumo_documentos.get("source_manifest") or {}
    platform = resumo_documentos.get("source_platform_status") or {}
    reader = resumo_documentos.get("architecture_reader") or {}
    filled, missing = _campos_documentais(resumo_documentos)
    official_documents = (
        list(reader.get("official_source_audit") or [])
        if isinstance(reader, dict)
        else []
    )
    if not official_documents:
        for item in manifest.get("items") or []:
            if not (
                item.get("accepted_for_reader")
                or item.get("accepted_for_metadata")
            ):
                continue
            official_documents.append(
                {
                    "filename": item.get("filename"),
                    "source_type": item.get("source_type"),
                    "source_role": item.get("source_role"),
                    "origin": item.get("origin"),
                    "path": item.get("path"),
                    "sha256": item.get("sha256"),
                    "read_status": item.get("read_status"),
                    "last_collected_at": item.get("collected_at"),
                    "accepted_for_reader": item.get("accepted_for_reader"),
                    "accepted_for_metadata": item.get("accepted_for_metadata"),
                }
            )
    return {
        "document_quality": _document_quality_from_resumo(resumo_documentos),
        "official_documents_found": official_documents,
        "platform": platform.get("platform"),
        "platform_url": platform.get("platform_url"),
        "platform_status": platform.get("status"),
        "requires_login": platform.get("requires_login"),
        "used_playwright": platform.get("used_playwright"),
        "last_collection_at": (
            reader.get("announcement_metadata", {}).get("collected_at")
            if isinstance(reader, dict)
            else None
        ),
        "fields_filled": filled,
        "fields_missing": missing,
        "warnings": list(resumo_documentos.get("avisos") or [])
        + list(platform.get("warnings") or []),
    }


def _texto_factual_concurso(concurso: dict, avisos: list[str]) -> str:
    campos = {
        "Titulo": concurso.get("titulo"),
        "Entidade": concurso.get("entidade"),
        "Link BASE": concurso.get("link"),
        "Link pecas": concurso.get("link_pecas"),
        "Tipo procedimento": concurso.get("tipo_procedimento"),
        "Preco base": concurso.get("preco_base"),
        "Data limite": concurso.get("data_limite"),
        "Avisos": "; ".join(avisos),
    }
    return "\n".join(f"{key}: {_texto_limpo(value)}" for key, value in campos.items() if _texto_limpo(value))


def _base_announcement_metadata(concurso: dict) -> dict:
    base_id = _id_base(concurso.get("link")) or _texto_limpo(
        concurso.get("id_portal_base")
    )
    source_url = (
        concurso.get("link")
        or (
            f"https://www.base.gov.pt/Base4/pt/detalhe/?type=anuncios&id={base_id}"
            if base_id
            else ""
        )
    )
    return {
        "source_role": "official_announcement",
        "source_type": "official_announcement",
        "source_name": f"Anuncio BASE {base_id}" if base_id else "Anuncio BASE",
        "source_url": source_url,
        "id_portal_base": base_id,
        "titulo": _texto_limpo(concurso.get("titulo")),
        "entidade": _texto_limpo(concurso.get("entidade")),
        "tipo_procedimento": _texto_limpo(concurso.get("tipo_procedimento")),
        "cpv": _texto_limpo(concurso.get("cpv") or concurso.get("cpvs")),
        "preco_base": _texto_limpo(concurso.get("preco_base")),
        "data_publicacao": _texto_limpo(concurso.get("data")),
        "prazo_propostas": _texto_limpo(
            concurso.get("data_entrega_propostas") or concurso.get("data_limite")
        ),
        "link_plataforma": _texto_limpo(concurso.get("link_pecas")),
        "link_anuncio_dr": _texto_limpo(concurso.get("link_anuncio_dr")),
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "collection_method": "database_snapshot_from_base_collector",
        "documentary_limits": [
            "O anuncio BASE confirma metadados do procedimento.",
            "O anuncio BASE nao substitui Programa do Procedimento, Caderno de Encargos, Programa Preliminar ou anexos tecnicos.",
        ],
    }



def _valor_confirmado(
    item: object,
) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("confirmed") is False:
        return False
    evidence = item.get("evidence")
    if isinstance(evidence, dict):
        status = _sem_acentos(
            _texto_limpo(
                evidence.get("status")
            )
        ).casefold()
        if status in {
            "por validar",
            "nao identificado",
            "incerto",
        }:
            return False
    return True


def _data_encontrada(
    valor: object,
) -> tuple[str, str] | None:
    texto = _texto_limpo(valor)
    if not texto:
        return None

    meses = {
        "janeiro": 1,
        "fevereiro": 2,
        "marco": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }

    texto_normalizado = _sem_acentos(
        texto
    ).casefold()

    textual = re.search(
        (
            r"\b(\d{1,2})(?:\.?\s*[ºo])?\s+de\s+"
            r"(janeiro|fevereiro|marco|abril|maio|junho|julho|"
            r"agosto|setembro|outubro|novembro|dezembro)\s+de\s+"
            r"(\d{4})"
            r"(?:.*?\b(?:as|pelas|ate as|até às)\s+"
            r"(\d{1,2})[:h.](\d{2}))?"
        ),
        texto_normalizado,
    )
    if textual:
        dia, mes_nome, ano, hora, minuto = textual.groups()
        try:
            parsed = datetime(
                int(ano),
                meses[mes_nome],
                int(dia),
                int(hora or 0),
                int(minuto or 0),
            )
        except (KeyError, ValueError):
            parsed = None
        if parsed is not None:
            publicacao = parsed.strftime("%d/%m/%Y")
            entrega = parsed.strftime("%d-%m-%Y")
            if hora and minuto:
                entrega += parsed.strftime(" %H:%M")
            return publicacao, entrega

    padroes = (
        (
            r"\b(\d{4})[./-](\d{2})[./-](\d{2})(?:[T\s]+(\d{2})[:h.](\d{2}))?",
            "ymd",
        ),
        (
            r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?:\s+(\d{1,2})[:h.](\d{2}))?",
            "dmy",
        ),
    )
    for padrao, ordem in padroes:
        match = re.search(
            padrao,
            texto,
        )
        if not match:
            continue

        if ordem == "ymd":
            ano, mes, dia, hora, minuto = (
                match.group(1),
                match.group(2),
                match.group(3),
                match.group(4),
                match.group(5),
            )
        else:
            dia, mes, ano, hora, minuto = (
                match.group(1),
                match.group(2),
                match.group(3),
                match.group(4),
                match.group(5),
            )

        try:
            parsed = datetime(
                int(ano),
                int(mes),
                int(dia),
                int(hora or 0),
                int(minuto or 0),
            )
        except ValueError:
            continue

        publicacao = parsed.strftime(
            "%d/%m/%Y"
        )
        entrega = parsed.strftime(
            "%d-%m-%Y"
        )
        if hora and minuto:
            entrega += parsed.strftime(
                " %H:%M"
            )
        return publicacao, entrega

    return None

def _texto_util_extraido(
    valor: object,
) -> str:
    texto = _texto_limpo(valor)
    normalizado = _sem_acentos(
        texto
    ).casefold()
    if not texto:
        return ""
    if any(
        marcador in normalizado
        for marcador in (
            "nao identificado",
            "por confirmar",
            "por validar",
            "sem data",
            "desconhecido",
        )
    ):
        return ""
    return texto


def _campos_concurso_extraidos(
    concurso: dict,
    ficha: dict,
) -> dict[str, str | None]:
    insights = (
        ficha.get("document_insights")
        if isinstance(
            ficha.get("document_insights"),
            dict,
        )
        else {}
    )
    timeline = (
        insights.get("timeline")
        if isinstance(
            insights.get("timeline"),
            list,
        )
        else []
    )

    data_publicacao = ""
    data_entrega = ""

    for item in timeline:
        if (
            not isinstance(item, dict)
            or not _valor_confirmado(item)
        ):
            continue

        tipo = _sem_acentos(
            _texto_limpo(
                item.get("type")
                or item.get("tipo")
            )
        ).casefold()
        value = (
            item.get("date")
            or item.get("value")
            or item.get("data")
        )
        parsed = _data_encontrada(
            value
        )
        if not parsed:
            continue

        publicacao, entrega = parsed
        if (
            not data_publicacao
            and "public" in tipo
        ):
            data_publicacao = publicacao

        if (
            not data_entrega
            and any(
                marker in tipo
                for marker in (
                    "entrega",
                    "proposta",
                    "submiss",
                    "candidatura",
                    "rececao",
                )
            )
        ):
            data_entrega = entrega

    procedure_summary = (
        insights.get("procedure_summary")
        if isinstance(
            insights.get("procedure_summary"),
            dict,
        )
        else {}
    )
    if not data_entrega:
        deadline = procedure_summary.get(
            "submission_deadline"
        )
        if isinstance(deadline, dict):
            parsed = _data_encontrada(
                deadline.get("value")
            )
            if parsed and _valor_confirmado(
                {
                    "evidence": deadline,
                }
            ):
                data_entrega = parsed[1]

    extraction = (
        ficha.get("design_competition_extraction")
        if isinstance(
            ficha.get("design_competition_extraction"),
            dict,
        )
        else {}
    )
    extraction_facts = (
        extraction.get("facts")
        if isinstance(
            extraction.get("facts"),
            dict,
        )
        else {}
    )

    def fact_value(key: str) -> object:
        item = extraction_facts.get(key)
        if isinstance(item, dict):
            return item.get("value")
        return item

    if not data_publicacao:
        for candidate in (
            fact_value("publication_date"),
            fact_value("announcement_publication_date"),
            fact_value("procedure_publication_date"),
        ):
            parsed = _data_encontrada(candidate)
            if parsed:
                data_publicacao = parsed[0]
                break

    if not data_entrega:
        for candidate in (
            fact_value("submission_deadline"),
            fact_value("proposal_deadline"),
            fact_value("application_deadline"),
        ):
            parsed = _data_encontrada(candidate)
            if parsed:
                data_entrega = parsed[1]
                break

    identificacao = (
        ficha.get("identificacao")
        if isinstance(
            ficha.get("identificacao"),
            dict,
        )
        else {}
    )
    if not data_publicacao:
        for candidate in (
            identificacao.get("data_publicacao"),
            identificacao.get("data"),
            ficha.get("data_publicacao"),
        ):
            parsed = _data_encontrada(candidate)
            if parsed:
                data_publicacao = parsed[0]
                break

    if not data_entrega:
        for candidate in (
            identificacao.get("data_entrega_propostas"),
            identificacao.get("prazo_entrega"),
            ficha.get("data_entrega_propostas"),
        ):
            parsed = _data_encontrada(candidate)
            if parsed:
                data_entrega = parsed[1]
                break

    tipo_procedimento = _texto_util_extraido(
        identificacao.get(
            "tipo_procedimento"
        )
    )

    economia = (
        ficha.get("economia")
        if isinstance(
            ficha.get("economia"),
            dict,
        )
        else {}
    )
    base_price_entry = procedure_summary.get(
        "base_price"
    )
    base_price_value = (
        base_price_entry.get("value")
        if isinstance(
            base_price_entry,
            dict,
        )
        else ""
    )
    preco_base = _texto_util_extraido(
        economia.get("valor_procedimento")
        or base_price_value
    )

    criterios = (
        ficha.get("criterios")
        if isinstance(
            ficha.get("criterios"),
            dict,
        )
        else {}
    )
    criterio_tipo = _texto_util_extraido(
        criterios.get(
            "criterio_adjudicacao"
        )
    )
    criterio_resumo = _texto_util_extraido(
        criterios.get("resumo")
    )
    criterio_detalhe = _texto_util_extraido(
        criterios.get("detalhe")
    )

    percentagens = (
        criterios.get("percentagens")
        if isinstance(
            criterios.get("percentagens"),
            list,
        )
        else []
    )
    if not criterio_tipo and percentagens:
        fatores = []
        for item in percentagens:
            if not isinstance(item, dict):
                continue
            fator = _texto_util_extraido(
                item.get("criterio")
            )
            if fator and fator not in fatores:
                fatores.append(fator)
        if fatores:
            criterio_tipo = " + ".join(
                fatores[:4]
            )

    entregaveis_value = ficha.get(
        "entregaveis"
    )
    if isinstance(entregaveis_value, dict):
        principais = entregaveis_value.get(
            "principais"
        )
        if isinstance(principais, list):
            entregaveis = json.dumps(
                principais,
                ensure_ascii=False,
            )
        else:
            entregaveis = _texto_util_extraido(
                principais
            )
    elif isinstance(entregaveis_value, list):
        entregaveis = json.dumps(
            entregaveis_value,
            ensure_ascii=False,
        )
    else:
        entregaveis = _texto_util_extraido(
            entregaveis_value
        )

    current_type = _sem_acentos(
        _texto_limpo(
            concurso.get(
                "tipo_procedimento"
            )
        )
    ).casefold()
    generic_types = {
        "",
        "concurso publico",
        "procedimento de contratacao publica",
        "concurso de arquitetura",
    }

    return {
        "data": (
            data_publicacao
            if not _texto_limpo(
                concurso.get("data")
            )
            else None
        ),
        "data_entrega_propostas": (
            data_entrega
            if not _texto_limpo(
                concurso.get(
                    "data_entrega_propostas"
                )
            )
            else None
        ),
        "preco_base": (
            preco_base
            if not _texto_limpo(
                concurso.get("preco_base")
            )
            else None
        ),
        "tipo_procedimento": (
            tipo_procedimento
            if (
                tipo_procedimento
                and current_type
                in generic_types
            )
            else None
        ),
        "criterio_tipo": (
            criterio_tipo
            if (
                criterio_tipo
                and (
                    not _texto_limpo(concurso.get("criterio_tipo"))
                    or (
                        "%" in criterio_resumo
                        and "%" not in _texto_limpo(
                            concurso.get("criterio_resumo")
                        )
                    )
                )
            )
            else None
        ),
        "criterio_resumo": (
            criterio_resumo
            if (
                criterio_resumo
                and (
                    not _texto_limpo(concurso.get("criterio_resumo"))
                    or (
                        "%" in criterio_resumo
                        and "%" not in _texto_limpo(
                            concurso.get("criterio_resumo")
                        )
                    )
                )
            )
            else None
        ),
        "criterio_detalhe": (
            criterio_detalhe
            if (
                criterio_detalhe
                and (
                    not _texto_limpo(concurso.get("criterio_detalhe"))
                    or "%" in criterio_resumo
                )
            )
            else None
        ),
        "entregaveis": (
            entregaveis
            if (
                entregaveis
                and (
                    not _texto_limpo(concurso.get("entregaveis"))
                    or _texto_limpo(concurso.get("entregaveis")) in {"[]", "{}"}
                    or _texto_limpo(concurso.get("entregaveis")).startswith("{")
                )
            )
            else None
        ),
    }


def _atualizar_concurso_com_ficha(
    concurso: dict,
    ficha: dict,
) -> None:
    campos = _campos_concurso_extraidos(
        concurso,
        ficha,
    )
    if not any(
        value
        for value in campos.values()
    ):
        return

    atualizar_dados_concurso(
        link=concurso.get("link"),
        **campos,
    )


def _criar_base_announcement(destino: Path, concurso: dict) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "base_announcement.json").write_text(
        json.dumps(
            _base_announcement_metadata(concurso),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _criar_fallback_concurso(destino: Path, concurso: dict, avisos: list[str]) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "dados_concurso.txt").write_text(
        _texto_factual_concurso(concurso, avisos),
        encoding="utf-8",
    )


def _tentar_recolha_plataforma_publica(
    job: dict,
    concurso: dict,
    destino: Path,
    orcamento: dict[str, int],
) -> list[str]:
    avisos: list[str] = []
    plataforma, _ = detect_platform(concurso)
    if plataforma == "unknown":
        return avisos

    cache_dir = _cache_plataforma_dir(concurso)
    if _copiar_cache_plataforma(cache_dir, destino, orcamento):
        return avisos
    metadata_existente = _metadata_plataforma_publica(concurso)
    if metadata_existente.get("status") in {
        "no_documents",
        "login_required",
        "unsupported",
    }:
        avisos.extend(metadata_existente.get("warnings") or [])
        return avisos

    try:
        atualizar_analise_job(
            job["id"],
            "extracao",
            15,
            stage="locating_documents",
        )
        resultado = discover_public_documents(concurso)
        if not resultado.public_documents:
            avisos.extend(resultado.warnings or [])
            save_platform_metadata(cache_dir, resultado, [])
            return avisos

        atualizar_analise_job(
            job["id"],
            "extracao",
            25,
            stage="downloading_documents",
        )
        documentos = download_public_documents(
            resultado.public_documents or [],
            cache_dir,
        )
        if not documentos:
            resultado.status = resultado.status if resultado.status != "success" else "error"
            resultado.warnings = list(resultado.warnings or [])
            resultado.warnings.append(
                "Nao foi possivel descarregar documentos publicos da plataforma."
            )
            avisos.extend(resultado.warnings)
            save_platform_metadata(cache_dir, resultado, [])
            return avisos
        save_platform_metadata(cache_dir, resultado, documentos)
        _copiar_cache_plataforma(cache_dir, destino, orcamento)
    except Exception as erro:
        logger.warning(
            "Nao foi possivel recolher documentos publicos para concurso %s: %s",
            concurso.get("id"),
            erro,
        )
        avisos.append("Erro da plataforma ao descarregar documentos publicos.")
    return avisos


def _fase_extracao(job: dict, concurso: dict, pasta_job: Path) -> tuple[Path, list[str]]:
    job_id = job["id"]
    _verificar_cancelamento(job_id)
    avisos: list[str] = []

    pasta_download = pasta_job / "download"
    pasta_extraida = pasta_job / "extraido"
    pasta_download.mkdir(parents=True, exist_ok=True)

    orcamento = _novo_orcamento_extracao()

    _criar_base_announcement(pasta_extraida, concurso)

    if _copiar_cache_plataforma(
        _cache_plataforma_dir(concurso),
        pasta_extraida,
        orcamento,
    ):
        return pasta_extraida, avisos

    if _copiar_documentos_existentes(
        concurso,
        pasta_extraida,
        orcamento,
    ):
        return pasta_extraida, avisos

    avisos.extend(
        _tentar_recolha_plataforma_publica(
            job,
            concurso,
            pasta_extraida,
            orcamento,
        )
    )
    if _tem_documentos_ou_fallback(pasta_extraida):
        return pasta_extraida, avisos

    link_pecas = _texto_limpo(concurso.get("link_pecas"))
    if not link_pecas:
        avisos.append("Nao foi possivel obter automaticamente as pecas do procedimento.")
        _criar_fallback_concurso(pasta_extraida, concurso, avisos)
        return pasta_extraida, avisos

    try:
        ficheiro = _descarregar(link_pecas, pasta_download)
        _verificar_cancelamento(job_id)
        _extrair_archivos_recursivo(
            ficheiro,
            pasta_extraida,
            orcamento,
        )
    except Exception as erro:
        logger.warning(
            "Nao foi possivel descarregar link_pecas do concurso %s: %s",
            concurso.get("id"),
            erro,
        )
        avisos.append("Nao foi possivel obter automaticamente as pecas do procedimento.")
        _criar_fallback_concurso(pasta_extraida, concurso, avisos)
    return pasta_extraida, avisos


def _fase_processamento(
    job: dict,
    pasta_extraida: Path,
    avisos: list[str] | None = None,
    concurso: dict | None = None,
) -> tuple[dict, list, dict]:
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
        for txt in pasta_extraida.rglob("*.txt"):
            try:
                textos[txt.name] = txt.read_text(encoding="utf-8")
            except OSError:
                continue

    documentos, resumo_documentos = _classificar_documentos(pasta_extraida)
    manifest = create_source_manifest(
        pasta_extraida,
        job_id=job_id,
        output_path=pasta_extraida / "source_manifest.json",
    )
    resumo_documentos["source_manifest"] = manifest.to_dict()
    if concurso is not None:
        resumo_documentos["architecture_reader"] = read_architecture_documents(
            concurso=concurso,
            manifest=manifest,
            root=pasta_extraida,
            extracted_texts=textos,
        )
    resumo_documentos["avisos"] = list(avisos or [])
    concurso = concurso_por_id(job["concurso_id"]) or {}
    resumo_documentos["source_platform_status"] = (
        _source_platform_status_para_textos(
            concurso,
            textos,
            _metadata_plataforma_publica(concurso),
        )
    )
    source_status = resumo_documentos["source_platform_status"].get("status")
    if source_status in {"no_documents", "login_required", "unsupported", "error"}:
        if source_status not in resumo_documentos["avisos"]:
            resumo_documentos["avisos"].append(source_status)

    if not textos:
        resumo_documentos["avisos"].append(
            "Nao foi possivel extrair texto pesquisavel dos documentos."
        )
        textos = {"dados_concurso.txt": "Dados factuais do concurso insuficientes."}

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

        atualizar_analise_job(
            job_id,
            "extracao",
            10,
            stage="locating_documents",
        )
        pasta_extraida, avisos_documentos = _fase_extracao(
            job,
            concurso,
            pasta_job,
        )

        atualizar_analise_job(
            job_id,
            "processamento",
            35,
            stage="extracting_documents",
        )
        textos, documentos, resumo_documentos = _fase_processamento(
            job,
            pasta_extraida,
            avisos_documentos,
            concurso,
        )
        _verificar_cancelamento(job_id)
        atualizar_analise_job(
            job_id,
            "geracao",
            60,
            stage="generating_competition_analysis",
        )
        analise_documental = analisar_documentos_ai(
            textos=textos,
            documentos=documentos,
            titulo=_texto_limpo(concurso.get("titulo"))
            or "Concurso sem titulo",
        )

        atualizar_analise_job(
            job_id,
            "geracao",
            75,
            stage="generating_competition_analysis",
        )
        _verificar_cancelamento(job_id)
        ficha, score = _gerar_ficha(
            concurso=concurso,
            job=job,
            textos=textos,
            documentos=documentos,
            resumo_documentos=resumo_documentos,
            analise_documental=analise_documental,
        )
        ficha["source_platform_status"] = resumo_documentos.get(
            "source_platform_status",
            {},
        )

        try:
            from .common_project_extractor import (
                apply_common_project_extraction,
            )

            common_project = apply_common_project_extraction(
                ficha=ficha,
                textos=textos,
                concurso=concurso,
            )
        except Exception as erro:
            common_project = {
                "active": False,
                "version": "common-project-extractor-v1",
                "warnings": [f"{type(erro).__name__}: {erro}"],
            }

        resumo_documentos["common_project_extraction"] = (
            common_project
        )

        try:
            from .intervention_program import (
                apply_intervention_program,
            )

            early_intervention = apply_intervention_program(
                ficha=ficha,
                textos=textos,
            )
            if early_intervention.get("active"):
                resumo_documentos["intervention_program"] = (
                    early_intervention
                )
        except Exception:
            early_intervention = {"active": False}

        try:
            from .procedure_analysis import (
                apply_procedure_analysis,
            )

            procedure_analysis = apply_procedure_analysis(
                ficha=ficha,
                textos=textos,
                concurso=concurso,
            )
        except Exception as erro:
            procedure_analysis = {
                "family": "project_services",
                "active": False,
                "version": "procedure-analysis-v15.4",
                "warnings": [f"{type(erro).__name__}: {erro}"],
            }

        resumo_documentos["procedure_analysis"] = (
            procedure_analysis
        )

        ficha = _enriquecer_ficha_com_empresa(
            ficha,
            job.get("company_id"),
        )
        _atualizar_concurso_com_ficha(
            concurso,
            ficha,
        )
        atualizar_analise_job(
            job_id,
            "geracao",
            88,
            stage="matching_company_profile",
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
            company_id=job.get("company_id"),
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
        atualizar_analise_job(
            job_id,
            "erro",
            0,
            str(erro)[:1000],
            stage="failed",
        )
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


def _extrair_valor_documentos(documentos):
    for documento in documentos:
        valor = _extrair_valor(str(documento or ""))
        if valor:
            return valor
    return None


def _extrair_areas_documentos(documentos):
    areas = {}
    indice = 1
    for documento in documentos:
        for area in re.finditer(r"(\d[\d\s.,]{1,})\s*m[²2]", str(documento or ""), re.IGNORECASE):
            areas[f"area_{indice}"] = f"{_texto_limpo(area.group(1))} m²"
            indice += 1
            if indice > 8:
                return areas
    return areas


def _agregar_listas_documentos(documentos, extrator, titulo):
    resultado = []
    for documento in documentos:
        resultado = _juntar_listas(resultado, extrator(str(documento or ""), titulo), limite=18)
    return resultado


def _extrair_tipo_intervencao_documentos(documentos, titulo):
    resultado = []
    for documento in documentos:
        tipos = _extrair_tipo_intervencao(str(documento or ""), titulo)
        resultado = _juntar_listas(
            resultado,
            [tipo for tipo in tipos if tipo != "Intervencao geral"],
            limite=18,
        )
    return resultado or ["Intervencao geral"]


def _extrair_funcoes_documentos(documentos, titulo):
    return _agregar_listas_documentos(documentos, _extrair_funcoes, titulo)


def _extrair_especialidades_documentos(documentos):
    resultado = []
    for documento in documentos:
        resultado = _juntar_listas(resultado, _extrair_especialidades(str(documento or "")), limite=18)
    return resultado


def _criterios_do_concurso_documentos(concurso, documentos):
    resumo = _texto_limpo(concurso.get("criterio_resumo"))
    detalhe = _texto_limpo(concurso.get("criterio_detalhe"))
    if resumo or detalhe:
        return _criterios_do_concurso(concurso, f"{resumo} {detalhe}".strip())
    analisado = analisar_criterios_documentos(documentos)
    partes = []
    if analisado.get("qualidade_percentagem"):
        partes.append(f"Qualidade {analisado['qualidade_percentagem']}%")
    if analisado.get("preco_percentagem"):
        partes.append(f"Preco {analisado['preco_percentagem']}%")
    analisado["resumo"] = " • ".join(partes)
    analisado["detalhe"] = analisado["resumo"]
    return analisado


def _extrair_entregaveis_textos(documentos, concurso):
    entregaveis_db = _texto_limpo(concurso.get("entregaveis"))
    if entregaveis_db:
        return _extrair_entregaveis("", concurso)
    termos = (
        "projeto de arquitetura", "projeto do espaço exterior", "estudo prévio",
        "projeto de execução", "memória descritiva", "mapa de quantidades",
        "estimativa orçamental", "peças desenhadas", "plano de acessibilidades",
        "plano de segurança", "telas finais",
    )
    return _frases_com_termos(documentos, termos, limite=12)


def _extrair_requisitos_textos(documentos):
    return {
        "obrigatorios": _frases_com_termos(documentos, ("obrigatório", "obrigatoria", "habilitação", "habilitacao", "termo de responsabilidade", "inscrição válida", "inscricao valida", "certificação", "certificacao", "experiência comprovada", "experiencia comprovada"), limite=10),
        "riscos_participacao": _frases_com_termos(documentos, ("exclusão", "exclusao", "caducidade", "não apresentação", "nao apresentacao", "falta", "insuficiência", "insuficiencia"), limite=8),
    }


def _sintese_programa_textos(documentos, titulo, funcoes):
    frases = _frases_com_termos(documentos, ("objeto", "âmbito", "ambito", "elaboração do projeto", "elaboracao do projeto", "intervenção", "intervencao", "reabilitação", "reabilitacao", "execução de arquitetura", "execucao de arquitetura"), limite=2)
    if frases:
        return " ".join(frases)
    return _sintese_programa("", titulo, funcoes)
