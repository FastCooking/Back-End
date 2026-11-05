"""
Script de demonstracao interativa da aplicacao de desconto.
Executa o fluxo completo e imprime os resultados na tela de forma visual.

Para rodar:
    python demo_desconto.py
"""

import sys

# Garante suporte a UTF-8 no terminal Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.app import app
from src.core.security import criar_token
from src.database.connection import Base, get_db
from src.models.Cardapio import Cardapio
from src.models.ItemPedido import ItemPedido
from src.models.Mesa import Mesa
from src.models.Pedido import Pedido
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha


@event.listens_for(Base.metadata, "before_create")
def _strip_server_defaults_for_sqlite(target, connection, **kw):
    if connection.dialect.name == "sqlite":
        for table in target.tables.values():
            for col in table.columns:
                if col.server_default is not None:
                    col.server_default = None


def main():
    print("=" * 70)
    print(" FASTCOOKING - DEMONSTRACAO DO ENDPOINT DE DESCONTO")
    print("=" * 70)

    # 1. Configura banco em memoria
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # 2. Cria dados de exemplo
    rest = Restaurante.create(
        db,
        nome="KFC Demonstracao",
        cnpj="00.111.222/0001-33",
        telefone="(11) 98888-0000",
        email="kfc@demo.com",
        cep="01001-000",
        status=True,
    )

    gerente = Usuario.create(
        db,
        idRestaurante=rest.idRestaurante,
        nome="Carlos Silva (Gerente Geral)",
        cpf="111.222.333-00",
        email="carlos.gerente@kfc.com",
        senha=hash_senha("senhaSecretaDoGerente"),
        funcao="Gerente",
    )

    garcom = Usuario.create(
        db,
        idRestaurante=rest.idRestaurante,
        nome="Lucas Oliveira (Garcom)",
        cpf="444.555.666-00",
        email="lucas.garcom@kfc.com",
        senha=hash_senha("senha123"),
        funcao="Garcom",
    )

    mesa = Mesa.create(db, idRestaurante=rest.idRestaurante, numero=15, status="Ocupada")

    prato1 = Cardapio.create(db, idRestaurante=rest.idRestaurante, nome="Balde Familia", preco=75.0, categoria="Prato Principal")
    prato2 = Cardapio.create(db, idRestaurante=rest.idRestaurante, nome="Batata Grande", preco=25.0, categoria="Acompanhamento")

    pedido = Pedido.create(
        db,
        idRestaurante=rest.idRestaurante,
        idMesa=mesa.idMesa,
        idGarcom=garcom.idUsuario,
        status="Aberto",
    )

    item1 = ItemPedido.create(db, idPedido=pedido.idPedido, idCardapio=prato1.idCardapio, quantidade=1, precoUnitario=75.0, status="Entregue")
    item2 = ItemPedido.create(db, idPedido=pedido.idPedido, idCardapio=prato2.idCardapio, quantidade=1, precoUnitario=25.0, status="Entregue")

    token_garcom = criar_token(garcom.idUsuario, "Garcom", rest.idRestaurante)
    headers = {"Authorization": f"Bearer {token_garcom}"}

    # 3. Consulta valor inicial
    print("\n[1] CONSULTA INICIAL DA CONTA (MESA 15)")
    resp_inicial = client.get(f"/pedidos/{pedido.idPedido}")
    dados_inicial = resp_inicial.json()
    print(f"    Subtotal dos Itens: R$ {dados_inicial['subtotal']:.2f}")
    print(f"    Desconto Atual:     R$ {dados_inicial['desconto']:.2f}")
    print(f"    Total a Pagar:      R$ {dados_inicial['total']:.2f}")

    # 4. Tentativa com senha errada
    print("\n[2] TENTATIVA COM SENHA INVALIDA DO GERENTE")
    resp_errada = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={"senhaGerente": "senhaErrada999", "tipo": "valor", "valor": 20.0, "motivo": "Tentativa indevida"},
        headers=headers,
    )
    print(f"    Status HTTP:     {resp_errada.status_code} Unauthorized")
    print(f"    Resposta da API: {resp_errada.json()['detail']}")

    # 5. Aplicacao bem-sucedida do desconto
    print("\n[3] APLICACAO DE DESCONTO COM A SENHA CORRETA")
    resp_sucesso = client.post(
        f"/pedidos/{pedido.idPedido}/desconto",
        json={
            "senhaGerente": "senhaSecretaDoGerente",
            "tipo": "valor",
            "valor": 30.0,
            "motivo": "Cortesia da casa - Demora no pedido",
        },
        headers=headers,
    )
    dados_sucesso = resp_sucesso.json()
    print(f"    Status HTTP: {resp_sucesso.status_code} OK")
    print(f"    Mensagem:    {dados_sucesso['message']}")
    print(f"    Gerente:     {dados_sucesso['desconto']['gerente']}")
    print(f"    Motivo:      {dados_sucesso['desconto']['motivo']}")
    print(f"    Desconto:    R$ {dados_sucesso['pedido']['desconto']:.2f}")
    print(f"    Novo Total:  R$ {dados_sucesso['pedido']['total']:.2f}")

    # 6. Verificacao do log gravado
    print("\n[4] LOG AUDITAVEL REGISTRADO NO BANCO DE DADOS")
    resp_logs = client.get(f"/pedidos/{pedido.idPedido}/desconto/logs", headers=headers)
    logs = resp_logs.json()
    for i, l in enumerate(logs, start=1):
        status_log = "APROVADO" if l["sucesso"] else "REJEITADO (TENTATIVA FALHA)"
        print(f"    [{i}] Status: {status_log}")
        print(f"        Usuario: {l['usuario']}")
        print(f"        Valor:   R$ {l['valorDesconto']:.2f}")
        print(f"        Horario: {l['dataHora']}")
        if not l["sucesso"]:
            print(f"        Falha:   {l['motivoFalha']}")

    # 7. Simula pagamento do total com desconto
    print("\n[5] FECHAMENTO DA CONTA COM O TOTAL REFLETINDO O DESCONTO")
    # Garçom registra pagamento do total líquido (R$ 70,00)
    resp_pag = client.post(
        f"/pedidos/{pedido.idPedido}/pagamento",
        json={"formaPagamento": "Cartao de Credito", "valor": 70.0},
        headers=headers,
    )
    dados_pag = resp_pag.json()
    print(f"    Total Pedido (com desconto): R$ {dados_pag['totalPedido']:.2f}")
    print(f"    Total Pago pelo Cliente:     R$ {dados_pag['totalPago']:.2f}")
    print(f"    Saldo Restante:              R$ {dados_pag['saldoRestante']:.2f}")
    print(f"    Status da Comanda:           {dados_pag['pedido']['status']}")
    print(f"    Pedido Encerrado:            {dados_pag['pedidoEncerrado']}")

    print("\n" + "=" * 70)
    print(" DEMONSTRACAO CONCLUIDA COM SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    main()
