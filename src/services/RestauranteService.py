from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.Restaurante import Restaurante
from src.schemas.RestauranteSchema import RestauranteCreate, RestauranteUpdate


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

    def get_by_id(self, idRestaurante: int) -> Restaurante:
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
            query.order_by(Restaurante.idRestaurante.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, idRestaurante: int, data: RestauranteUpdate) -> Restaurante:
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

    def change_status(self, idRestaurante: int, novo_status: bool) -> Restaurante:
        """Altera o status do restaurante via métodos able/disable do Model."""
        restaurante = self.get_by_id(idRestaurante)
        if novo_status:
            restaurante.able(self.db)
        else:
            restaurante.disable(self.db)
        return restaurante

    def delete(self, idRestaurante: int) -> bool:
        """Desativa o restaurante (soft delete via disable do Model)."""
        restaurante = self.get_by_id(idRestaurante)
        restaurante.disable(self.db)
        return True
