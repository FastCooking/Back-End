from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.schemas.UsuarioSchema import (
    FuncaoUsuario,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioStatusUpdate,
    UsuarioUpdate,
)
from src.services.UsuarioService import UsuarioService

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.post(
    "",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo usuário",
    description="Cadastra um novo funcionário/usuário com validações de CPF, e-mail único e hash de senha.",
)
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
) -> UsuarioResponse:
    service = UsuarioService(db)
    return service.create(dados)


@router.get(
    "",
    response_model=list[UsuarioResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar usuários",
    description="Retorna a lista de usuários cadastrados com opções de filtro e paginação.",
)
def listar_usuarios(
    idRestaurante: int | None = Query(
        default=None, description="Filtrar por Restaurante"
    ),
    funcao: FuncaoUsuario | None = Query(
        default=None, description="Filtrar por cargo/função"
    ),
    status_filtro: bool | None = Query(
        default=None, alias="status", description="Filtrar por status ativo/inativo"
    ),
    busca: str | None = Query(
        default=None, description="Buscar por nome ou e-mail"
    ),
    skip: int = Query(default=0, ge=0, description="Registros a ignorar (offset)"),
    limit: int = Query(
        default=100, ge=1, le=500, description="Quantidade máxima de registros"
    ),
    db: Session = Depends(get_db),
) -> list[UsuarioResponse]:
    service = UsuarioService(db)
    return service.list_all(
        idRestaurante=idRestaurante,
        funcao=funcao,
        status_filtro=status_filtro,
        busca=busca,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{idUsuario}",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Obter usuário por ID",
    description="Retorna os dados cadastrais de um usuário específico.",
)
def obter_usuario_por_id(
    idUsuario: int,
    db: Session = Depends(get_db),
) -> UsuarioResponse:
    service = UsuarioService(db)
    return service.get_by_id(idUsuario)


@router.put(
    "/{idUsuario}",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar usuário",
    description="Atualiza os dados de um usuário existente com validações.",
)
def atualizar_usuario(
    idUsuario: int,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
) -> UsuarioResponse:
    service = UsuarioService(db)
    return service.update(idUsuario, dados)


@router.patch(
    "/{idUsuario}",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar parcialmente usuário",
    description="Atualiza campos específicos de um usuário.",
)
def atualizar_parcial_usuario(
    idUsuario: int,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
) -> UsuarioResponse:
    service = UsuarioService(db)
    return service.update(idUsuario, dados)


@router.patch(
    "/{idUsuario}/status",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Alterar status do usuário",
    description="Ativa ou desativa um usuário no sistema.",
)
def alterar_status_usuario(
    idUsuario: int,
    dados: UsuarioStatusUpdate,
    db: Session = Depends(get_db),
) -> UsuarioResponse:
    service = UsuarioService(db)
    return service.change_status(idUsuario, dados.status)


@router.delete(
    "/{idUsuario}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover usuário",
    description="Remove o usuário através do método de exclusão do Model.",
)
def deletar_usuario(
    idUsuario: int,
    db: Session = Depends(get_db),
):
    service = UsuarioService(db)
    service.delete(idUsuario)
