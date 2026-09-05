from fastapi import HTTPException, status

from src.repositories.EstoqueRepository import EstoqueRepository
from src.schemas.EstoqueSchema import EstoqueCreateDTO, EstoqueResponseDTO


class EstoqueService:
    def __init__(self, db):
        self.repository = EstoqueRepository(db)

    def criar_insumo(self, payload: EstoqueCreateDTO) -> EstoqueResponseDTO:
        try:
            insumo = self.repository.create(
                nome=payload.nome,
                quantidadeEmEstoque=payload.quantidadeEmEstoque,
                quantidadeMinima=payload.quantidadeMinima,
                idRestaurante=payload.idRestaurante,
                unidadeMedida=payload.unidadeMedida,
                pathImage=payload.pathImage,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Erro ao criar insumo: {str(exc)}",
            ) from exc

        return EstoqueResponseDTO(
            idEstoque=insumo.idEstoque,
            nome=insumo.nome,
            quantidadeEmEstoque=float(insumo.quantidadeEstoque),
            quantidadeMinima=float(insumo.quantidadeMinima),
            idRestaurante=insumo.idRestaurante,
            unidadeMedida=insumo.unidadeMedida,
            pathImage=insumo.pathImage,
        )

    def buscar_por_id(self, idEstoque: int) -> EstoqueResponseDTO:
        insumo = self.repository.get_by_id(idEstoque)
        if insumo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insumo não encontrado.",
            )

        return EstoqueResponseDTO(
            idEstoque=insumo.idEstoque,
            nome=insumo.nome,
            quantidadeEmEstoque=float(insumo.quantidadeEstoque),
            quantidadeMinima=float(insumo.quantidadeMinima),
            idRestaurante=insumo.idRestaurante,
            unidadeMedida=insumo.unidadeMedida,
        )

    def listar_insumos(self) -> list[EstoqueResponseDTO]:
        insumos = self.repository.list_all()
        return [
            EstoqueResponseDTO(
                idEstoque=item.idEstoque,
                nome=item.nome,
                quantidadeEmEstoque=float(item.quantidadeEstoque),
                quantidadeMinima=float(item.quantidadeMinima),
                idRestaurante=item.idRestaurante,
                unidadeMedida=item.unidadeMedida,
                pathImage=item.pathImage,
            )
            for item in insumos
        ]
