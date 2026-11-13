import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from src.core.audit_logger import (
    formatar_linha_auditoria,
    limpar_logs_antigos,
    log_abertura_mesa,
    log_cancelamento_assistido,
    log_cancelamento_cliente,
    log_desconto,
    log_edicao_mesa,
    log_exclusao_mesa,
    log_login,
    obter_caminho_arquivo_auditoria,
    registrar_auditoria,
    sanitizar_lgpd,
)


@pytest.fixture
def temp_log_dir(tmp_path: Path):
    """Cria um diretório temporário para testes de logs de auditoria."""
    log_dir = tmp_path / "test_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    yield log_dir
    if log_dir.exists():
        shutil.rmtree(log_dir, ignore_errors=True)


def test_sanitizar_lgpd():
    # UUID deve permanecer intacto
    uid = str(uuid4())
    assert sanitizar_lgpd(uid) == uid

    # E-mail deve ser mascarado
    assert sanitizar_lgpd("admin@fastcooking.com") == "a***n@fastcooking.com"
    assert sanitizar_lgpd("garcom1@empresa.com.br") == "g***1@empresa.com.br"

    # Senha ou campos sensíveis são ocultados
    assert sanitizar_lgpd("senhaSuperSecreta123") == "[DADO_SENSIVEL_OMITIDO]"
    assert sanitizar_lgpd("Bearer eyJhbGciOi...") == "[DADO_SENSIVEL_OMITIDO]"

    # Vazio / None
    assert sanitizar_lgpd(None) == "N/A"
    assert sanitizar_lgpd("") == "N/A"


def test_obter_caminho_arquivo_auditoria(temp_log_dir: Path):
    data_teste = datetime(2026, 11, 13, 14, 30, tzinfo=UTC)
    caminho = obter_caminho_arquivo_auditoria(data=data_teste, base_dir=temp_log_dir)

    esperado = temp_log_dir / "2026" / "11" / "13" / "auditoria.log"
    assert caminho == esperado
    assert caminho.parent.exists()


def test_formatar_e_registrar_auditoria(temp_log_dir: Path):
    linha = registrar_auditoria(
        acao="TESTE_ACAO",
        ator="EQUIPE(idUsuario=123)",
        recurso="Mesa(1)",
        detalhes={"campo": "antigo -> novo"},
        base_dir=temp_log_dir,
    )

    assert "[AUDITORIA]" in linha
    assert "ACAO=TESTE_ACAO" in linha
    assert "ATOR=EQUIPE(idUsuario=123)" in linha
    assert "RECURSO=Mesa(1)" in linha
    assert "campo=antigo -> novo" in linha

    # Verifica gravação no arquivo
    caminho_hoje = obter_caminho_arquivo_auditoria(base_dir=temp_log_dir)
    assert caminho_hoje.exists()
    conteudo = caminho_hoje.read_text(encoding="utf-8")
    assert linha in conteudo


def test_log_cancelamento_assistido(temp_log_dir: Path):
    id_user = uuid4()
    id_item = uuid4()
    id_ped = uuid4()
    id_mesa = uuid4()

    linha = log_cancelamento_assistido(
        id_usuario=id_user,
        funcao_usuario="Garcom",
        id_pedido=id_ped,
        id_mesa=id_mesa,
        id_item_pedido=id_item,
        motivo="Cliente desistiu do prato",
        base_dir=temp_log_dir,
    )

    assert "ACAO=CANCELAMENTO_ASSISTIDO" in linha
    assert f"idUsuario={id_user}" in linha
    assert "funcao=Garcom" in linha
    assert f"ItemPedido({id_item})" in linha
    assert "Cliente desistiu do prato" in linha


def test_log_cancelamento_cliente(temp_log_dir: Path):
    id_item = uuid4()
    id_ped = uuid4()
    id_mesa = uuid4()

    linha = log_cancelamento_cliente(
        sessao_id="sessao-qrcode-mesa-5",
        id_mesa=id_mesa,
        id_pedido=id_ped,
        id_item_pedido=id_item,
        base_dir=temp_log_dir,
    )

    assert "ACAO=CANCELAMENTO_CLIENTE" in linha
    assert "CLIENTE(sessao_id=sessao-qrcode-mesa-5" in linha
    assert f"idMesa={id_mesa}" in linha
    assert "tipoCancelamento=AUTOATENDIMENTO_CLIENTE" in linha


def test_log_edicao_e_exclusao_mesa(temp_log_dir: Path):
    id_user = uuid4()
    id_mesa = uuid4()

    linha_edicao = log_edicao_mesa(
        id_usuario=id_user,
        funcao_usuario="Gerente",
        id_mesa=id_mesa,
        dados_anteriores={"numero": 5, "status": "Disponivel"},
        dados_novos={"numero": 5, "status": "Ocupada"},
        base_dir=temp_log_dir,
    )
    assert "ACAO=EDICAO_MESA" in linha_edicao
    assert "Mesa(" in linha_edicao
    assert "status': 'Ocupada'" in linha_edicao

    linha_exclusao = log_exclusao_mesa(
        id_usuario=id_user,
        funcao_usuario="Adm",
        id_mesa=id_mesa,
        numero_mesa=10,
        base_dir=temp_log_dir,
    )
    assert "ACAO=EXCLUSAO_MESA" in linha_exclusao
    assert "numero=10" in linha_exclusao


def test_log_desconto(temp_log_dir: Path):
    id_user = uuid4()
    id_ped = uuid4()
    id_rest = uuid4()

    linha = log_desconto(
        id_usuario=id_user,
        funcao_usuario="Gerente",
        id_pedido=id_ped,
        id_restaurante=id_rest,
        valor_desconto=15.50,
        motivo="Cortesia de aniversário",
        sucesso=True,
        base_dir=temp_log_dir,
    )

    assert "ACAO=DESCONTO_COMANDA" in linha
    assert "valorDesconto=R$15.50" in linha
    assert "Cortesia de aniversário" in linha
    assert "status=CONCEDIDO" in linha


def test_log_login(temp_log_dir: Path):
    id_user = uuid4()
    # Login sucesso
    linha_sucesso = log_login(
        sucesso=True,
        identificador_usuario="gerente@fastcooking.com",
        ip_origem="192.168.1.100",
        id_usuario=id_user,
        funcao="Gerente",
        base_dir=temp_log_dir,
    )
    assert "ACAO=LOGIN_SUCESSO" in linha_sucesso
    assert "g***e@fastcooking.com" in linha_sucesso
    assert f"idUsuario={id_user}" in linha_sucesso

    # Login falha
    linha_falha = log_login(
        sucesso=False,
        identificador_usuario="usuario.inv@teste.com",
        ip_origem="200.100.50.25",
        detalhe_erro="Credenciais inválidas",
        base_dir=temp_log_dir,
    )
    assert "ACAO=LOGIN_FALHA" in linha_falha
    assert "status=FALHA" in linha_falha
    assert "motivoFalha=Credenciais inválidas" in linha_falha


def test_limpeza_logs_90_dias(temp_log_dir: Path):
    hoje = datetime.now(UTC)

    # 1. Cria log recente (de 10 dias atrás) -> DEVE FICAR
    data_recente = hoje - timedelta(days=10)
    arq_recente = obter_caminho_arquivo_auditoria(data=data_recente, base_dir=temp_log_dir)
    arq_recente.write_text("log recente", encoding="utf-8")

    # 2. Cria log de 91 dias atrás -> DEVE SER REMOVIDO
    data_antiga_91 = hoje - timedelta(days=91)
    arq_antigo_91 = obter_caminho_arquivo_auditoria(data=data_antiga_91, base_dir=temp_log_dir)
    arq_antigo_91.write_text("log 91 dias", encoding="utf-8")

    # 3. Cria log de 150 dias atrás -> DEVE SER REMOVIDO
    data_antiga_150 = hoje - timedelta(days=150)
    arq_antigo_150 = obter_caminho_arquivo_auditoria(data=data_antiga_150, base_dir=temp_log_dir)
    arq_antigo_150.write_text("log 150 dias", encoding="utf-8")

    assert arq_recente.exists()
    assert arq_antigo_91.exists()
    assert arq_antigo_150.exists()

    resultado = limpar_logs_antigos(dias=90, base_dir=temp_log_dir)

    assert resultado["arquivos_removidos"] >= 2
    assert arq_recente.exists()
    assert not arq_antigo_91.exists()
    assert not arq_antigo_150.exists()
