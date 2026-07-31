from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, status

from .models import CompanyProfile


router = APIRouter(prefix="/company", tags=["Company Intelligence"])


_TEMPORARY_PROFILE = CompanyProfile()


def _ler_perfil_temporario() -> CompanyProfile:
    return deepcopy(_TEMPORARY_PROFILE)


def _guardar_perfil_temporario(perfil: CompanyProfile) -> CompanyProfile:
    global _TEMPORARY_PROFILE
    _TEMPORARY_PROFILE = deepcopy(perfil)
    return deepcopy(_TEMPORARY_PROFILE)


@router.get("/profile")
def obter_company_profile() -> CompanyProfile:
    return _ler_perfil_temporario()


@router.post("/profile", status_code=status.HTTP_201_CREATED)
def criar_company_profile(
    perfil: CompanyProfile,
) -> CompanyProfile:
    return _guardar_perfil_temporario(perfil)


@router.put("/profile")
def atualizar_company_profile(
    perfil: CompanyProfile,
) -> CompanyProfile:
    return _guardar_perfil_temporario(perfil)
