import os
import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.core.security import exigir_funcao
from src.database.connection import get_db
from src.models.Usuario import Usuario
from src.schemas.CardapioSchema import (
    CardapioCreate,
    CardapioResponse,
    CardapioStatusUpdate,
    CardapioUpdate,
)
from src.services.CardapioService import CardapioService

SECRET_KEY = os.getenv("JWT_SECRET") or "fastcooking_default_secret_key_change_in_prod"
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
            return Usuario.get_by_id(db, uuid.UUID(str(id_usuario)))
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
    usuario: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    service = CardapioService(db)
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        file_obj = form.get("file")
        file = file_obj if hasattr(file_obj, "filename") and getattr(file_obj, "filename", None) else None

        path_image = form.get("pathImage")
        if file:
            path_image = await service.salvar_e_comprimir_imagem(file)
        elif path_image == "":
            path_image = None

        id_restaurante_val = form.get("idRestaurante")
        id_restaurante = uuid.UUID(str(id_restaurante_val)) if id_restaurante_val else None

        dados = CardapioCreate(
            nome=str(form.get("nome")),
            preco=float(form.get("preco")),
            categoria=str(form.get("categoria")),
            descricao=form.get("descricao") or None,
            pathImage=path_image or None,
            idRestaurante=id_restaurante,
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
    idRestaurante: uuid.UUID = Query(..., description="ID do Restaurante"),
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
    idCardapio: uuid.UUID,
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
    idCardapio: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    service = CardapioService(db)
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        file_obj = form.get("file")
        file = file_obj if hasattr(file_obj, "filename") and getattr(file_obj, "filename", None) else None

        path_image = form.get("pathImage")
        if file:
            path_image = await service.salvar_e_comprimir_imagem(file)
        elif path_image == "":
            path_image = None

        dados_dict = {}
        if form.get("nome"):
            dados_dict["nome"] = form["nome"]
        if form.get("preco"):
            dados_dict["preco"] = float(form["preco"])
        if form.get("categoria"):
            dados_dict["categoria"] = form["categoria"]
        if form.get("tempoPreparo"):
            dados_dict["tempoPreparo"] = int(form["tempoPreparo"])
        if "descricao" in form:
            dados_dict["descricao"] = form["descricao"] or None
        if path_image is not None or "pathImage" in form or file:
            dados_dict["pathImage"] = path_image
        status_raw = form.get("status") if form.get("status") is not None else form.get("disponivel")
        if status_raw is not None:
            dados_dict["status"] = str(status_raw).strip().lower() in ("true", "1", "yes", "sim")

        dados = CardapioUpdate(**dados_dict)
    else:
        body = await request.json()
        if "disponivel" in body and "status" not in body:
            body["status"] = bool(body["disponivel"])
        dados = CardapioUpdate(**body)

    return service.editar(
        idCardapio=idCardapio,
        dados=dados,
        usuario=usuario,
    )


@router.patch(
    "/{idCardapio}/status",
    response_model=CardapioResponse,
    status_code=status.HTTP_200_OK,
    summary="Alternar status de disponibilidade do item do cardápio",
)
@router.put(
    "/{idCardapio}/status",
    response_model=CardapioResponse,
    status_code=status.HTTP_200_OK,
    summary="Alternar status de disponibilidade do item do cardápio",
)
def alterar_status_item(
    idCardapio: uuid.UUID,
    dados: CardapioStatusUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    service = CardapioService(db)
    return service.alterar_status(
        idCardapio=idCardapio,
        novo_status=dados.status,
        usuario=usuario,
    )


@router.post(
    "/{idCardapio}",
    response_model=CardapioResponse,
    status_code=status.HTTP_200_OK,
    summary="Editar item do cardápio (alias POST multipart)",
)
async def editar_item_post(
    idCardapio: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    return await editar_item(
        idCardapio=idCardapio,
        request=request,
        db=db,
        usuario=usuario,
    )


@router.delete(
    "/{idCardapio}",
    status_code=status.HTTP_200_OK,
    summary="Desativar item do cardápio",
)
def excluir_item(
    idCardapio: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(exigir_funcao("Gerente", "Adm")),
):
    service = CardapioService(db)

    service.excluir(
        idCardapio=idCardapio,
        usuario=usuario,
    )

    return {
        "message": "Item do cardápio desativado com sucesso.",
    }
