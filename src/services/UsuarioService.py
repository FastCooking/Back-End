import bcrypt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.schemas.UsuarioSchema import UsuarioCreate, UsuarioUpdate


def hash_senha(senha: str) -> str:
    """Gera hash seguro bcrypt para a senha."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha.encode("utf-8"), salt).decode("utf-8")


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """Verifica se a senha em texto plano coincide com o hash bcrypt."""
    try:
        return bcrypt.checkpw(
            senha_plana.encode("utf-8"), senha_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


class UsuarioService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: UsuarioCreate) -> Usuario:
        """Cria um novo usuário/funcionário validando regras de negócio e chamando Usuario.create."""
        # 1. Verifica ou obtém o restaurante vinculado
        idRestaurante = data.idRestaurante
        if idRestaurante is None:
            restaurante_padrao = self.db.query(Restaurante).first()
            if not restaurante_padrao:
                restaurante_padrao = Restaurante.create(
                    db=self.db,
                    nome="Restaurante Principal",
                    cnpj="12.345.678/0001-99",
                    telefone="(11) 98765-4321",
                    email="contato@restaurante.com",
                    cep="01001-000",
                    status=True,
                )
            idRestaurante = restaurante_padrao.idRestaurante
        else:
            restaurante = Restaurante.get_by_id(self.db, idRestaurante)
            if not restaurante:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Restaurante com ID {idRestaurante} não encontrado.",
                )

        # 2. Verifica se o e-mail/login já está cadastrado
        email_existente = Usuario.get_by_email(self.db, data.email)
        if email_existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um usuário cadastrado com o e-mail/login '{data.email}'.",
            )

        # 3. Verifica ou gera CPF válido se não informado
        cpf_final = data.cpf
        if cpf_final is None:
            import time
            ts = int(time.time() * 1000) % 1000000000
            base_dig = f"{ts:09d}"
            soma1 = sum(int(base_dig[i]) * (10 - i) for i in range(9))
            d1 = 0 if (soma1 * 10) % 11 == 10 else (soma1 * 10) % 11
            soma2 = sum(int((base_dig + str(d1))[i]) * (11 - i) for i in range(10))
            d2 = 0 if (soma2 * 10) % 11 == 10 else (soma2 * 10) % 11
            cpf_final = f"{base_dig[:3]}.{base_dig[3:6]}.{base_dig[6:9]}-{d1}{d2}"
        else:
            cpf_existente = Usuario.get_by_cpf(self.db, cpf_final)
            if cpf_existente:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Já existe um usuário cadastrado com o CPF '{cpf_final}'.",
                )

        # 4. Cria o usuário delegando ao método create do Model
        senha_hasheada = hash_senha(data.senha)
        return Usuario.create(
            db=self.db,
            idRestaurante=idRestaurante,
            nome=data.nome,
            cpf=cpf_final,
            email=data.email,
            senha=senha_hasheada,
            funcao=data.funcao,
        )

    def get_by_id(self, idUsuario: int) -> Usuario:
        """Busca um usuário pelo ID ou levanta 404."""
        usuario = Usuario.get_by_id(self.db, idUsuario)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuário com ID {idUsuario} não encontrado.",
            )
        return usuario

    def list_all(
        self,
        idRestaurante: int | None = None,
        funcao: str | None = None,
        status_filtro: bool | None = None,
        busca: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Usuario]:
        """Lista usuários com filtros e paginação."""
        query = self.db.query(Usuario)

        if idRestaurante is not None:
            query = query.filter(Usuario.idRestaurante == idRestaurante)

        if funcao is not None:
            query = query.filter(Usuario.funcao == funcao)

        if status_filtro is not None:
            query = query.filter(Usuario.status == status_filtro)

        if busca:
            termo = f"%{busca}%"
            query = query.filter(
                (Usuario.nome.ilike(termo)) | (Usuario.email.ilike(termo))
            )

        return (
            query.order_by(Usuario.idUsuario.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, idUsuario: int, data: UsuarioUpdate) -> Usuario:
        """Atualiza dados cadastrais de um usuário com validações."""
        usuario = self.get_by_id(idUsuario)

        # Se alterar e-mail, verifica se já não pertence a outro usuário
        if data.email is not None and data.email != usuario.email:
            email_em_uso = (
                self.db.query(Usuario)
                .filter(
                    Usuario.email == data.email,
                    Usuario.idUsuario != idUsuario,
                )
                .first()
            )
            if email_em_uso:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"O e-mail '{data.email}' já está em uso por outro usuário.",
                )

        # Se alterar CPF, verifica se já não pertence a outro usuário
        if data.cpf is not None and data.cpf != usuario.cpf:
            cpf_em_uso = (
                self.db.query(Usuario)
                .filter(
                    Usuario.cpf == data.cpf,
                    Usuario.idUsuario != idUsuario,
                )
                .first()
            )
            if cpf_em_uso:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"O CPF '{data.cpf}' já está em uso por outro usuário.",
                )

        nova_senha = hash_senha(data.senha) if data.senha is not None else None

        return usuario.update(
            db=self.db,
            nome=data.nome,
            cpf=data.cpf,
            email=data.email,
            senha=nova_senha,
            funcao=data.funcao,
        )

    def change_status(self, idUsuario: int, novo_status: bool) -> Usuario:
        """Altera o status de um usuário delegando aos métodos able/disable do Model."""
        usuario = self.get_by_id(idUsuario)
        if novo_status:
            usuario.able(self.db)
        else:
            usuario.disable(self.db)
        return usuario

    def delete(self, idUsuario: int) -> bool:
        """Remove o usuário através do método delete do Model."""
        usuario = self.get_by_id(idUsuario)
        return usuario.delete(self.db)
