from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from ..auth import UtilizadorAutenticado, obter_utilizador_atual
from .company_storage import (
    adicionar_membro,
    criar_empresa,
    listar_membros,
    obter_empresa_utilizador,
)
from .intelligence_builder import build_company_intelligence
from .member_storage import (
    criar_member_profile,
    guardar_member_profile,
    obter_member_profile,
)
from .profile_storage import (
    guardar_company_profile as guardar_company_profile_storage,
    obter_company_profile as obter_company_profile_storage,
)
from .models import CompanyMember, CompanyProfile, MemberProfile


router = APIRouter(prefix="/company", tags=["Company Intelligence"])


class CompanyCreatePedido(BaseModel):
    name: str = Field(min_length=1)
    website: str | None = None


class CompanyMemberCreatePedido(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = "member"


def _membro_pertence_empresa(
    company_id: int,
    member_id: int,
) -> bool:
    return any(
        membro["id"] == member_id
        for membro in listar_membros(company_id)
    )


@router.get("/profile")
def obter_company_profile(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> CompanyProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    # Futuro: member_profiles, interviewer, extractor e matching vão
    # alimentar este profile persistido por company_id.
    return obter_company_profile_storage(empresa["id"])


@router.post("/profile", status_code=status.HTTP_201_CREATED)
def criar_company_profile(
    perfil: CompanyProfile,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> CompanyProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    return guardar_company_profile_storage(empresa["id"], perfil)


@router.put("/profile")
def atualizar_company_profile(
    perfil: CompanyProfile,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> CompanyProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    return guardar_company_profile_storage(empresa["id"], perfil)


@router.get("/intelligence")
def obter_company_intelligence(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    # Futuro: esta visão agregada será consumida por interviewer,
    # matching engine, response generator e knowledge base.
    return build_company_intelligence(empresa["id"])


@router.get(
    "/members/{member_id}/profile"
)
def obter_member_profile_endpoint(
    member_id: int,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> MemberProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    if not _membro_pertence_empresa(empresa["id"], member_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membro não encontrado na empresa atual.",
        )

    # Futuro: owner/admin, visibilidade e permissões individuais vão
    # controlar o acesso a este perfil.
    return obter_member_profile(member_id)


@router.post(
    "/members/{member_id}/profile",
    status_code=status.HTTP_201_CREATED,
)
def criar_member_profile_endpoint(
    member_id: int,
    perfil: MemberProfile,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> MemberProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    if not _membro_pertence_empresa(empresa["id"], member_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membro não encontrado na empresa atual.",
        )

    # Futuro: o member profile será usado por interviewer individual,
    # matching de concursos, resposta AI e agregação Company Intelligence.
    criar_member_profile(member_id)
    return guardar_member_profile(member_id, perfil)


@router.put("/members/{member_id}/profile")
def atualizar_member_profile_endpoint(
    member_id: int,
    perfil: MemberProfile,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> MemberProfile:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    if not _membro_pertence_empresa(empresa["id"], member_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membro não encontrado na empresa atual.",
        )

    return guardar_member_profile(member_id, perfil)


@router.get("")
def obter_company(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )
    return empresa


@router.post("")
def criar_company(
    pedido: CompanyCreatePedido,
    response: Response,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa_existente = obter_empresa_utilizador(utilizador.id)
    if empresa_existente is not None:
        response.status_code = status.HTTP_200_OK
        return empresa_existente

    empresa = criar_empresa(
        utilizador.id,
        pedido.name,
        pedido.website,
    )

    response.status_code = status.HTTP_201_CREATED
    return empresa


@router.get("/members")
def listar_company_members(
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
):
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    return {
        "company_id": empresa["id"],
        "members": listar_membros(empresa["id"]),
    }


@router.post("/members", status_code=status.HTTP_201_CREATED)
def adicionar_company_member(
    pedido: CompanyMemberCreatePedido,
    utilizador: UtilizadorAutenticado = Depends(
        obter_utilizador_atual
    ),
) -> CompanyMember:
    empresa = obter_empresa_utilizador(utilizador.id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa não encontrada para o utilizador atual.",
        )

    # Futuro: regras de permissões, convites por email e papéis mais
    # granulares serão tratadas na camada de equipa/empresa.
    membro = adicionar_membro(
        empresa["id"],
        pedido.user_id,
        pedido.role,
    )
    return CompanyMember.model_validate(membro)
