import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.core.security import exigir_funcao, get_current_user
from src.database.connection import get_db
from src.models.Usuario import Usuario
from src.schemas.UsuarioSchema import (
    FuncaoUsuario,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioStatusUpdate,
    UsuarioUpdate,
)
from src.services.UsuarioService import UsuarioService

router = APIRouter(prefix="/usuarios", tags=["Usuários"])

CARGOS_INFERIORES_GERENTE = ("Garcom", "Cozinheiro")


@router.post(
    "",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo usuário",
    description="Cadastra um novo funcionário. Adm pode criar qualquer função; Gerente apenas Garçom e Cozinheiro no seu restaurante.",
)
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
    usuario_logado: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
) -> UsuarioResponse:
    if usuario_logado.funcao == "Gerente":
        if dados.funcao not in CARGOS_INFERIORES_GERENTE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gerente só possui permissão para cadastrar funcionários de cargos inferiores: Garçom e Cozinheiro.",
            )
        # Trava o restaurante para o restaurante do gerente autenticado se não informado
        if not dados.idRestaurante:
            dados.idRestaurante = usuario_logado.idRestaurante

    service = UsuarioService(db)
    return service.create(dados)


@router.get(
    "",
    response_model=list[UsuarioResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar usuários",
    description="Retorna a lista de usuários. Gerente visualiza apenas os funcionários do seu próprio restaurante.",
)
def listar_usuarios(
    idRestaurante: uuid.UUID | None = Query(
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
    usuario_logado: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
) -> list[UsuarioResponse]:
    # Se for Gerente, restringe estritamente ao seu próprio restaurante
    if usuario_logado.funcao == "Gerente":
        idRestaurante = usuario_logado.idRestaurante

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
    idUsuario: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_logado: Usuario = Depends(get_current_user),
) -> UsuarioResponse:
    service = UsuarioService(db)
    usuario_alvo = service.get_by_id(idUsuario)

    # Adm e o próprio usuário podem ver tudo. Gerente só vê usuários do seu restaurante.
    if usuario_logado.funcao == "Gerente":
        if usuario_alvo.idRestaurante != usuario_logado.idRestaurante:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para visualizar usuários de outro restaurante.",
            )

    return usuario_alvo


@router.put(
    "/{idUsuario}",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar usuário",
    description="Atualiza os dados de um usuário existente com validação de hierarquia.",
)
def atualizar_usuario(
    idUsuario: uuid.UUID,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario_logado: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
) -> UsuarioResponse:
    service = UsuarioService(db)
    usuario_alvo = service.get_by_id(idUsuario)

    if usuario_logado.funcao == "Gerente":
        if usuario_alvo.idRestaurante != usuario_logado.idRestaurante:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para atualizar usuários de outro restaurante.",
            )
        if usuario_alvo.funcao in ("Adm", "Gerente") and usuario_alvo.idUsuario != usuario_logado.idUsuario:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gerente não possui permissão para editar Administradores ou outros Gerentes.",
            )
        if dados.funcao and dados.funcao not in CARGOS_INFERIORES_GERENTE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gerente só pode atribuir cargos inferiores: Garçom ou Cozinheiro.",
            )

    return service.update(idUsuario, dados)


@router.patch(
    "/{idUsuario}",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar parcialmente usuário",
    description="Atualiza campos específicos de um usuário com validação de hierarquia.",
)
def atualizar_parcial_usuario(
    idUsuario: uuid.UUID,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario_logado: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
) -> UsuarioResponse:
    return atualizar_usuario(idUsuario, dados, db, usuario_logado)


@router.patch(
    "/{idUsuario}/status",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Alterar status do usuário",
    description="Ativa ou desativa um usuário no sistema com validação de hierarquia.",
)
def alterar_status_usuario(
    idUsuario: uuid.UUID,
    dados: UsuarioStatusUpdate,
    db: Session = Depends(get_db),
    usuario_logado: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
) -> UsuarioResponse:
    service = UsuarioService(db)
    usuario_alvo = service.get_by_id(idUsuario)

    if usuario_logado.funcao == "Gerente":
        if usuario_alvo.idRestaurante != usuario_logado.idRestaurante:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para alterar status de usuários de outro restaurante.",
            )
        if usuario_alvo.funcao in ("Adm", "Gerente"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gerente não possui permissão para desativar Administradores ou outros Gerentes.",
            )

    return service.change_status(idUsuario, dados.status)


@router.delete(
    "/{idUsuario}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover usuário",
    description="Remove o usuário através do método de exclusão com validação de hierarquia.",
)
def deletar_usuario(
    idUsuario: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_logado: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    service = UsuarioService(db)
    usuario_alvo = service.get_by_id(idUsuario)

    if usuario_logado.funcao == "Gerente":
        if usuario_alvo.idRestaurante != usuario_logado.idRestaurante:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para remover usuários de outro restaurante.",
            )
        if usuario_alvo.funcao in ("Adm", "Gerente"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gerente não possui permissão para remover Administradores ou outros Gerentes.",
            )

    service.delete(idUsuario)
