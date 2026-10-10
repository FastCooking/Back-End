import uuid

from sqlalchemy.orm import Session

from src.models.FichaTecnica import FichaTecnica


class FichaTecnicaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        idCardapio: uuid.UUID | str,
        idEstoque: uuid.UUID | str,
        quantidadeNecessaria: float,
    ) -> FichaTecnica:
        ficha = FichaTecnica(
            idCardapio=idCardapio,
            idEstoque=idEstoque,
            quantidadeNecessaria=quantidadeNecessaria,
        )
        self.db.add(ficha)
        self.db.commit()
        self.db.refresh(ficha)
        return ficha

    def replace_for_cardapio(
        self,
        idCardapio: uuid.UUID | str,
        insumos: list[tuple[uuid.UUID | str, float]],
    ) -> list[FichaTecnica]:
        try:
            self.db.query(FichaTecnica).filter(
                FichaTecnica.idCardapio == idCardapio
            ).delete()

            criadas: list[FichaTecnica] = []
            for idEstoque, quantidade in insumos:
                ficha = FichaTecnica(
                    idCardapio=idCardapio,
                    idEstoque=idEstoque,
                    quantidadeNecessaria=quantidade,
                )
                self.db.add(ficha)
                criadas.append(ficha)

            self.db.flush()
            self.db.commit()
            for ficha in criadas:
                self.db.refresh(ficha)
            return criadas
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, idFichaTecnica: uuid.UUID | str) -> FichaTecnica | None:
        return (
            self.db.query(FichaTecnica)
            .filter(FichaTecnica.idFichaTecnica == idFichaTecnica)
            .first()
        )

    def get_by_cardapio(self, idCardapio: uuid.UUID | str) -> list[FichaTecnica]:
        return (
            self.db.query(FichaTecnica)
            .filter(FichaTecnica.idCardapio == idCardapio)
            .all()
        )

    def exists_for_cardapio_and_insumo(
        self, idCardapio: uuid.UUID | str, idEstoque: uuid.UUID | str
    ) -> bool:
        return (
            self.db.query(FichaTecnica)
            .filter(
                FichaTecnica.idCardapio == idCardapio,
                FichaTecnica.idEstoque == idEstoque,
            )
            .first()
            is not None
        )
