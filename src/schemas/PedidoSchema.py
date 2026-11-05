import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PedidoItemCreate(BaseModel):
    idCardapio: uuid.UUID
    quantidade: int = Field(default=1, gt=0)
    observacao: str | None = None


class PedidoCreate(BaseModel):
    idMesa: uuid.UUID
    sessao_id: str | None = None
    itens: list[PedidoItemCreate] = Field(min_length=1)


class ItemPedidoStatusUpdate(BaseModel):
    status: Literal["Pendente", "Em preparo", "Pronto", "Entregue"]


class ItemPayloadSchema(BaseModel):
    item_id: uuid.UUID = Field(..., description="ID do produto no cardápio")
    quantidade: int = Field(..., ge=1)
    observacoes: str | None = None


class PedidoCriarSchema(BaseModel):
    sessao_id: str = Field(..., description="Identificador único da sessão/mesa")
    idRestaurante: uuid.UUID
    idMesa: uuid.UUID
    idGarcom: uuid.UUID | None = None
    itens: list[ItemPayloadSchema] = Field(min_length=1)


class ItemResponseSchema(BaseModel):
    idItemPedido: uuid.UUID
    idCardapio: uuid.UUID
    quantidade: int
    precoUnitario: float
    status: str
    observacao: str | None
    categoria: str | None = None
    prioridade: int = 1

    model_config = ConfigDict(from_attributes=True)


class PedidoResponseSchema(BaseModel):
    idPedido: uuid.UUID
    sessao_id: str | None
    status: str
    dataAbertura: datetime
    desconto: float = 0.0
    tipoDesconto: str | None = None
    itens: list[ItemResponseSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ItemPedidoQuantidadeUpdate(BaseModel):
    quantidade: int = Field(..., ge=0, description="Nova quantidade do item (0 cancela o item)")


class ItemCancelamentoRequest(BaseModel):
    justificativa: str | None = Field(None, description="Justificativa para cancelamento do item (RF11)")
    motivo: str | None = Field(None, description="Motivo alternativo para cancelamento")


class DescontoApplyRequest(BaseModel):
    senhaGerente: str | None = Field(None, description="Senha do gerente autorizador da operação")
    senha: str | None = Field(None, description="Alias para senhaGerente")
    tipo: str = Field(default="valor", description="Tipo do desconto: 'percentual' ou 'valor'")
    valor: float = Field(..., gt=0, description="Valor do desconto (reais ou percentual)")
    motivo: str | None = Field(None, description="Motivo ou justificativa da concessão do desconto")
    justificativa: str | None = Field(None, description="Alias para motivo")
    emailGerente: str | None = Field(None, description="E-mail opcional do gerente para identificação direta")
    idGerente: uuid.UUID | None = Field(None, description="ID opcional do gerente para identificação direta")

    @property
    def senha_efetiva(self) -> str:
        s = self.senhaGerente or self.senha or ""
        return s.strip()

    @property
    def motivo_efetivo(self) -> str:
        return (self.motivo or self.justificativa or "").strip()


class DescontoRemoverRequest(BaseModel):
    senhaGerente: str | None = Field(None, description="Senha do gerente para autorizar remoção")
    senha: str | None = Field(None, description="Alias para senhaGerente")
    motivo: str | None = Field(None, description="Motivo da remoção do desconto")
    emailGerente: str | None = Field(None, description="E-mail opcional do gerente")
    idGerente: uuid.UUID | None = Field(None, description="ID opcional do gerente")

    @property
    def senha_efetiva(self) -> str:
        s = self.senhaGerente or self.senha or ""
        return s.strip()


class LogDescontoResponseSchema(BaseModel):
    idLogDesconto: uuid.UUID
    idRestaurante: uuid.UUID
    idPedido: uuid.UUID | None = None
    idUsuario: uuid.UUID | None = None
    usuario: str
    funcaoUsuario: str | None = None
    valorDesconto: float
    tipoDesconto: str | None = None
    motivo: str | None = None
    sucesso: bool
    motivoFalha: str | None = None
    dataHora: datetime

    model_config = ConfigDict(from_attributes=True)
