-- =====================================================================
-- Script DML: Carga Inicial de Dados
-- =====================================================================

INSERT INTO "Restaurante" (nome) VALUES
('FastCooking Matriz'),
('FastCooking Filial Jardins');

INSERT INTO "Usuarios" (idRestaurante, nome, email, senha, funcao) VALUES
(1, 'Carlos Gerente', 'carlos.gerente@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Gerente'),
(1, 'Mariana Silva', 'mariana.gerente@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Gerente'),
(1, 'Joao Garcom', 'joao.garcom@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Garcom'),
(1, 'Ana Paula', 'ana.garcom@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Garcom'),
(1, 'Lucas Mendes', 'lucas.garcom@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Garcom'),
(1, 'Beatriz Costa', 'beatriz.garcom@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Garcom'),
(1, 'Chef Rodrigo', 'rodrigo.cozinha@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Cozinheiro'),
(1, 'Amanda Chef', 'amanda.cozinha@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Cozinheiro'),
(1, 'Fernando Cozinheiro', 'fernando.cozinha@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Cozinheiro'),
(1, 'Juliana Cozinheira', 'juliana.cozinha@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Cozinheiro');

INSERT INTO "Mesa" (idRestaurante, numero, capacidade, status) VALUES
(1, 1, 2, 'ocupada'),
(1, 2, 2, 'ocupada'),
(1, 3, 4, 'ocupada'),
(1, 4, 4, 'livre'),
(1, 5, 4, 'livre'),
(1, 6, 6, 'livre'),
(1, 7, 6, 'livre'),
(1, 8, 8, 'livre'),
(1, 9, 2, 'livre'),
(1, 10, 4, 'livre');

INSERT INTO "Estoque" (idRestaurante, nome, quantidadeEstoque, unidadeMedida, quantidadeMinima) VALUES
(1, 'Massa de Pizza', 50.000, 'UN', 10.000),
(1, 'Molho de Tomate', 30.500, 'KG', 5.000),
(1, 'Queijo Mucarela', 45.000, 'KG', 8.000),
(1, 'Calabresa Fatiada', 25.000, 'KG', 4.000),
(1, 'Hamburguer Bovina 180g', 80.000, 'UN', 15.000),
(1, 'Pao de Brioche', 100.000, 'UN', 20.000),
(1, 'Bacon Fatiado', 18.000, 'KG', 3.000),
(1, 'Batata Congelada', 60.000, 'KG', 10.000),
(1, 'Refrigerante Lata 350ml', 120.000, 'UN', 24.000),
(1, 'Suco de Laranja Natural', 40.000, 'L', 8.000);

INSERT INTO "Cardapio" (idRestaurante, nome, descricao, preco, categoria, ativo) VALUES
(1, 'Pizza Calabresa', 'Molho de tomate, mucarela, calabresa e cebola', 49.90, 'Pizzas', TRUE),
(1, 'Pizza Mucarela', 'Molho de tomate, dobro de mucarela e oregano', 45.90, 'Pizzas', TRUE),
(1, 'Burguer Bacon Classico', 'Pao brioche, hamburguer 180g, queijo e bacon crocante', 34.90, 'Hamburgueres', TRUE),
(1, 'Burguer Simples', 'Pao brioche, hamburguer 180g e queijo mucarela', 28.90, 'Hamburgueres', TRUE),
(1, 'Porcao Batata Frita', 'Batatas fritas crocantes com sal e tempero especial', 24.90, 'Porcoes', TRUE),
(1, 'Porcao Batata com Bacon', 'Batatas fritas cobertas com queijo e bacon', 32.90, 'Porcoes', TRUE),
(1, 'Refrigerante Coca-Cola 350ml', 'Lata gelada 350ml', 6.50, 'Bebidas', TRUE),
(1, 'Refrigerante Guarana 350ml', 'Lata gelada 350ml', 6.50, 'Bebidas', TRUE),
(1, 'Suco de Laranja 500ml', 'Suco natural feito na hora', 9.90, 'Bebidas', TRUE),
(1, 'Agua Mineral 500ml', 'Garrafa com ou sem gas', 4.50, 'Bebidas', TRUE);

INSERT INTO "FichaTecnica" (idCardapio, idEstoque, quantidadeNecessaria) VALUES
(1, 1, 1.000),   -- Pizza Calabresa: 1x Massa
(1, 2, 0.150),   -- Pizza Calabresa: 150g Molho
(1, 3, 0.250),   -- Pizza Calabresa: 250g Mucarela
(1, 4, 0.200),   -- Pizza Calabresa: 200g Calabresa
(2, 1, 1.000),   -- Pizza Mucarela: 1x Massa
(2, 2, 0.150),   -- Pizza Mucarela: 150g Molho
(2, 3, 0.400),   -- Pizza Mucarela: 400g Mucarela
(3, 5, 1.000),   -- Burguer Bacon: 1x Carne
(3, 6, 1.000),   -- Burguer Bacon: 1x Pao
(3, 7, 0.080);   -- Burguer Bacon: 80g Bacon

INSERT INTO "Pedido" (idRestaurante, idMesa, idGarcom, status, dataAbertura, dataFechamento) VALUES
(1, 1, 3, 'Aberto', CURRENT_TIMESTAMP - INTERVAL '40 minutes', NULL),
(1, 2, 4, 'Em preparo', CURRENT_TIMESTAMP - INTERVAL '35 minutes', NULL),
(1, 3, 5, 'Pronto', CURRENT_TIMESTAMP - INTERVAL '30 minutes', NULL),
(1, 4, 6, 'Entregue', CURRENT_TIMESTAMP - INTERVAL '25 minutes', NULL),
(1, 5, 3, 'Fechado', CURRENT_TIMESTAMP - INTERVAL '3 hours', CURRENT_TIMESTAMP - INTERVAL '2 hours'),
(1, 6, 4, 'Fechado', CURRENT_TIMESTAMP - INTERVAL '4 hours', CURRENT_TIMESTAMP - INTERVAL '3 hours'),
(1, 7, 5, 'Fechado', CURRENT_TIMESTAMP - INTERVAL '5 hours', CURRENT_TIMESTAMP - INTERVAL '4 hours'),
(1, 8, 6, 'Fechado', CURRENT_TIMESTAMP - INTERVAL '6 hours', CURRENT_TIMESTAMP - INTERVAL '5 hours'),
(1, 9, 3, 'Fechado', CURRENT_TIMESTAMP - INTERVAL '7 hours', CURRENT_TIMESTAMP - INTERVAL '6 hours'),
(1, 10, 4, 'Fechado', CURRENT_TIMESTAMP - INTERVAL '8 hours', CURRENT_TIMESTAMP - INTERVAL '7 hours');

INSERT INTO "ItemPedido" (idPedido, idCardapio, idCozinheiro, quantidade, precoUnitario, status, observacao) VALUES
(1, 1, 7, 1, 49.90, 'Em preparo', 'Sem cebola'),
(1, 7, NULL, 2, 6.50, 'Entregue', 'Com gelo e limao'),
(2, 3, 8, 2, 34.90, 'Em preparo', 'Ponto da carne: bem passado'),
(2, 5, 9, 1, 24.90, 'Pronto', 'Molho a parte'),
(3, 2, 7, 1, 45.90, 'Pronto', NULL),
(3, 9, NULL, 1, 9.90, 'Entregue', 'Sem acucar'),
(4, 4, 10, 1, 28.90, 'Entregue', NULL),
(4, 8, NULL, 1, 6.50, 'Entregue', 'Gelada'),
(5, 1, 7, 2, 49.90, 'Entregue', NULL),
(5, 7, NULL, 2, 6.50, 'Entregue', NULL);

INSERT INTO "Pagamento" (idPedido, formaPagamento, valor, dataPagamento) VALUES
(5, 'PIX', 99.80, CURRENT_TIMESTAMP - INTERVAL '2 hours'),
(5, 'Credito', 13.00, CURRENT_TIMESTAMP - INTERVAL '2 hours'),
(6, 'Credito', 69.80, CURRENT_TIMESTAMP - INTERVAL '3 hours'),
(7, 'Debito', 45.90, CURRENT_TIMESTAMP - INTERVAL '4 hours'),
(8, 'Dinheiro', 34.90, CURRENT_TIMESTAMP - INTERVAL '5 hours'),
(9, 'PIX', 28.90, CURRENT_TIMESTAMP - INTERVAL '6 hours'),
(10, 'Credito', 56.70, CURRENT_TIMESTAMP - INTERVAL '7 hours'),
(5, 'PIX', 10.00, CURRENT_TIMESTAMP - INTERVAL '2 hours'),
(6, 'Debito', 15.00, CURRENT_TIMESTAMP - INTERVAL '3 hours'),
(7, 'Dinheiro', 20.00, CURRENT_TIMESTAMP - INTERVAL '4 hours');