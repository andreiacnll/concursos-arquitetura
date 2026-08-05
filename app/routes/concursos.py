from fastapi import APIRouter

router = APIRouter(
    prefix="/concursos",
    tags=["Concursos"],
)


@router.get("/")
def listar_concursos():
    return {
        "mensagem": "Endpoint dos concursos a funcionar!"
    }