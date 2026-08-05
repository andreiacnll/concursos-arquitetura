from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..auth import UtilizadorAutenticado, obter_utilizador_atual
from ..database import (
    concurso_por_id,
    criar_ou_obter_favorito,
    listar_favoritos_utilizador,
    remover_favorito,
)


router = APIRouter(prefix="/favoritos", tags=["Favoritos"])


@router.get("")
def listar_favoritos(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    return {
        "favoritos": listar_favoritos_utilizador(
            utilizador.id
        )
    }


@router.post("/{concurso_id}")
def criar_favorito(
    concurso_id: int,
    response: Response,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    if concurso_por_id(concurso_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concurso não encontrado.",
        )

    favorito, criado = criar_ou_obter_favorito(
        utilizador.id,
        concurso_id,
    )
    response.status_code = (
        status.HTTP_201_CREATED
        if criado
        else status.HTTP_200_OK
    )
    return favorito


@router.delete(
    "/{concurso_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def apagar_favorito(
    concurso_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> Response:
    remover_favorito(utilizador.id, concurso_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
