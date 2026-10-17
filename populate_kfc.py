import uuid
from datetime import datetime

import bcrypt

from src.database.connection import SessionLocal
from src.models.Cardapio import Cardapio
from src.models.Estoque import Estoque
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Sessao import Sessao
from src.models.Usuario import Usuario


def hash_senha(senha: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha.encode("utf-8"), salt).decode("utf-8")

ID_RESTAURANTE = "3aac2dbe-b7d5-4e94-b8c3-a1aa5a02a76d"

def popular_kfc():
    db = SessionLocal()
    try:
        print(f"=== Populando Restaurante KFC Osasco ({ID_RESTAURANTE}) ===")
        
        # 1. Verificar Restaurante
        rest = db.query(Restaurante).filter_by(idRestaurante=ID_RESTAURANTE).first()
        if not rest:
            print("Criando Restaurante KFC Osasco...")
            rest = Restaurante(
                idRestaurante=uuid.UUID(ID_RESTAURANTE),
                nome="KFC Osasco",
                cnpj="00.111.222/0001-33",
                telefone="(11) 3681-9988",
                email="osasco@kfc.com.br",
                cep="06010-000",
                status=True
            )
            db.add(rest)
            db.commit()
            db.refresh(rest)
        else:
            print(f"Restaurante encontrado: {rest.nome}")

        # 2. Usuários / Funcionários
        senha_padrao = hash_senha("123456")
        
        funcionarios_dados = [
            ("Carlos Silva", "123.456.789-00", "carlos@kfc.com.br", "Gerente"),
            ("Lucas Oliveira", "234.567.890-11", "lucas.garcom@kfc.com.br", "Garcom"),
            ("Mariana Costa", "345.678.901-22", "mariana.garcom@kfc.com.br", "Garcom"),
            ("Roberto Lima", "456.789.012-33", "roberto.cozinha@kfc.com.br", "Cozinheiro"),
            ("Fernanda Souza", "567.890.123-44", "fernanda.cozinha@kfc.com.br", "Cozinheiro"),
        ]

        for nome, cpf, email, funcao in funcionarios_dados:
            user = db.query(Usuario).filter_by(email=email).first()
            if not user:
                user = Usuario(
                    idRestaurante=uuid.UUID(ID_RESTAURANTE),
                    nome=nome,
                    cpf=cpf,
                    email=email,
                    senha=senha_padrao,
                    funcao=funcao,
                    status=True,
                )
                db.add(user)
                print(f"  + Usuário criado: {nome} ({funcao}) - Senha: 123456")
            else:
                user.senha = senha_padrao
                user.status = True
                user.idRestaurante = uuid.UUID(ID_RESTAURANTE)
                print(f"  ~ Usuário atualizado: {nome} ({funcao}) - Senha: 123456")

        db.commit()

        # 3. Mesas
        mesas_dados = [
            (1, "Disponivel"),
            (2, "Disponivel"),
            (3, "Ocupada"),
            (4, "Disponivel"),
            (5, "Reservada"),
            (6, "Disponivel"),
            (7, "Disponivel"),
            (8, "Disponivel"),
        ]

        mapa_mesas = {}
        for num, st in mesas_dados:
            mesa = db.query(Mesa).filter_by(idRestaurante=ID_RESTAURANTE, numero=num).first()
            if not mesa:
                mesa = Mesa(
                    idRestaurante=uuid.UUID(ID_RESTAURANTE),
                    numero=num,
                    status=st
                )
                db.add(mesa)
                db.commit()
                db.refresh(mesa)
                print(f"  + Mesa #{num} criada (Status: {st})")
            else:
                mesa.status = st
                db.commit()
                print(f"  ~ Mesa #{num} atualizada (Status: {st})")
            mapa_mesas[num] = mesa

        # 4. Estoque
        estoque_dados = [
            ("Frango em Pedaços Fresco", "KG", 55.0, 15.0),
            ("Farinha Especial para Empanar", "KG", 32.0, 10.0),
            ("Mix Secreto 11 Ervas e Especiarias", "KG", 14.5, 3.0),
            ("Óleo Vegetal Especial para Fritura", "L", 80.0, 20.0),
            ("Batata Palito Rústica Congelada", "KG", 42.0, 12.0),
            ("Pão de Brioche para Burger", "UN", 90.0, 25.0),
            ("Queijo Cheddar Cremoso Fatiado", "KG", 4.5, 8.0), # Estoque baixo proposital para alerta
            ("Maionese Especial do Coronel", "L", 18.0, 5.0),
            ("Molho Barbecue Defumado", "L", 12.0, 4.0),
            ("Alface Americana Selecionada", "KG", 9.0, 3.0),
            ("Refrigerante Coca-Cola 350ml Lata", "UN", 120.0, 30.0),
            ("Refrigerante Guaraná Antarctica 350ml", "UN", 95.0, 25.0),
            ("Balde Térmico KFC Grande", "UN", 140.0, 40.0),
        ]

        for nome, un, qtd, qtd_min in estoque_dados:
            item_est = db.query(Estoque).filter_by(idRestaurante=ID_RESTAURANTE, nome=nome).first()
            if not item_est:
                item_est = Estoque(
                    idRestaurante=uuid.UUID(ID_RESTAURANTE),
                    nome=nome,
                    unidadeMedida=un,
                    quantidadeEstoque=qtd,
                    quantidadeMinima=qtd_min
                )
                db.add(item_est)
                print(f"  + Estoque criado: {nome} ({qtd} {un})")
            else:
                item_est.quantidadeEstoque = qtd
                item_est.quantidadeMinima = qtd_min
                print(f"  ~ Estoque atualizado: {nome} ({qtd} {un})")

        db.commit()

        # 5. Cardápio
        cardapio_dados = [
            (
                "Balde Variedade (8 Pedaços + 6 Tiras Crocantes)",
                "Combos",
                69.90,
                "Nosso clássico balde recheado com 8 deliciosos pedaços de frango e 6 tiras crocantes empanadas na receita secreta do Coronel.",
                "https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Balde Só Tiras (10 Tiras Crocantes)",
                "Combos",
                54.90,
                "10 tiras de filé de peito de frango super crocantes, acompanhadas de molho barbecue à sua escolha.",
                "https://images.unsplash.com/photo-1562967914-608f82629710?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Sanduíche Coronel Burger",
                "Lanches",
                29.90,
                "Pão brioche quentinho, filé de sobrecoxa crocante, queijo cheddar derretido, alface fresca e maionese secreta.",
                "https://images.unsplash.com/photo-1553979459-d2229ba7433b?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Sanduíche Double Crunch Bacon",
                "Lanches",
                36.90,
                "Dois filés de frango ultra crocantes, dobro de queijo cheddar fatiado, bacon crocante e molho barbecue.",
                "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Popcorn Chicken Família",
                "Acompanhamentos",
                32.00,
                "Pedaços de frango empanados em formato de pipoca, super sequinhos e temperados na medida certa.",
                "https://images.unsplash.com/photo-1569058242253-92a9c755a0ec?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Batata Suprema com Cheddar e Bacon",
                "Acompanhamentos",
                24.50,
                "Porção generosa de batatas fritas crocantes cobertas com queijo cheddar cremoso aquecido e farofa de bacon.",
                "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Coca-Cola 350ml Lata",
                "Bebidas",
                7.50,
                "Refrigerante Coca-Cola 350ml servido trincando de gelado com opção de limão e gelo.",
                "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Guaraná Antarctica 350ml",
                "Bebidas",
                7.50,
                "Lata 350ml gelada.",
                "https://images.unsplash.com/photo-1610440042657-612c34d95e9f?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Suco Natural de Laranja 500ml",
                "Bebidas",
                11.00,
                "Suco 100% natural espremido na hora.",
                "https://images.unsplash.com/photo-1613478223719-2ab802602423?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Minibolo de Chocolate com Calda Quente",
                "Sobremesas",
                16.00,
                "Bolo quente com recheio cremoso e cobertura de calda de chocolate belga.",
                "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?auto=format&fit=crop&w=800&q=80"
            ),
            (
                "Sundae Doce de Leite com Farofa Crocante",
                "Sobremesas",
                13.90,
                "Sorvete cremoso de baunilha com generosa calda de doce de leite artesanal e farofa crocante de amendoim.",
                "https://images.unsplash.com/photo-1572490122747-3968b75cc699?auto=format&fit=crop&w=800&q=80"
            ),
        ]

        mapa_cardapio = {}
        for nome, cat, preco, desc, img in cardapio_dados:
            item_c = db.query(Cardapio).filter_by(idRestaurante=ID_RESTAURANTE, nome=nome).first()
            if not item_c:
                item_c = Cardapio(
                    idRestaurante=uuid.UUID(ID_RESTAURANTE),
                    nome=nome,
                    categoria=cat,
                    preco=preco,
                    descricao=desc,
                    pathImage=img,
                    status=True
                )
                db.add(item_c)
                db.commit()
                db.refresh(item_c)
                print(f"  + Cardápio criado: {nome} (R$ {preco:.2f})")
            else:
                item_c.preco = preco
                item_c.categoria = cat
                item_c.descricao = desc
                item_c.pathImage = img
                item_c.status = True
                db.commit()
                print(f"  ~ Cardápio atualizado: {nome} (R$ {preco:.2f})")
            mapa_cardapio[nome] = item_c

        # 6. Sessão e Pedido Ativo na Mesa 3 (Ocupada) para validação de KDS, Garçom e Autoatendimento
        mesa3 = mapa_mesas.get(3)
        garcom_lucas = db.query(Usuario).filter_by(email="lucas.garcom@kfc.com.br").first()

        # Cria Sessão ativa
        sessao_ativa = db.query(Sessao).filter_by(idMesa=mesa3.idMesa, status="Aberta").first()
        if not sessao_ativa:
            sessao_ativa = Sessao(
                idMesa=mesa3.idMesa,
                status="Aberta"
            )
            db.add(sessao_ativa)
            db.commit()
            db.refresh(sessao_ativa)

        # Verifica se já há pedido aberto na mesa 3
        pedido_ativo = db.query(Pedido).filter_by(idMesa=mesa3.idMesa, status="Aberto").first()
        if not pedido_ativo:
            pedido_ativo = Pedido(
                idRestaurante=uuid.UUID(ID_RESTAURANTE),
                idMesa=mesa3.idMesa,
                idGarcom=garcom_lucas.idUsuario if garcom_lucas else None,
                sessao_id=str(sessao_ativa.idSessao),
                status="Aberto",
                dataAbertura=datetime.now()
            )
            db.add(pedido_ativo)
            db.commit()
            db.refresh(pedido_ativo)
            print(f"  + Pedido ativo criado para a Mesa 3: {pedido_ativo.idPedido}")

            # Itens do pedido com status variados para testar telas de Cozinha (KDS), Garçom e Tracking
            burger = mapa_cardapio.get("Sanduíche Coronel Burger")
            batata = mapa_cardapio.get("Batata Suprema com Cheddar e Bacon")
            coca = mapa_cardapio.get("Coca-Cola 350ml Lata")
            sobremesa = mapa_cardapio.get("Minibolo de Chocolate com Calda Quente")

            itens_para_adicionar = [
                (burger, 1, "Sem: Alface. Obs: carne bem passada", "EmPreparo", 2),
                (batata, 1, "Com bastante bacon", "Pronto", 1),
                (coca, 2, "Gelo e limão", "Entregue", 1),
                (sobremesa, 1, "Liberar após o prato principal", "Pendente", 3),
            ]

            for item_card, qtd, obs, st_item, prioridade in itens_para_adicionar:
                if item_card:
                    item_ped = ItemPedido(
                        idPedido=pedido_ativo.idPedido,
                        idCardapio=item_card.idCardapio,
                        quantidade=qtd,
                        precoUnitario=item_card.preco,
                        status=st_item,
                        observacao=obs,
                        categoria=item_card.categoria,
                        prioridade=prioridade
                    )
                    db.add(item_ped)
            db.commit()
            print("  + Itens adicionados à comanda da Mesa 3 com sucesso!")

        print("\n=== População de KFC Osasco concluída com sucesso! ===")
        print(f"ID Restaurante: {ID_RESTAURANTE}")
        print("Login Gerente: carlos@kfc.com.br / Senha: 123456")
        print("Login Garçom: lucas.garcom@kfc.com.br / Senha: 123456")
        print("Login Cozinha: roberto.cozinha@kfc.com.br / Senha: 123456")
        print(f"Mesa 3 ID: {mesa3.idMesa} (comanda ativa com itens no KDS/Garçom)")

    except Exception as e:
        db.rollback()
        print(f"ERRO ao popular banco: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    popular_kfc()
