from sqlalchemy.orm import Session

from src.models.FichaTecnica import FichaTecnica


class FichaTecnicaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, idCardapio: int, idEstoque: int, quantidadeNecessaria: float
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
        self, idCardapio: int, insumos: list[tuple[int, float]]
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

    def get_by_id(self, idFichaTecnica: int) -> FichaTecnica | None:
        return (
            self.db.query(FichaTecnica)
            .filter(FichaTecnica.idFichaTecnica == idFichaTecnica)
            .first()
        )

    def get_by_cardapio(self, idCardapio: int) -> list[FichaTecnica]:
        return (
            self.db.query(FichaTecnica)
            .filter(FichaTecnica.idCardapio == idCardapio)
            .order_by(FichaTecnica.idEstoque.asc())
            .all()
        )

    def exists_for_cardapio_and_insumo(self, idCardapio: int, idEstoque: int) -> bool:
        return (
            self.db.query(FichaTecnica)
            .filter(
                FichaTecnica.idCardapio == idCardapio,
                FichaTecnica.idEstoque == idEstoque,
            )
            .first()
            is not None
        )
