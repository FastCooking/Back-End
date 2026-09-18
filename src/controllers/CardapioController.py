import os

from fastapi import APIRouter, Depends, Query, Request, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.models.Usuario import Usuario
from src.schemas.CardapioSchema import (
    CardapioCreate,
    CardapioResponse,
    CardapioUpdate,
)
from src.services.CardapioService import CardapioService

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
security_optional = HTTPBearer(auto_error=False)


def get_optional_user(
    credenciais: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: Session = Depends(get_db),
) -> Usuario | None:
    if credenciais is None or not SECRET_KEY:
        return None
    try:
        payload = jwt.decode(credenciais.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        id_usuario = payload.get("sub")
        if id_usuario:
            return Usuario.get_by_id(db, int(id_usuario))
    except (JWTError, ValueError):
        return None
    return None


router = APIRouter(
    prefix="/cardapio",
    tags=["Cardápio"],
)


@router.post(
    "",
    response_model=CardapioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar item do cardápio",
)
async def criar_item(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
):
    service = CardapioService(db)
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        file_obj = form.get("file")
        file = file_obj if isinstance(file_obj, UploadFile) else None

        path_image = form.get("pathImage")
        if file and file.filename:
            path_image = await service.salvar_e_comprimir_imagem(file)

        dados = CardapioCreate(
            nome=form.get("nome"),
            preco=float(form.get("preco")),
            categoria=form.get("categoria"),
            descricao=form.get("descricao") or None,
            pathImage=path_image or None,
            idRestaurante=int(form.get("idRestaurante")) if form.get("idRestaurante") else None,
        )
    else:
        body = await request.json()
        dados = CardapioCreate(**body)

    return service.criar(
        dados=dados,
        usuario=usuario,
    )


@router.get(
    "",
    response_model=list[CardapioResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar itens do cardápio",
)
def listar_itens(
    idRestaurante: int = Query(default=1),
    db: Session = Depends(get_db),
):
    service = CardapioService(db)

    return service.listar(
        idRestaurante=idRestaurante,
    )


@router.get(
    "/{idCardapio}",
    response_model=CardapioResponse,
    status_code=status.HTTP_200_OK,
    summary="Buscar item do cardápio",
)
def buscar_item(
    idCardapio: int,
    db: Session = Depends(get_db),
):
    service = CardapioService(db)

    return service.buscar_por_id(idCardapio)


@router.put(
    "/{idCardapio}",
    response_model=CardapioResponse,
    status_code=status.HTTP_200_OK,
    summary="Editar item do cardápio",
)
async def editar_item(
    idCardapio: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
):
    service = CardapioService(db)
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        file_obj = form.get("file")
        file = file_obj if isinstance(file_obj, UploadFile) else None

        path_image = form.get("pathImage")
        if file and file.filename:
            path_image = await service.salvar_e_comprimir_imagem(file)

        dados_dict = {}
        if "nome" in form and form["nome"]:
            dados_dict["nome"] = form["nome"]
        if "preco" in form and form["preco"]:
            dados_dict["preco"] = float(form["preco"])
        if "categoria" in form and form["categoria"]:
            dados_dict["categoria"] = form["categoria"]
        if "descricao" in form:
            dados_dict["descricao"] = form["descricao"] or None
        if path_image is not None or "pathImage" in form or (file and file.filename):
            dados_dict["pathImage"] = path_image

        dados = CardapioUpdate(**dados_dict)
    else:
        body = await request.json()
        dados = CardapioUpdate(**body)

    return service.editar(
        idCardapio=idCardapio,
        dados=dados,
        usuario=usuario,
    )


@router.delete(
    "/{idCardapio}",
    status_code=status.HTTP_200_OK,
    summary="Desativar item do cardápio",
)
def excluir_item(
    idCardapio: int,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(get_optional_user),
):
    service = CardapioService(db)

    service.excluir(
        idCardapio=idCardapio,
        usuario=usuario,
    )

    return {
        "message": "Item do cardápio desativado com sucesso.",
    }
