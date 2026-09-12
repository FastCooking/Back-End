"""normalize column casing

Revision ID: 002_normalize_column_casing
Revises: 001_initial_schema
Create Date: 2026-09-10 22:24:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002_normalize_column_casing'
down_revision: str | Sequence[str] | None = '001_initial_schema'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Garante casing camelCase oficial das colunas no PostgreSQL
    op.execute("""
        DO $$
        BEGIN
            -- Restaurante
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Restaurante' AND column_name='idrestaurante') THEN
                ALTER TABLE "Restaurante" RENAME COLUMN "idrestaurante" TO "idRestaurante";
            END IF;

            -- Usuarios
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Usuarios' AND column_name='idusuario') THEN
                ALTER TABLE "Usuarios" RENAME COLUMN "idusuario" TO "idUsuario";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Usuarios' AND column_name='idrestaurante') THEN
                ALTER TABLE "Usuarios" RENAME COLUMN "idrestaurante" TO "idRestaurante";
            END IF;

            -- Mesa
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Mesa' AND column_name='idmesa') THEN
                ALTER TABLE "Mesa" RENAME COLUMN "idmesa" TO "idMesa";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Mesa' AND column_name='idrestaurante') THEN
                ALTER TABLE "Mesa" RENAME COLUMN "idrestaurante" TO "idRestaurante";
            END IF;

            -- Cardapio
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Cardapio' AND column_name='idcardapio') THEN
                ALTER TABLE "Cardapio" RENAME COLUMN "idcardapio" TO "idCardapio";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Cardapio' AND column_name='idrestaurante') THEN
                ALTER TABLE "Cardapio" RENAME COLUMN "idrestaurante" TO "idRestaurante";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Cardapio' AND column_name='pathimage') THEN
                ALTER TABLE "Cardapio" RENAME COLUMN "pathimage" TO "pathImage";
            END IF;

            -- Estoque
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Estoque' AND column_name='idestoque') THEN
                ALTER TABLE "Estoque" RENAME COLUMN "idestoque" TO "idEstoque";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Estoque' AND column_name='idrestaurante') THEN
                ALTER TABLE "Estoque" RENAME COLUMN "idrestaurante" TO "idRestaurante";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Estoque' AND column_name='pathimage') THEN
                ALTER TABLE "Estoque" RENAME COLUMN "pathimage" TO "pathImage";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Estoque' AND column_name='unidademedida') THEN
                ALTER TABLE "Estoque" RENAME COLUMN "unidademedida" TO "unidadeMedida";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Estoque' AND column_name='quantidadeestoque') THEN
                ALTER TABLE "Estoque" RENAME COLUMN "quantidadeestoque" TO "quantidadeEstoque";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Estoque' AND column_name='quantidademinima') THEN
                ALTER TABLE "Estoque" RENAME COLUMN "quantidademinima" TO "quantidadeMinima";
            END IF;

            -- FichaTecnica
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='FichaTecnica' AND column_name='idfichatecnica') THEN
                ALTER TABLE "FichaTecnica" RENAME COLUMN "idfichatecnica" TO "idFichaTecnica";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='FichaTecnica' AND column_name='idcardapio') THEN
                ALTER TABLE "FichaTecnica" RENAME COLUMN "idcardapio" TO "idCardapio";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='FichaTecnica' AND column_name='idestoque') THEN
                ALTER TABLE "FichaTecnica" RENAME COLUMN "idestoque" TO "idEstoque";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='FichaTecnica' AND column_name='quantidadenecessaria') THEN
                ALTER TABLE "FichaTecnica" RENAME COLUMN "quantidadenecessaria" TO "quantidadeNecessaria";
            END IF;

            -- Pedido
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pedido' AND column_name='idpedido') THEN
                ALTER TABLE "Pedido" RENAME COLUMN "idpedido" TO "idPedido";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pedido' AND column_name='idrestaurante') THEN
                ALTER TABLE "Pedido" RENAME COLUMN "idrestaurante" TO "idRestaurante";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pedido' AND column_name='idmesa') THEN
                ALTER TABLE "Pedido" RENAME COLUMN "idmesa" TO "idMesa";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pedido' AND column_name='idgarcom') THEN
                ALTER TABLE "Pedido" RENAME COLUMN "idgarcom" TO "idGarcom";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pedido' AND column_name='dataabertura') THEN
                ALTER TABLE "Pedido" RENAME COLUMN "dataabertura" TO "dataAbertura";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pedido' AND column_name='datafechamento') THEN
                ALTER TABLE "Pedido" RENAME COLUMN "datafechamento" TO "dataFechamento";
            END IF;

            -- ItemPedido
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ItemPedido' AND column_name='iditempedido') THEN
                ALTER TABLE "ItemPedido" RENAME COLUMN "iditempedido" TO "idItemPedido";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ItemPedido' AND column_name='idpedido') THEN
                ALTER TABLE "ItemPedido" RENAME COLUMN "idpedido" TO "idPedido";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ItemPedido' AND column_name='idcardapio') THEN
                ALTER TABLE "ItemPedido" RENAME COLUMN "idcardapio" TO "idCardapio";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ItemPedido' AND column_name='precounitario') THEN
                ALTER TABLE "ItemPedido" RENAME COLUMN "precounitario" TO "precoUnitario";
            END IF;

            -- Pagamento
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pagamento' AND column_name='idpagamento') THEN
                ALTER TABLE "Pagamento" RENAME COLUMN "idpagamento" TO "idPagamento";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pagamento' AND column_name='idpedido') THEN
                ALTER TABLE "Pagamento" RENAME COLUMN "idpedido" TO "idPedido";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pagamento' AND column_name='formapagamento') THEN
                ALTER TABLE "Pagamento" RENAME COLUMN "formapagamento" TO "formaPagamento";
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='Pagamento' AND column_name='datapagamento') THEN
                ALTER TABLE "Pagamento" RENAME COLUMN "datapagamento" TO "dataPagamento";
            END IF;
        END $$;
    """)


def downgrade() -> None:
    pass
