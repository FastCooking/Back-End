from fastapi import HTTPException, status

from src.models.Cardapio import Cardapio
from src.models.Estoque import Estoque
from src.repositories.FichaTecnicaRepository import FichaTecnicaRepository
from src.schemas.FichaTecnicaSchema import (
    CardapioFichaTecnicaItemDTO,
    CardapioResumoDTO,
    FichaTecnicaCompletaResponseDTO,
    FichaTecnicaCreateDTO,
    FichaTecnicaItemResponseDTO,
    FichaTecnicaResponseDTO,
)


class FichaTecnicaService:
    def __init__(self, db):
        self.db = db
        self.repository = FichaTecnicaRepository(db)

    def _to_response(self, fichas) -> FichaTecnicaResponseDTO:
        lista = fichas if isinstance(fichas, list) else [fichas]
        if not lista:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A ficha técnica deve conter ao menos um insumo.",
            )

        primeira = lista[0]
        return FichaTecnicaResponseDTO(
            idFichaTecnica=primeira.idFichaTecnica,
            idCardapio=primeira.idCardapio,
            insumos=[
                FichaTecnicaItemResponseDTO(
                    idEstoque=item.idEstoque,
                    quantidadeNecessaria=float(item.quantidadeNecessaria),
                )
                for item in lista
            ],
        )

    def criar_ficha_tecnica(
        self, payload: FichaTecnicaCreateDTO
    ) -> FichaTecnicaResponseDTO:
        cardapio = (
            self.db.query(Cardapio)
            .filter(Cardapio.idCardapio == payload.idCardapio)
            .first()
        )
        if cardapio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item de cardápio não encontrado.",
            )

        seen: set[int] = set()
        for item in payload.insumos:
            insumo = (
                self.db.query(Estoque)
                .filter(Estoque.idEstoque == item.idEstoque)
                .first()
            )
            if insumo is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Insumo com id {item.idEstoque} não encontrado.",
                )
            if item.idEstoque in seen:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="um mesmo insumo não pode ser associado duas vezes à mesma ficha técnica",
                )
            seen.add(item.idEstoque)

        fichas = self.repository.replace_for_cardapio(
            payload.idCardapio,
            [
                (item.idEstoque, float(item.quantidadeNecessaria))
                for item in payload.insumos
            ],
        )

        if not fichas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A ficha técnica deve conter ao menos um insumo.",
            )

        return self._to_response(fichas)

    def buscar_por_id(self, idFichaTecnica: int) -> FichaTecnicaResponseDTO:
        ficha = self.repository.get_by_id(idFichaTecnica)
        if ficha is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ficha técnica não encontrada.",
            )
        return self._to_response([ficha])

    def listar_por_cardapio(self, idCardapio: int) -> list[FichaTecnicaResponseDTO]:
        cardapio = (
            self.db.query(Cardapio).filter(Cardapio.idCardapio == idCardapio).first()
        )
        if cardapio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item de cardápio não encontrado.",
            )

        fichas = self.repository.get_by_cardapio(idCardapio)
        if not fichas:
            return []

        return [self._to_response([ficha]) for ficha in fichas]

    def buscar_ficha_completa_por_cardapio(
        self, idCardapio: int
    ) -> FichaTecnicaCompletaResponseDTO:
        cardapio = (
            self.db.query(Cardapio).filter(Cardapio.idCardapio == idCardapio).first()
        )
        if cardapio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item de cardápio não encontrado.",
            )

        fichas = self.repository.get_by_cardapio(idCardapio)
        if not fichas:
            return FichaTecnicaCompletaResponseDTO(
                cardapio=CardapioResumoDTO(
                    idCardapio=cardapio.idCardapio,
                    idRestaurante=cardapio.idRestaurante,
                    nome=cardapio.nome,
                    preco=float(cardapio.preco),
                    categoria=cardapio.categoria,
                    status=cardapio.status,
                ),
                insumos=[],
            )

        insumos = []
        for ficha in fichas:
            insumo = (
                self.db.query(Estoque)
                .filter(Estoque.idEstoque == ficha.idEstoque)
                .first()
            )
            if insumo is not None:
                insumos.append(
                    CardapioFichaTecnicaItemDTO(
                        idEstoque=insumo.idEstoque,
                        nome=insumo.nome,
                        quantidadeNecessaria=float(ficha.quantidadeNecessaria),
                        unidadeMedida=insumo.unidadeMedida,
                    )
                )

        return FichaTecnicaCompletaResponseDTO(
            cardapio=CardapioResumoDTO(
                idCardapio=cardapio.idCardapio,
                idRestaurante=cardapio.idRestaurante,
                nome=cardapio.nome,
                preco=float(cardapio.preco),
                categoria=cardapio.categoria,
                status=cardapio.status,
            ),
            insumos=insumos,
        )
