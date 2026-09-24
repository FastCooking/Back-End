import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.schemas.RestauranteSchema import (
    RestauranteComUsuarioCreate,
    RestauranteCreate,
    RestauranteUpdate,
)
from src.services.UsuarioService import hash_senha


class RestauranteService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: RestauranteCreate) -> Restaurante:
        """Cria um novo restaurante validando unicidade de CNPJ e E-mail e chamando Restaurante.create."""
        # 1. Verifica se o CNPJ já está cadastrado
        cnpj_existente = Restaurante.get_by_cnpj(self.db, data.cnpj)
        if cnpj_existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um restaurante cadastrado com o CNPJ '{data.cnpj}'.",
            )

        # 2. Verifica se o e-mail já está cadastrado
        email_existente = Restaurante.get_by_email(self.db, data.email)
        if email_existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um restaurante cadastrado com o e-mail '{data.email}'.",
            )

        # 3. Cria e persiste o restaurante via Model
        return Restaurante.create(
            db=self.db,
            nome=data.nome,
            cnpj=data.cnpj,
            telefone=data.telefone,
            email=data.email,
            cep=data.cep,
            status=data.status,
        )

    def create_with_user(
        self, data: RestauranteComUsuarioCreate
    ) -> tuple[Restaurante, Usuario]:
        """Cria um restaurante e o usuário inicial/gerente de forma atômica dentro de uma transação."""
        # 1. Validações prévias de unicidade para o Restaurante
        if Restaurante.get_by_cnpj(self.db, data.restaurante.cnpj):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um restaurante cadastrado com o CNPJ '{data.restaurante.cnpj}'.",
            )
        if Restaurante.get_by_email(self.db, data.restaurante.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um restaurante cadastrado com o e-mail '{data.restaurante.email}'.",
            )

        # 2. Validações prévias de unicidade para o Usuário
        if Usuario.get_by_email(self.db, data.usuario.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um usuário cadastrado com o e-mail/login '{data.usuario.email}'.",
            )

        cpf_final = data.usuario.cpf
        if cpf_final is not None:
            if Usuario.get_by_cpf(self.db, cpf_final):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Já existe um usuário cadastrado com o CPF '{cpf_final}'.",
                )
        else:
            import time
            ts = int(time.time() * 1000) % 1000000000
            base_dig = f"{ts:09d}"
            soma1 = sum(int(base_dig[i]) * (10 - i) for i in range(9))
            d1 = 0 if (soma1 * 10) % 11 == 10 else (soma1 * 10) % 11
            soma2 = sum(int((base_dig + str(d1))[i]) * (11 - i) for i in range(10))
            d2 = 0 if (soma2 * 10) % 11 == 10 else (soma2 * 10) % 11
            cpf_final = f"{base_dig[:3]}.{base_dig[3:6]}.{base_dig[6:9]}-{d1}{d2}"

        # 3. Execução transacional atômica
        try:
            # Cria o restaurante sem efetivar commit
            restaurante = Restaurante.create(
                db=self.db,
                nome=data.restaurante.nome,
                cnpj=data.restaurante.cnpj,
                telefone=data.restaurante.telefone,
                email=data.restaurante.email,
                cep=data.restaurante.cep,
                status=data.restaurante.status,
                commit=False,
            )
            self.db.flush()

            # Cria o usuário associado
            senha_hasheada = hash_senha(data.usuario.senha)
            usuario = Usuario.create(
                db=self.db,
                idRestaurante=restaurante.idRestaurante,
                nome=data.usuario.nome,
                cpf=cpf_final,
                email=data.usuario.email,
                senha=senha_hasheada,
                funcao=data.usuario.funcao or "Gerente",
                commit=False,
            )
            self.db.flush()

            # Se ambas as operações forem bem-sucedidas, efetivar o COMMIT
            self.db.commit()
            self.db.refresh(restaurante)
            self.db.refresh(usuario)
            return restaurante, usuario
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, idRestaurante: uuid.UUID | str) -> Restaurante:
        """Busca um restaurante pelo ID ou levanta 404."""
        restaurante = Restaurante.get_by_id(self.db, idRestaurante)
        if not restaurante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurante com ID {idRestaurante} não encontrado.",
            )
        return restaurante

    def list_all(self, status_filtro: bool | None = None, busca: str | None = None, skip: int = 0, limit: int = 100,) -> list[Restaurante]:
        """Lista restaurantes cadastrados com filtros e paginação."""
        query = self.db.query(Restaurante)

        if status_filtro is not None:
            query = query.filter(Restaurante.status == status_filtro)

        if busca:
            termo = f"%{busca}%"
            query = query.filter(
                (Restaurante.nome.ilike(termo))
                | (Restaurante.cnpj.ilike(termo))
                | (Restaurante.email.ilike(termo))
            )

        return (
            query.order_by(Restaurante.nome.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, idRestaurante: uuid.UUID | str, data: RestauranteUpdate) -> Restaurante:
        """Atualiza os dados de um restaurante com validações."""
        restaurante = self.get_by_id(idRestaurante)

        # Se alterar CNPJ, verifica duplicidade
        if data.cnpj is not None and data.cnpj != restaurante.cnpj:
            cnpj_em_uso = (
                self.db.query(Restaurante)
                .filter(
                    Restaurante.cnpj == data.cnpj,
                    Restaurante.idRestaurante != idRestaurante,
                )
                .first()
            )
            if cnpj_em_uso:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"O CNPJ '{data.cnpj}' já está em uso por outro restaurante.",
                )

        # Se alterar e-mail, verifica duplicidade
        if data.email is not None and data.email != restaurante.email:
            email_em_uso = (
                self.db.query(Restaurante)
                .filter(
                    Restaurante.email == data.email,
                    Restaurante.idRestaurante != idRestaurante,
                )
                .first()
            )
            if email_em_uso:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"O e-mail '{data.email}' já está em uso por outro restaurante.",
                )

        return restaurante.update(
            db=self.db,
            nome=data.nome,
            cnpj=data.cnpj,
            telefone=data.telefone,
            email=data.email,
            cep=data.cep,
            status=data.status,
        )

    def change_status(self, idRestaurante: uuid.UUID | str, novo_status: bool) -> Restaurante:
        """Altera o status do restaurante via métodos able/disable do Model."""
        restaurante = self.get_by_id(idRestaurante)
        if novo_status:
            restaurante.able(self.db)
        else:
            restaurante.disable(self.db)
        return restaurante

    def delete(self, idRestaurante: uuid.UUID | str) -> bool:
        """Anonimiza e desativa o restaurante e todos os seus usuários dependentes em cascata de forma transacional."""
        restaurante = self.get_by_id(idRestaurante)

        try:
            # 1. Soft delete e anonimização do restaurante
            restaurante.delete(self.db, commit=False)

            # 2. Soft delete e anonimização em cascata dos usuários do restaurante
            usuarios = (
                self.db.query(Usuario)
                .filter(Usuario.idRestaurante == idRestaurante)
                .all()
            )
            for usuario in usuarios:
                usuario.delete(self.db, commit=False)

            # 3. Commit de toda a operação
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise
