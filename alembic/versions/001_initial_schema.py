"""initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-28 12:29:39.851748

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Restaurante
    op.create_table(
        'Restaurante',
        sa.Column('idRestaurante', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nome', sa.String(length=255), nullable=False),
        sa.Column('cnpj', sa.String(length=18), nullable=False),
        sa.Column('telefone', sa.String(length=15), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('cep', sa.String(length=9), nullable=False),
        sa.Column('status', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.PrimaryKeyConstraint('idRestaurante'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('cnpj')
    )

    # 2. Usuarios
    op.create_table(
        'Usuarios',
        sa.Column('idUsuario', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('idRestaurante', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=255), nullable=False),
        sa.Column('cpf', sa.String(length=14), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('senha', sa.String(length=255), nullable=False),
        sa.Column('funcao', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.ForeignKeyConstraint(['idRestaurante'], ['Restaurante.idRestaurante'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('idUsuario'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('cpf')
    )

    # 3. Mesa
    op.create_table(
        'Mesa',
        sa.Column('idMesa', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('idRestaurante', sa.Integer(), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='Disponivel'),
        sa.ForeignKeyConstraint(['idRestaurante'], ['Restaurante.idRestaurante'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('idMesa'),
        sa.UniqueConstraint('idRestaurante', 'numero', name='uq_restaurante_mesa')
    )

    # 4. Cardapio
    op.create_table(
        'Cardapio',
        sa.Column('idCardapio', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('idRestaurante', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=150), nullable=False),
        sa.Column('pathImage', sa.Text(), nullable=True),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('preco', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('categoria', sa.String(length=100), nullable=False),
        sa.Column('status', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.ForeignKeyConstraint(['idRestaurante'], ['Restaurante.idRestaurante'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('idCardapio')
    )

    # 5. Estoque
    op.create_table(
        'Estoque',
        sa.Column('idEstoque', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('idRestaurante', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=150), nullable=False),
        sa.Column('pathImage', sa.String(length=150), nullable=True),
        sa.Column('unidadeMedida', sa.String(length=20), nullable=False),
        sa.Column('quantidadeEstoque', sa.Numeric(precision=10, scale=3), nullable=False, server_default='0.000'),
        sa.Column('quantidadeMinima', sa.Numeric(precision=10, scale=3), nullable=False, server_default='0.000'),
        sa.ForeignKeyConstraint(['idRestaurante'], ['Restaurante.idRestaurante'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('idEstoque')
    )

    # 6. FichaTecnica
    op.create_table(
        'FichaTecnica',
        sa.Column('idFichaTecnica', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('idCardapio', sa.Integer(), nullable=False),
        sa.Column('idEstoque', sa.Integer(), nullable=False),
        sa.Column('quantidadeNecessaria', sa.Numeric(precision=10, scale=3), nullable=False),
        sa.ForeignKeyConstraint(['idCardapio'], ['Cardapio.idCardapio'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['idEstoque'], ['Estoque.idEstoque'], onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('idFichaTecnica'),
        sa.UniqueConstraint('idCardapio', 'idEstoque', name='uq_ficha_cardapio_estoque')
    )

    # 7. Pedido
    op.create_table(
        'Pedido',
        sa.Column('idPedido', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('idRestaurante', sa.Integer(), nullable=False),
        sa.Column('idMesa', sa.Integer(), nullable=False),
        sa.Column('idGarcom', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='Aberto'),
        sa.Column('dataAbertura', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('dataFechamento', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['idGarcom'], ['Usuarios.idUsuario'], onupdate='CASCADE', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['idMesa'], ['Mesa.idMesa'], onupdate='CASCADE', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['idRestaurante'], ['Restaurante.idRestaurante'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('idPedido')
    )

    # 8. ItemPedido
    op.create_table(
        'ItemPedido',
        sa.Column('idItemPedido', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('idPedido', sa.Integer(), nullable=False),
        sa.Column('idCardapio', sa.Integer(), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('precoUnitario', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='Pendente'),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['idCardapio'], ['Cardapio.idCardapio'], onupdate='CASCADE', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['idPedido'], ['Pedido.idPedido'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('idItemPedido')
    )

    # 9. Pagamento
    op.create_table(
        'Pagamento',
        sa.Column('idPagamento', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('idPedido', sa.Integer(), nullable=False),
        sa.Column('formaPagamento', sa.String(length=30), nullable=False),
        sa.Column('valor', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('dataPagamento', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['idPedido'], ['Pedido.idPedido'], onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('idPagamento')
    )


def downgrade() -> None:
    op.drop_table('Pagamento')
    op.drop_table('ItemPedido')
    op.drop_table('Pedido')
    op.drop_table('FichaTecnica')
    op.drop_table('Estoque')
    op.drop_table('Cardapio')
    op.drop_table('Mesa')
    op.drop_table('Usuarios')
    op.drop_table('Restaurante')
