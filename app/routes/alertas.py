from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..auth import UtilizadorAutenticado, obter_utilizador_atual
from ..database import (
    arquivar_alerta_utilizador,
    ativar_alertas_concurso,
    concurso_por_id,
    desativar_alertas_concurso,
    listar_alerta_subscricoes_utilizador,
    listar_alertas_utilizador,
    obter_alertas_concurso_utilizador,
)


router = APIRouter(prefix="/alertas", tags=["Alertas"])


@router.get("")
def listar_alertas(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    return {
        "alertas": listar_alertas_utilizador(
            utilizador.id
        ),
        "subscricoes": listar_alerta_subscricoes_utilizador(
            utilizador.id
        ),
    }


@router.get("/subscricoes")
def listar_subscricoes(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    return {
        "subscricoes": listar_alerta_subscricoes_utilizador(
            utilizador.id
        )
    }


@router.get("/{concurso_id}/subscricao")
def obter_subscricao(
    concurso_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    if concurso_por_id(concurso_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concurso nao encontrado.",
        )

    return obter_alertas_concurso_utilizador(
        utilizador.id,
        concurso_id,
    )


@router.post("/{concurso_id}/ativar")
def ativar_subscricao(
    concurso_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    if concurso_por_id(concurso_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concurso nao encontrado.",
        )

    subscricao = ativar_alertas_concurso(
        utilizador.id,
        concurso_id,
    )
    return subscricao


@router.delete(
    "/{concurso_id}/desativar",
    status_code=status.HTTP_204_NO_CONTENT,
)
def desativar_subscricao(
    concurso_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> Response:
    if concurso_por_id(concurso_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concurso nao encontrado.",
        )

    desativar_alertas_concurso(
        utilizador.id,
        concurso_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/item/{alerta_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def arquivar_alerta(
    alerta_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> Response:
    arquivar_alerta_utilizador(
        utilizador.id,
        alerta_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
