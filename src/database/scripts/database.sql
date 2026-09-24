-- =====================================================================
-- Script DDL: Sistema de Pedidos de Restaurante (FASTCOOKING)
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS "Restaurante" (
    "idRestaurante" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "nome" VARCHAR(255) NOT NULL,
    "cnpj" VARCHAR(18) NOT NULL UNIQUE,
    "telefone" VARCHAR(15) NOT NULL,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "cep" VARCHAR(9) NOT NULL,
    "status" BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS "Usuarios" (
    "idUsuario" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "idRestaurante" UUID NOT NULL REFERENCES "Restaurante"("idRestaurante") ON UPDATE CASCADE ON DELETE CASCADE,
    "nome" VARCHAR(255) NOT NULL,
    "cpf" VARCHAR(14) NOT NULL UNIQUE,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "senha" VARCHAR(255) NOT NULL,
    "funcao" VARCHAR(50) NOT NULL CHECK ("funcao" IN ('Garcom', 'Cozinheiro', 'Gerente', 'Adm')),
    "status" BOOLEAN NOT NULL DEFAULT TRUE,
    "tentativasFalhas" INT NOT NULL DEFAULT 0,
    "bloqueadoAte" TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS "Mesa" (
    "idMesa" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "idRestaurante" UUID NOT NULL REFERENCES "Restaurante"("idRestaurante") ON UPDATE CASCADE ON DELETE CASCADE,
    "numero" INT NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'Disponivel' CHECK ("status" IN ('Disponivel', 'Indisponivel')),
    CONSTRAINT uq_restaurante_mesa UNIQUE ("idRestaurante", "numero")
);

CREATE TABLE IF NOT EXISTS "Cardapio" (
    "idCardapio" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "idRestaurante" UUID NOT NULL REFERENCES "Restaurante"("idRestaurante") ON UPDATE CASCADE ON DELETE CASCADE,
    "nome" VARCHAR(150) NOT NULL,
    "pathImage" TEXT,
    "descricao" TEXT,
    "preco" NUMERIC(10, 2) NOT NULL CHECK ("preco" >= 0),
    "categoria" VARCHAR(100) NOT NULL,
    "status" BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS "Estoque" (
    "idEstoque" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "idRestaurante" UUID NOT NULL REFERENCES "Restaurante"("idRestaurante") ON UPDATE CASCADE ON DELETE CASCADE,
    "nome" VARCHAR(150) NOT NULL,
    "pathImage" VARCHAR(150) NULL,
    "unidadeMedida" VARCHAR(20) NOT NULL,
    "quantidadeEstoque" NUMERIC(10, 3) NOT NULL DEFAULT 0.000,
    "quantidadeMinima" NUMERIC(10, 3) NOT NULL DEFAULT 0.000
);

CREATE TABLE IF NOT EXISTS "FichaTecnica" (
    "idFichaTecnica" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "idCardapio" UUID NOT NULL REFERENCES "Cardapio"("idCardapio") ON UPDATE CASCADE ON DELETE CASCADE,
    "idEstoque" UUID NOT NULL REFERENCES "Estoque"("idEstoque") ON UPDATE CASCADE ON DELETE RESTRICT,
    "quantidadeNecessaria" NUMERIC(10, 3) NOT NULL CHECK ("quantidadeNecessaria" > 0),
    CONSTRAINT uq_ficha_cardapio_estoque UNIQUE ("idCardapio", "idEstoque")
);

CREATE TABLE IF NOT EXISTS "Pedido" (
    "idPedido" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "idRestaurante" UUID NOT NULL REFERENCES "Restaurante"("idRestaurante") ON UPDATE CASCADE ON DELETE CASCADE,
    "idMesa" UUID NOT NULL REFERENCES "Mesa"("idMesa") ON UPDATE CASCADE ON DELETE RESTRICT,
    "idGarcom" UUID NULL REFERENCES "Usuarios"("idUsuario") ON UPDATE CASCADE ON DELETE SET NULL,
    "status" VARCHAR(30) NOT NULL DEFAULT 'Aberto' CHECK ("status" IN ('Aberto', 'Em preparo', 'Pronto', 'Entregue', 'Fechado', 'Cancelado')),
    "dataAbertura" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "dataFechamento" TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS "ItemPedido" (
    "idItemPedido" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "idPedido" UUID NOT NULL REFERENCES "Pedido"("idPedido") ON UPDATE CASCADE ON DELETE CASCADE,
    "idCardapio" UUID NOT NULL REFERENCES "Cardapio"("idCardapio") ON UPDATE CASCADE ON DELETE RESTRICT,
    "quantidade" INT NOT NULL CHECK ("quantidade" > 0),
    "precoUnitario" NUMERIC(10, 2) NOT NULL CHECK ("precoUnitario" >= 0),
    "status" VARCHAR(30) NOT NULL DEFAULT 'Pendente' CHECK ("status" IN ('Pendente', 'Em preparo', 'Pronto', 'Entregue', 'Cancelado')),
    "observacao" TEXT
);

CREATE TABLE IF NOT EXISTS "Pagamento" (
    "idPagamento" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "idPedido" UUID NOT NULL REFERENCES "Pedido"("idPedido") ON UPDATE CASCADE ON DELETE RESTRICT,
    "formaPagamento" VARCHAR(30) NOT NULL CHECK ("formaPagamento" IN ('Dinheiro', 'Credito', 'Debito', 'PIX')),
    "valor" NUMERIC(10, 2) NOT NULL CHECK ("valor" > 0),
    "dataPagamento" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- Índices para Performance de Consultas Frequentes
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_Pedido_Mesa ON "Pedido"("idMesa");
CREATE INDEX IF NOT EXISTS idx_Pedido_Garcom ON "Pedido"("idGarcom");
CREATE INDEX IF NOT EXISTS idx_Pedido_Status ON "Pedido"("status");

CREATE INDEX IF NOT EXISTS idx_ItemPedido_Pedido ON "ItemPedido"("idPedido");
CREATE INDEX IF NOT EXISTS idx_ItemPedido_Cardapio ON "ItemPedido"("idCardapio");
CREATE INDEX IF NOT EXISTS idx_ItemPedido_Status ON "ItemPedido"("status");

CREATE INDEX IF NOT EXISTS idx_FichaTecnica_Cardapio ON "FichaTecnica"("idCardapio");
CREATE INDEX IF NOT EXISTS idx_FichaTecnica_Estoque ON "FichaTecnica"("idEstoque");

CREATE INDEX IF NOT EXISTS idx_Pagamento_Pedido ON "Pagamento"("idPedido");
