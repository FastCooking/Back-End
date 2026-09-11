-- =====================================================================
-- Script DML: Carga Inicial de Dados (FASTCOOKING)
-- =====================================================================

INSERT INTO "Restaurante" (nome, cpnj, telefone, email, cep, status) VALUES
('FastCooking Matriz', '12.345.678/0001-90', '(11) 98765-4321', 'contato@matriz.fastcooking.com', '01310-100', TRUE),
('FastCooking Filial Jardins', '98.765.432/0001-10', '(11) 91234-5678', 'contato@jardins.fastcooking.com', '01415-000', TRUE);

INSERT INTO "Usuario" (idRestaurante, nome, cpf, email, senha, funcao, status) VALUES
(1, 'Carlos Gerente', '111.111.111-11', 'carlos.gerente@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Gerente', TRUE),
(1, 'Mariana Silva', '222.222.222-22', 'mariana.gerente@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Gerente', TRUE),
(1, 'Joao Garcom', '333.333.333-33', 'joao.garcom@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Garcom', TRUE),
(1, 'Ana Paula', '444.444.444-44', 'ana.garcom@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Garcom', TRUE),
(1, 'Lucas Mendes', '555.555.555-55', 'lucas.garcom@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Garcom', TRUE),
(1, 'Beatriz Costa', '666.666.666-66', 'beatriz.garcom@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Garcom', TRUE),
(1, 'Chef Rodrigo', '777.777.777-77', 'rodrigo.cozinha@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Cozinheiro', TRUE),
(1, 'Amanda Chef', '888.888.888-88', 'amanda.cozinha@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Cozinheiro', TRUE),
(1, 'Fernando Cozinheiro', '999.999.999-99', 'fernando.cozinha@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Cozinheiro', TRUE),
(1, 'Juliana Cozinheira', '000.000.000-00', 'juliana.cozinha@fastcooking.com', '$2b$12$e8p4hE9T5aC9aF0tHw2rSe7fG3hK1lM2nO3pQ4rS5tU6vW7xY8z0a', 'Cozinheiro', TRUE);

INSERT INTO "Mesa" (idRestaurante, numero, status) VALUES
(1, 1, 'Disponivel'),
(1, 2, 'Disponivel'),
(1, 3, 'Disponivel'),
(1, 4, 'Disponivel'),
(1, 5, 'Disponivel'),
(1, 6, 'Disponivel'),
(1, 7, 'Disponivel'),
(1, 8, 'Disponivel'),
(1, 9, 'Indisponivel'),
(1, 10, 'Disponivel');

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

INSERT INTO "Cardapio" (idRestaurante, nome, pathImage, descricao, preco, categoria, status) VALUES
(1, 'Pizza Calabresa', '/images/cardapio/pizza-calabresa.png', 'Molho de tomate, mucarela, calabresa e cebola', 49.90, 'Pizzas', TRUE),
(1, 'Pizza Mucarela', '/images/cardapio/pizza-mucarela.png', 'Molho de tomate, dobro de mucarela e oregano', 45.90, 'Pizzas', TRUE),
(1, 'Burguer Bacon Classico', '/images/cardapio/burguer-bacon.png', 'Pao brioche, hamburguer 180g, queijo e bacon crocante', 34.90, 'Hamburgueres', TRUE),
(1, 'Burguer Simples', '/images/cardapio/burguer-simples.png', 'Pao brioche, hamburguer 180g e queijo mucarela', 28.90, 'Hamburgueres', TRUE),
(1, 'Porcao Batata Frita', '/images/cardapio/batata-frita.png', 'Batatas fritas crocantes com sal e tempero especial', 24.90, 'Porcoes', TRUE),
(1, 'Porcao Batata com Bacon', '/images/cardapio/batata-bacon.png', 'Batatas fritas cobertas com queijo e bacon', 32.90, 'Porcoes', TRUE),
(1, 'Refrigerante Coca-Cola 350ml', '/images/cardapio/coca-cola.png', 'Lata gelada 350ml', 6.50, 'Bebidas', TRUE),
(1, 'Refrigerante Guarana 350ml', '/images/cardapio/guarana.png', 'Lata gelada 350ml', 6.50, 'Bebidas', TRUE),
(1, 'Suco de Laranja 500ml', '/images/cardapio/suco-laranja.png', 'Suco natural feito na hora', 9.90, 'Bebidas', TRUE),
(1, 'Agua Mineral 500ml', '/images/cardapio/agua-mineral.png', 'Garrafa com ou sem gas', 4.50, 'Bebidas', TRUE);

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

INSERT INTO "ItemPedido" (idPedido, idCardapio, quantidade, precoUnitario, status, observacao) VALUES
(1, 1, 1, 49.90, 'Em preparo', 'Sem cebola'),
(1, 7, 2, 6.50, 'Entregue', 'Com gelo e limao'),
(2, 3, 2, 34.90, 'Em preparo', 'Ponto da carne: bem passado'),
(2, 5, 1, 24.90, 'Pronto', 'Molho a parte'),
(3, 2, 1, 45.90, 'Pronto', NULL),
(3, 9, 1, 9.90, 'Entregue', 'Sem acucar'),
(4, 4, 1, 28.90, 'Entregue', NULL),
(4, 8, 1, 6.50, 'Entregue', 'Gelada'),
(5, 1, 2, 49.90, 'Entregue', NULL),
(5, 7, 2, 6.50, 'Entregue', NULL);

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