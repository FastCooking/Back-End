-- =====================================================================
-- Script DDL: Sistema de Pedidos de Restaurante (FASTCOOKING)
-- =====================================================================

DROP DATABASE IF EXISTS "FASTCOOKING";
CREATE DATABASE "FASTCOOKING";

USE "FASTCOOKING";

CREATE TABLE "Restaurante" (
    idRestaurante SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    cpnj CHAR(18) NOT NULL UNIQUE,
    telefone VARCHAR(15) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    cep CHAR(9) NOT NULL,
    status BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE "Usuarios" (
    idFuncionario SERIAL PRIMARY KEY,
    idRestaurante INT NOT NULL REFERENCES "Restaurante"(idRestaurante) ON UPDATE CASCADE ON DELETE CASCADE,
    nome VARCHAR(255) NOT NULL,
    cpf CHAR(14) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    funcao VARCHAR(50) NOT NULL CHECK (funcao IN ('Garcom', 'Cozinheiro', 'Gerente', 'Adm'))
    status BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE "Mesa" (
    idMesa SERIAL PRIMARY KEY,
    idRestaurante INT NOT NULL REFERENCES "Restaurante"(idRestaurante) ON UPDATE CASCADE ON DELETE CASCADE,
    numero INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Disponivel' CHECK (status IN ('Disponivel', 'Indisponivel')),
    CONSTRAINT uq_restaurante_mesa UNIQUE (idRestaurante, numero)
);

CREATE TABLE "Pedido" (
    idPedido SERIAL PRIMARY KEY,
    idRestaurante INT NOT NULL REFERENCES "Restaurante"(idRestaurante) ON UPDATE CASCADE ON DELETE CASCADE,
    idMesa INT NOT NULL REFERENCES "Mesa"(idMesa) ON UPDATE CASCADE ON DELETE RESTRICT,
    idGarcom INT REFERENCES "Usuarios"(idFuncionario) ON UPDATE CASCADE ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Aberto' CHECK (status IN ('Aberto', 'Em preparo', 'Pronto', 'Entregue', 'Fechado', 'Cancelado')),
    dataAbertura TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dataFechamento TIMESTAMP
);

CREATE TABLE "Cardapio" (
    idCardapio SERIAL PRIMARY KEY,
    idRestaurante INT NOT NULL REFERENCES "Restaurante"(idRestaurante) ON UPDATE CASCADE ON DELETE CASCADE,
    nome VARCHAR(150) NOT NULL,
    pathImage TEXT NOT NULL,
    descricao TEXT,
    preco NUMERIC(10, 2) NOT NULL CHECK (preco >= 0),
    categoria VARCHAR(100) NOT NULL,
    status BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE "Estoque" (
    idEstoque SERIAL PRIMARY KEY,
    idRestaurante INT NOT NULL REFERENCES "Restaurante"(idRestaurante) ON UPDATE CASCADE ON DELETE CASCADE,
    nome VARCHAR(150) NOT NULL,
    quantidadeEstoque NUMERIC(10, 3) NOT NULL DEFAULT 0.000,
    unidadeMedida VARCHAR(20) NOT NULL,
    quantidadeMinima NUMERIC(10, 3) NOT NULL DEFAULT 0.000
);

CREATE TABLE "FichaTecnica" (
    idFichaTecnica SERIAL PRIMARY KEY,
    idCardapio INT NOT NULL REFERENCES "Cardapio"(idCardapio) ON UPDATE CASCADE ON DELETE CASCADE,
    idEstoque INT NOT NULL REFERENCES "Estoque"(idEstoque) ON UPDATE CASCADE ON DELETE RESTRICT,
    quantidadeNecessaria NUMERIC(10, 3) NOT NULL CHECK (quantidadeNecessaria > 0),
    CONSTRAINT uq_ficha_cardapio_estoque UNIQUE (idCardapio, idEstoque)
);

CREATE TABLE "ItemPedido" (
    idItemPedido SERIAL PRIMARY KEY,
    idPedido INT NOT NULL REFERENCES "Pedido"(idPedido) ON UPDATE CASCADE ON DELETE CASCADE,
    idCardapio INT NOT NULL REFERENCES "Cardapio"(idCardapio) ON UPDATE CASCADE ON DELETE RESTRICT,
    quantidade INT NOT NULL CHECK (quantidade > 0),
    precoUnitario NUMERIC(10, 2) NOT NULL CHECK (precoUnitario >= 0),
    status VARCHAR(30) NOT NULL DEFAULT 'Pendente' CHECK (status IN ('Pendente', 'Em preparo', 'Pronto', 'Entregue', 'Cancelado')),
    observacao TEXT
);

CREATE TABLE "Pagamento" (
    idPagamento SERIAL PRIMARY KEY,
    idPedido INT NOT NULL REFERENCES "Pedido"(idPedido) ON UPDATE CASCADE ON DELETE RESTRICT,
    formaPagamento VARCHAR(30) NOT NULL CHECK (formaPagamento IN ('Dinheiro', 'Credito', 'Debito', 'PIX')),
    valor NUMERIC(10, 2) NOT NULL CHECK (valor > 0),
    dataPagamento TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- Índices para Performance de Consultas Frequentes
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_Pedido_Mesa ON "Pedido"(idMesa);
CREATE INDEX IF NOT EXISTS idx_Pedido_Garcom ON "Pedido"(idGarcom);
CREATE INDEX IF NOT EXISTS idx_Pedido_Status ON "Pedido"(status);

CREATE INDEX IF NOT EXISTS idx_ItemPedido_Pedido ON "ItemPedido"(idPedido);
CREATE INDEX IF NOT EXISTS idx_ItemPedido_Cardapio ON "ItemPedido"(idCardapio);
CREATE INDEX IF NOT EXISTS idx_ItemPedido_Status ON "ItemPedido"(status);

CREATE INDEX IF NOT EXISTS idx_FichaTecnica_Cardapio ON "FichaTecnica"(idCardapio);
CREATE INDEX IF NOT EXISTS idx_FichaTecnica_Estoque ON "FichaTecnica"(idEstoque);

CREATE INDEX IF NOT EXISTS idx_Pagamento_Pedido ON "Pagamento"(idPedido);
