import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from ..auth import UtilizadorAutenticado, obter_utilizador_atual
from ..database import (
    analise_concluida_por_concurso,
    cancelar_analise_job,
    concurso_por_id,
    criar_ou_obter_analise_job,
    listar_analises_utilizador,
    obter_analise_job_utilizador,
    remover_analise_utilizador,
)


router = APIRouter(prefix="/analises", tags=["Análises"])
BASE_DIR = Path(__file__).resolve().parents[2]
ANALISES_DIR = (BASE_DIR / "analise_documentos").resolve()
JOBS_TEMP_DIR = (ANALISES_DIR / ".jobs").resolve()


class CriarAnalisePedido(BaseModel):
    concurso_id: int = Field(gt=0)


@router.get("")
def listar_analises(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    return {
        "analises": listar_analises_utilizador(
            utilizador.id
        )
    }


@router.post("/criar")
def criar_analise(
    pedido: CriarAnalisePedido,
    response: Response,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    if concurso_por_id(pedido.concurso_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concurso não encontrado.",
        )

    analise_existente = analise_concluida_por_concurso(
        pedido.concurso_id,
        utilizador.id,
    )
    if analise_existente is not None:
        response.status_code = status.HTTP_200_OK
        return analise_existente

    job, criado = criar_ou_obter_analise_job(
        utilizador.id,
        pedido.concurso_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED
        if criado
        else status.HTTP_200_OK
    )
    return job


def _remover_temporarios_job(job_id: int) -> bool:
    pasta = (JOBS_TEMP_DIR / str(job_id)).resolve()
    if JOBS_TEMP_DIR not in pasta.parents or not pasta.exists():
        return False
    shutil.rmtree(pasta)
    return True


def _remover_ficha_especifica(caminho_relativo: str | None) -> bool:
    if not caminho_relativo:
        return False

    ficheiro = (BASE_DIR / caminho_relativo).resolve()
    if (
        ANALISES_DIR not in ficheiro.parents
        or ficheiro.name != "ficha.json"
        or not ficheiro.is_file()
    ):
        return False

    ficheiro.unlink()
    return True


@router.post("/{job_id}/cancelar")
def cancelar_analise(
    job_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    job = obter_analise_job_utilizador(utilizador.id, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análise não encontrada.",
        )
    if job["estado"] not in {
        "aguarda", "extracao", "processamento", "geracao"
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta análise já não pode ser cancelada.",
        )

    cancelado = cancelar_analise_job(utilizador.id, job_id)
    if cancelado is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O estado da análise foi alterado. Atualiza a página.",
        )

    temporarios_removidos = _remover_temporarios_job(job_id)
    return {
        **cancelado,
        "temporarios_removidos": temporarios_removidos,
    }


@router.delete("/{analise_id}")
def apagar_analise(
    analise_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    removida = remover_analise_utilizador(
        utilizador.id,
        analise_id,
    )
    if removida is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Análise não encontrada ou não pertence "
                "ao utilizador atual."
            ),
        )

    ficha_removida = False
    if removida["ficheiro_exclusivo"]:
        ficha_removida = _remover_ficha_especifica(
            removida.get("ficheiro_ficha")
        )

    return {
        "apagada": True,
        "analise_id": analise_id,
        "concurso_id": removida["concurso_id"],
        "ficha_removida": ficha_removida,
    }
