from __future__ import annotations

import argparse
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .coletor import PortalBaseBrowser, normalizar_anuncio
from .database import atualizar_dados_concurso


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "concursos.db"


def extrair_id_portal(link: str) -> str:
    """
    Extrai o ID de um link como:
    https://www.base.gov.pt/Base4/pt/detalhe/?type=anuncios&id=451620
    """
    if not link:
        return ""

    parametros = parse_qs(urlparse(link).query)
    valores = parametros.get("id", [])

    if not valores:
        return ""

    return str(valores[0]).strip()


def obter_concursos_pendentes(limite: int | None) -> list[dict[str, str]]:
    """
    Seleciona concursos que ainda não têm preço base ou prazo.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    sql = """
        SELECT
            link,
            titulo,
            data_limite,
            preco_base
        FROM concursos
        WHERE
            TRIM(COALESCE(data_limite, '')) = ''
            OR TRIM(COALESCE(preco_base, '')) = ''
        ORDER BY id DESC
    """

    parametros: tuple[object, ...] = ()

    if limite is not None:
        sql += " LIMIT ?"
        parametros = (limite,)

    linhas = conn.execute(sql, parametros).fetchall()
    conn.close()

    return [dict(linha) for linha in linhas]


def criar_backup() -> Path:
    """
    Cria uma cópia da base antes de qualquer alteração.
    """
    momento = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = BASE_DIR / f"concursos-antes-migracao-{momento}.db"

    shutil.copy2(DB_PATH, destino)

    return destino


def desembrulhar_detalhe(resposta: object) -> dict:
    """
    Aceita diferentes formatos que o Portal BASE possa devolver.
    """
    if not isinstance(resposta, dict):
        return {}

    for chave in ("item", "data", "result", "resultado"):
        valor = resposta.get(chave)

        if isinstance(valor, dict):
            return valor

    itens = resposta.get("items")

    if isinstance(itens, list) and itens:
        primeiro = itens[0]

        if isinstance(primeiro, dict):
            return primeiro

    return resposta


def migrar(limite: int | None, pausa: float) -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Base de dados não encontrada: {DB_PATH}")

    concursos = obter_concursos_pendentes(limite)

    print("=" * 60)
    print(" Preenchimento de preço base e prazo")
    print("=" * 60)
    print(f"Base de dados: {DB_PATH}")
    print(f"Concursos a verificar: {len(concursos)}")

    if not concursos:
        print("Não existem concursos pendentes.")
        return

    backup = criar_backup()
    print(f"Backup criado: {backup.name}")

    atualizados = 0
    com_preco = 0
    com_prazo = 0
    sem_id = 0
    erros = 0

    with PortalBaseBrowser() as portal:
        portal.inicializar()

        for numero, concurso in enumerate(concursos, start=1):
            link = concurso.get("link", "")
            titulo = concurso.get("titulo", "")
            identificador = extrair_id_portal(link)

            nome_curto = titulo[:75]

            print(
                f"\n[{numero}/{len(concursos)}] "
                f"{identificador or 'sem ID'} — {nome_curto}"
            )

            if not identificador:
                print("  Ignorado: o link não contém um ID do Portal BASE.")
                sem_id += 1
                continue

            try:
                resposta = portal.obter_detalhe(identificador)
                detalhe = desembrulhar_detalhe(resposta)

                if not detalhe:
                    print("  Ignorado: detalhe vazio.")
                    erros += 1
                    continue

                normalizado = normalizar_anuncio(detalhe)

                preco_base = normalizado.get("preco_base")
                data_limite = normalizado.get("data_limite")
                cpvs = normalizado.get("cpvs")
                tipos = normalizado.get("tipos_contrato")

                if isinstance(cpvs, list):
                    cpv = "; ".join(
                        str(valor).strip()
                        for valor in cpvs
                        if str(valor).strip()
                    )
                else:
                    cpv = str(cpvs or "").strip()

                if isinstance(tipos, list):
                    tipo_procedimento = "; ".join(
                        str(valor).strip()
                        for valor in tipos
                        if str(valor).strip()
                    )
                else:
                    tipo_procedimento = str(tipos or "").strip()

                foi_atualizado = atualizar_dados_concurso(
                    link=link,
                    titulo=normalizado.get("titulo"),
                    entidade=normalizado.get("entidade"),
                    data=normalizado.get("data"),
                    data_limite=data_limite,
                    preco_base=preco_base,
                    cpv=cpv,
                    tipo_procedimento=tipo_procedimento,
                )

                if foi_atualizado:
                    atualizados += 1

                if preco_base:
                    com_preco += 1

                if data_limite:
                    com_prazo += 1

                print(
                    "  Resultado:"
                    f" preço={preco_base or 'não indicado'};"
                    f" prazo={data_limite or 'não indicado'}"
                )

            except KeyboardInterrupt:
                print("\nMigração interrompida pelo utilizador.")
                break

            except Exception as erro:
                erros += 1
                print(f"  ERRO: {erro}")

            if pausa > 0:
                time.sleep(pausa)

    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Registos processados: {len(concursos)}")
    print(f"Registos atualizados: {atualizados}")
    print(f"Detalhes com preço: {com_preco}")
    print(f"Detalhes com prazo: {com_prazo}")
    print(f"Links sem ID: {sem_id}")
    print(f"Erros: {erros}")
    print(f"Backup: {backup}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Preenche retroativamente preço base, prazo, "
            "CPV e procedimento dos concursos existentes."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Número máximo de concursos a processar.",
    )

    parser.add_argument(
        "--pausa",
        type=float,
        default=0.3,
        help="Pausa, em segundos, entre pedidos ao Portal BASE.",
    )

    argumentos = parser.parse_args()

    if argumentos.limit is not None and argumentos.limit < 1:
        parser.error("--limit deve ser igual ou superior a 1.")

    if argumentos.pausa < 0:
        parser.error("--pausa não pode ser negativa.")

    migrar(
        limite=argumentos.limit,
        pausa=argumentos.pausa,
    )


if __name__ == "__main__":
    main()
