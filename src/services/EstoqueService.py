from fastapi import HTTPException, status

from src.repositories.EstoqueRepository import EstoqueRepository
from src.schemas.EstoqueSchema import EstoqueCreateDTO, EstoqueResponseDTO, EstoqueUpdateDTO


class EstoqueService:
    def __init__(self, db):
        self.repository = EstoqueRepository(db)

    def _to_response(self, insumo) -> EstoqueResponseDTO:
        return EstoqueResponseDTO(
            idEstoque=insumo.idEstoque,
            nome=insumo.nome,
            quantidadeEmEstoque=float(insumo.quantidadeEstoque),
            quantidadeMinima=float(insumo.quantidadeMinima),
            idRestaurante=insumo.idRestaurante,
            unidadeMedida=insumo.unidadeMedida,
            pathImage=insumo.pathImage,
        )

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
                detail=f"Erro ao criar insumo: {exc!s}",
            ) from exc

        return self._to_response(insumo)

    def buscar_por_id(self, idEstoque: int) -> EstoqueResponseDTO:
        insumo = self.repository.get_by_id(idEstoque)
        if insumo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insumo não encontrado.",
            )

        return self._to_response(insumo)

    def listar_insumos(self) -> list[EstoqueResponseDTO]:
        insumos = self.repository.list_all()
        return [self._to_response(item) for item in insumos]

    def atualizar_insumo(
        self,
        idEstoque: int,
        payload: EstoqueCreateDTO | EstoqueUpdateDTO,
    ) -> EstoqueResponseDTO:
        insumo = self.repository.get_by_id(idEstoque)
        if insumo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insumo não encontrado.",
            )

        dados = payload.model_dump(exclude_unset=True)
        if not dados:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhum campo foi informado para atualização.",
            )

        insumo_atualizado = self.repository.update(idEstoque, **dados)
        return self._to_response(insumo_atualizado)

    def excluir_insumo(self, idEstoque: int) -> bool:
        if not self.repository.delete(idEstoque):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insumo não encontrado.",
            )
        return True
