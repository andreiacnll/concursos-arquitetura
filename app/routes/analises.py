from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from ..auth import UtilizadorAutenticado, obter_utilizador_atual
from ..database import (
    analise_concluida_por_concurso,
    concurso_por_id,
    criar_ou_obter_analise_job,
    listar_analises_utilizador,
)


router = APIRouter(prefix="/analises", tags=["Análises"])


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
        pedido.concurso_id
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
