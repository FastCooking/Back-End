"""Cria índices estratégicos de performance para RNF03, RNF04 e RNF08.

Revision ID: 005_indices_performance_rnf08
Revises: 004_entregas_concorrencia
Create Date: 2026-11-11 10:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_indices_performance_rnf08"
down_revision: str | Sequence[str] | None = "004_entregas_concorrencia"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. ItemPedido: índices para KDS, entregas e filtros de comanda
    op.create_index(
        "ix_item_pedido_kds",
        "ItemPedido",
        ["idPedido", "status", "liberadoParaPreparo"],
        unique=False,
    )
    op.create_index(
        "ix_item_pedido_status",
        "ItemPedido",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_item_pedido_delivery",
        "ItemPedido",
        ["deliveryStatus", "claimedByWaiterId"],
        unique=False,
    )
    op.create_index(
        "ix_item_pedido_data_criacao",
        "ItemPedido",
        ["dataCriacao"],
        unique=False,
    )
    op.create_index(
        "ix_item_pedido_cardapio",
        "ItemPedido",
        ["idCardapio"],
        unique=False,
    )

    # 2. Pedido: índices para consultas ativas, por mesa e histórico
    op.create_index(
        "ix_pedido_restaurante_status",
        "Pedido",
        ["idRestaurante", "status"],
        unique=False,
    )
    op.create_index(
        "ix_pedido_mesa_status",
        "Pedido",
        ["idMesa", "status"],
        unique=False,
    )
    op.create_index(
        "ix_pedido_data_abertura",
        "Pedido",
        ["dataAbertura"],
        unique=False,
    )

    # 3. Mesa: índice para listagem por status no restaurante
    op.create_index(
        "ix_mesa_restaurante_status",
        "Mesa",
        ["idRestaurante", "status"],
        unique=False,
    )

    # 4. Cardapio: índice para listagem pública e filtros por categoria
    op.create_index(
        "ix_cardapio_rest_status_cat",
        "Cardapio",
        ["idRestaurante", "status", "categoria"],
        unique=False,
    )

    # 5. Pagamento: índice para busca por pedido
    op.create_index(
        "ix_pagamento_pedido",
        "Pagamento",
        ["idPedido"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pagamento_pedido", table_name="Pagamento")
    op.drop_index("ix_cardapio_rest_status_cat", table_name="Cardapio")
    op.drop_index("ix_mesa_restaurante_status", table_name="Mesa")
    op.drop_index("ix_pedido_data_abertura", table_name="Pedido")
    op.drop_index("ix_pedido_mesa_status", table_name="Pedido")
    op.drop_index("ix_pedido_restaurante_status", table_name="Pedido")
    op.drop_index("ix_item_pedido_cardapio", table_name="ItemPedido")
    op.drop_index("ix_item_pedido_data_criacao", table_name="ItemPedido")
    op.drop_index("ix_item_pedido_delivery", table_name="ItemPedido")
    op.drop_index("ix_item_pedido_status", table_name="ItemPedido")
    op.drop_index("ix_item_pedido_kds", table_name="ItemPedido")
