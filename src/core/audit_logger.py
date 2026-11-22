import asyncio
import logging
import os
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

# Configuração do logger de console
logger = logging.getLogger("fastcooking.audit")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def obter_base_dir(base_dir: Path | str | None = None) -> Path:
    """Retorna o diretório base configurado ou dinamicamente via variáveis de ambiente."""
    if base_dir:
        return Path(base_dir)
    return Path(os.getenv("AUDIT_LOG_DIR", os.getenv("LOG_DIR", "/tmp/logs")))


def sanitizar_lgpd(valor: Any) -> str:
    """Sanitiza e mascara informações pessoais conforme diretrizes da LGPD."""
    if valor is None:
        return "N/A"

    texto = str(valor).strip()
    if not texto:
        return "N/A"

    # Se for UUID, mantém identificador íntegro
    try:
        UUID(texto)
        return texto
    except (ValueError, AttributeError):
        pass

    # Mascara e-mails (ex: joao.silva@empresa.com -> j***a@empresa.com)
    email_regex = r"^([a-zA-Z0-9_.+-])[^@]*([a-zA-Z0-9_.+-])@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)$"
    match_email = re.match(email_regex, texto)
    if match_email:
        p1, p2, dominio = match_email.groups()
        return f"{p1}***{p2}@{dominio}"

    # Remove senhas ou campos sensíveis se passados por engano
    if any(k in texto.lower() for k in ("password", "senha", "bearer ", "secret", "token")):
        return "[DADO_SENSIVEL_OMITIDO]"

    return texto


def obter_caminho_arquivo_auditoria(
    data: datetime | None = None, base_dir: Path | str | None = None
) -> Path:
    """Retorna o caminho do arquivo de auditoria organizado em YYYY/MM/dd/auditoria.log."""
    dt = data or datetime.now(UTC)
    base = obter_base_dir(base_dir)
    ano = dt.strftime("%Y")
    mes = dt.strftime("%m")
    dia = dt.strftime("%d")

    diretorio = base / ano / mes / dia
    diretorio.mkdir(parents=True, exist_ok=True)
    return diretorio / "auditoria.log"
    mes = dt.strftime("%m")
    dia = dt.strftime("%d")

    diretorio = base / ano / mes / dia
    diretorio.mkdir(parents=True, exist_ok=True)
    return diretorio / "auditoria.log"


def formatar_linha_auditoria(
    acao: str,
    ator: str,
    recurso: str,
    detalhes: dict[str, Any] | None = None,
    data_hora: datetime | None = None,
) -> str:
    """Monta a linha de log no formato:
    [AUDITORIA] YYYY-MM-DD HH:MM:SS | ACAO=... | ATOR=... | RECURSO=... | DETALHES=...
    """
    dt = data_hora or datetime.now(UTC)
    timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")

    detalhes_parts = []
    if detalhes:
        for k, v in detalhes.items():
            if v is not None:
                val_str = sanitizar_lgpd(v)
                detalhes_parts.append(f"{k}={val_str}")
    detalhes_str = ", ".join(detalhes_parts) if detalhes_parts else "Nenhum"

    return (
        f"[AUDITORIA] {timestamp_str} | "
        f"ACAO={acao.upper()} | "
        f"ATOR={ator} | "
        f"RECURSO={recurso} | "
        f"DETALHES={detalhes_str}"
    )


def registrar_auditoria(
    acao: str,
    ator: str,
    recurso: str,
    detalhes: dict[str, Any] | None = None,
    data_hora: datetime | None = None,
    base_dir: Path | str | None = None,
) -> str:
    """Grava o registro de auditoria no arquivo /tmp/logs/YYYY/MM/dd/auditoria.log

    e envia para o console (stdout) para exibição em tempo real.
    """
    dt = data_hora or datetime.now(UTC)
    linha = formatar_linha_auditoria(
        acao=acao,
        ator=ator,
        recurso=recurso,
        detalhes=detalhes,
        data_hora=dt,
    )

    # 1. Output em stdout para console Vercel / terminal
    logger.info(linha)

    # 2. Gravação em arquivo físico no caminho particionado
    try:
        arquivo_log = obter_caminho_arquivo_auditoria(dt, base_dir=base_dir)
        with open(arquivo_log, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception as exc:
        logger.error(f"[AUDITORIA_ERRO] Falha ao gravar log em arquivo: {exc}")

    return linha


# ==============================================================================
# Funções de Conveniência para Ações Sensíveis
# ==============================================================================


def log_cancelamento_assistido(
    id_usuario: Any,
    funcao_usuario: str | None,
    id_pedido: Any,
    id_mesa: Any,
    id_item_pedido: Any,
    motivo: str | None,
    base_dir: Path | str | None = None,
) -> str:
    """Auditoria para cancelamento de item assistido pela equipe (garçom, gerente, adm)."""
    ator = f"EQUIPE(idUsuario={sanitizar_lgpd(id_usuario)}, funcao={funcao_usuario or 'N/A'})"
    recurso = f"ItemPedido({sanitizar_lgpd(id_item_pedido)})"
    detalhes = {
        "idPedido": sanitizar_lgpd(id_pedido),
        "idMesa": sanitizar_lgpd(id_mesa),
        "motivo": sanitizar_lgpd(motivo) if motivo else "Não informado",
        "tipoCancelamento": "ASSISTIDO",
    }
    return registrar_auditoria(
        acao="CANCELAMENTO_ASSISTIDO",
        ator=ator,
        recurso=recurso,
        detalhes=detalhes,
        base_dir=base_dir,
    )


def log_cancelamento_cliente(
    sessao_id: str | None,
    id_mesa: Any,
    id_pedido: Any,
    id_item_pedido: Any,
    base_dir: Path | str | None = None,
) -> str:
    """Auditoria para cancelamento de item feito pelo próprio cliente na sessão/mesa."""
    ator = f"CLIENTE(sessao_id={sanitizar_lgpd(sessao_id)}, idMesa={sanitizar_lgpd(id_mesa)})"
    recurso = f"ItemPedido({sanitizar_lgpd(id_item_pedido)})"
    detalhes = {
        "idPedido": sanitizar_lgpd(id_pedido),
        "idMesa": sanitizar_lgpd(id_mesa),
        "sessao_id": sanitizar_lgpd(sessao_id),
        "tipoCancelamento": "AUTOATENDIMENTO_CLIENTE",
    }
    return registrar_auditoria(
        acao="CANCELAMENTO_CLIENTE",
        ator=ator,
        recurso=recurso,
        detalhes=detalhes,
        base_dir=base_dir,
    )


def log_edicao_mesa(
    id_usuario: Any,
    funcao_usuario: str | None,
    id_mesa: Any,
    dados_anteriores: dict[str, Any] | None = None,
    dados_novos: dict[str, Any] | None = None,
    base_dir: Path | str | None = None,
) -> str:
    """Auditoria para alteração cadastral ou de status de uma mesa."""
    ator = f"EQUIPE(idUsuario={sanitizar_lgpd(id_usuario)}, funcao={funcao_usuario or 'N/A'})"
    recurso = f"Mesa({sanitizar_lgpd(id_mesa)})"
    detalhes: dict[str, Any] = {}
    if dados_anteriores:
        detalhes["antes"] = str(dados_anteriores)
    if dados_novos:
        detalhes["depois"] = str(dados_novos)

    return registrar_auditoria(
        acao="EDICAO_MESA",
        ator=ator,
        recurso=recurso,
        detalhes=detalhes,
        base_dir=base_dir,
    )


def log_exclusao_mesa(
    id_usuario: Any,
    funcao_usuario: str | None,
    id_mesa: Any,
    numero_mesa: int | None = None,
    base_dir: Path | str | None = None,
) -> str:
    """Auditoria para exclusão de uma mesa."""
    ator = f"EQUIPE(idUsuario={sanitizar_lgpd(id_usuario)}, funcao={funcao_usuario or 'N/A'})"
    recurso = f"Mesa({sanitizar_lgpd(id_mesa)})"
    detalhes = {
        "numero": numero_mesa if numero_mesa is not None else "N/A",
        "acao": "EXCLUSAO",
    }
    return registrar_auditoria(
        acao="EXCLUSAO_MESA",
        ator=ator,
        recurso=recurso,
        detalhes=detalhes,
        base_dir=base_dir,
    )


def log_abertura_mesa(
    id_usuario: Any,
    funcao_usuario: str | None,
    id_mesa: Any,
    sessao_id: str | None = None,
    base_dir: Path | str | None = None,
) -> str:
    """Auditoria para abertura de atendimento em mesa."""
    ator = f"EQUIPE(idUsuario={sanitizar_lgpd(id_usuario)}, funcao={funcao_usuario or 'N/A'})"
    recurso = f"Mesa({sanitizar_lgpd(id_mesa)})"
    detalhes = {
        "sessao_id": sanitizar_lgpd(sessao_id),
        "acao": "ABERTURA_MESA",
    }
    return registrar_auditoria(
        acao="ABERTURA_MESA",
        ator=ator,
        recurso=recurso,
        detalhes=detalhes,
        base_dir=base_dir,
    )


def log_desconto(
    id_usuario: Any,
    funcao_usuario: str | None,
    id_pedido: Any,
    id_restaurante: Any,
    valor_desconto: float,
    tipo_desconto: str | None = None,
    motivo: str | None = None,
    sucesso: bool = True,
    base_dir: Path | str | None = None,
) -> str:
    """Auditoria para concessão ou tentativa de desconto em comanda/pedido."""
    ator = f"EQUIPE(idUsuario={sanitizar_lgpd(id_usuario)}, funcao={funcao_usuario or 'N/A'})"
    recurso = f"Pedido({sanitizar_lgpd(id_pedido)})"
    detalhes = {
        "idRestaurante": sanitizar_lgpd(id_restaurante),
        "valorDesconto": f"R${float(valor_desconto):.2f}",
        "tipoDesconto": tipo_desconto or "Valor",
        "motivo": sanitizar_lgpd(motivo) if motivo else "Não informado",
        "status": "CONCEDIDO" if sucesso else "NEGADO",
    }
    return registrar_auditoria(
        acao="DESCONTO_COMANDA",
        ator=ator,
        recurso=recurso,
        detalhes=detalhes,
        base_dir=base_dir,
    )


def log_login(
    sucesso: bool,
    identificador_usuario: str,
    ip_origem: str | None = None,
    id_usuario: Any = None,
    funcao: str | None = None,
    detalhe_erro: str | None = None,
    base_dir: Path | str | None = None,
) -> str:
    """Auditoria de eventos de login com proteção de dados LGPD."""
    ator = f"USUARIO({sanitizar_lgpd(identificador_usuario)})"
    recurso = "SessaoAutenticacao"
    detalhes = {
        "status": "SUCESSO" if sucesso else "FALHA",
        "ip": ip_origem or "desconhecido",
    }
    if id_usuario:
        detalhes["idUsuario"] = sanitizar_lgpd(id_usuario)
    if funcao:
        detalhes["funcao"] = funcao
    if detalhe_erro:
        detalhes["motivoFalha"] = sanitizar_lgpd(detalhe_erro)

    acao = "LOGIN_SUCESSO" if sucesso else "LOGIN_FALHA"
    return registrar_auditoria(
        acao=acao,
        ator=ator,
        recurso=recurso,
        detalhes=detalhes,
        base_dir=base_dir,
    )


# ==============================================================================
# Rotina de Limpeza de Logs Antigos (Retenção 90 dias)
# ==============================================================================


def limpar_logs_antigos(dias: int = 90, base_dir: Path | str | None = None) -> dict[str, int]:
    """Varre a estrutura de diretórios YYYY/MM/dd e remove logs com mais de `dias` dias.

    Remove também diretórios vazios resultantes da exclusão.
    """
    base = obter_base_dir(base_dir)
    if not base.exists():
        return {"arquivos_removidos": 0, "diretorios_removidos": 0}

    limite_data = datetime.now(UTC).date() - timedelta(days=dias)
    arquivos_removidos = 0
    diretorios_removidos = 0

    # Percorre YYYY / MM / dd
    for path_ano in sorted(base.glob("*")):
        if not path_ano.is_dir() or not path_ano.name.isdigit():
            continue
        ano_val = int(path_ano.name)

        for path_mes in sorted(path_ano.glob("*")):
            if not path_mes.is_dir() or not path_mes.name.isdigit():
                continue
            mes_val = int(path_mes.name)

            for path_dia in sorted(path_mes.glob("*")):
                if not path_dia.is_dir() or not path_dia.name.isdigit():
                    continue
                dia_val = int(path_dia.name)

                try:
                    data_pasta = datetime(ano_val, mes_val, dia_val, tzinfo=UTC).date()
                except ValueError:
                    continue

                if data_pasta < limite_data:
                    # Remove todos os arquivos do dia
                    for arq in path_dia.glob("*"):
                        if arq.is_file():
                            try:
                                arq.unlink()
                                arquivos_removidos += 1
                            except Exception as err:
                                logger.warning(f"[LIMPEZA_LOG] Erro ao remover {arq}: {err}")
                    # Remove o diretório do dia se vazio
                    try:
                        path_dia.rmdir()
                        diretorios_removidos += 1
                    except Exception:
                        pass

            # Remove mês se vazio
            if path_mes.is_dir() and not any(path_mes.iterdir()):
                try:
                    path_mes.rmdir()
                    diretorios_removidos += 1
                except Exception:
                    pass

        # Remove ano se vazio
        if path_ano.is_dir() and not any(path_ano.iterdir()):
            try:
                path_ano.rmdir()
                diretorios_removidos += 1
            except Exception:
                pass

    logger.info(
        f"[LIMPEZA_LOG] Concluída. {arquivos_removidos} arquivo(s) e "
        f"{diretorios_removidos} diretório(s) com mais de {dias} dias removidos."
    )
    return {
        "arquivos_removidos": arquivos_removidos,
        "diretorios_removidos": diretorios_removidos,
    }


async def rotina_diaria_limpeza_logs(intervalo_horas: int = 24, dias_retencao: int = 90):
    """Loop assíncrono para executar a limpeza a cada `intervalo_horas`."""
    while True:
        try:
            await asyncio.sleep(intervalo_horas * 3600)
            limpar_logs_antigos(dias=dias_retencao)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[LIMPEZA_LOG_ERRO] Falha no loop diário de limpeza: {e}")
