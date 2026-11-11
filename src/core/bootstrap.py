import logging
import os
import uuid

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.core.security import get_password_hash
from src.database.connection import SessionLocal
from src.models.Usuario import Usuario

load_dotenv()

logger = logging.getLogger(__name__)


def garantir_usuario_admin(db: Session | None = None) -> Usuario:
    """Garante a existência do usuário administrador padrão em ambiente de deploy.

    Garante a existência do usuário administrador padrão em ambiente de
    deploy.
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        email_admin = os.getenv("DEFAULT_ADMIN_EMAIL", "fastcooking@fastcooking.com.br")
        senha_admin = os.getenv("DEFAULT_ADMIN_PASSWORD", "f4stc0oking")

        admin_existente = (
            db.query(Usuario)
            .filter(Usuario.email == email_admin, Usuario.funcao == "Adm")
            .first()
        )

        if admin_existente:
            logger.info("Usuário administrador padrão já existe: %s", email_admin)
            return admin_existente

        admin_outro_cargo = (
            db.query(Usuario).filter(Usuario.email == email_admin).first()
        )
        if admin_outro_cargo:
            admin_outro_cargo.funcao = "Adm"
            admin_outro_cargo.senha = get_password_hash(senha_admin)
            admin_outro_cargo.status = True
            db.commit()
            db.refresh(admin_outro_cargo)
            logger.info(
                "Usuário existente promovido a administrador padrão: %s",
                email_admin,
            )
            return admin_outro_cargo

        novo_admin = Usuario(
            idUsuario=uuid.uuid4(),
            idRestaurante=None,
            nome="Administrador Padrão",
            cpf="00000000000",
            email=email_admin,
            senha=get_password_hash(senha_admin),
            funcao="Adm",
            status=True,
        )
        db.add(novo_admin)
        db.commit()
        db.refresh(novo_admin)
        logger.info(
            "Usuário administrador padrão criado com sucesso: %s", email_admin
        )
        return novo_admin

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error(
            "Erro ao inicializar usuário administrador padrão: %s", exc
        )
        raise exc
    finally:
        if close_session:
            db.close()


def executar_migracoes_seguras(db: Session | None = None) -> None:
    """Aplica migrações DDL seguras (colunas novas com IF NOT EXISTS) de forma idempotente."""
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        bind_engine = db.get_bind()
        if bind_engine.dialect.name in ("postgresql", "postgres"):
            db.execute(text("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables WHERE table_name = 'Pedido'
                    ) THEN
                        ALTER TABLE "Pedido" 
                        ADD COLUMN IF NOT EXISTS "idUsuarioFechamento" UUID 
                        REFERENCES "Usuarios"("idUsuario") 
                        ON UPDATE CASCADE ON DELETE SET NULL;
                    END IF;

                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables WHERE table_name = 'Cardapio'
                    ) THEN
                        ALTER TABLE "Cardapio" 
                        ADD COLUMN IF NOT EXISTS "tempoPreparo" INTEGER NOT NULL DEFAULT 15;
                    END IF;

                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables WHERE table_name = 'ItemPedido'
                    ) THEN
                        ALTER TABLE "ItemPedido"
                        ADD COLUMN IF NOT EXISTS "origem" VARCHAR(20) NOT NULL DEFAULT 'CLIENTE';
                    END IF;
                END $$;
            """))
            # Índices de performance para PostgreSQL
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_item_pedido_kds ON "ItemPedido" ("idPedido", "status", "liberadoParaPreparo");
                CREATE INDEX IF NOT EXISTS ix_item_pedido_status ON "ItemPedido" ("status");
                CREATE INDEX IF NOT EXISTS ix_item_pedido_delivery ON "ItemPedido" ("deliveryStatus", "claimedByWaiterId");
                CREATE INDEX IF NOT EXISTS ix_item_pedido_data_criacao ON "ItemPedido" ("dataCriacao");
                CREATE INDEX IF NOT EXISTS ix_item_pedido_cardapio ON "ItemPedido" ("idCardapio");
                CREATE INDEX IF NOT EXISTS ix_pedido_restaurante_status ON "Pedido" ("idRestaurante", "status");
                CREATE INDEX IF NOT EXISTS ix_pedido_mesa_status ON "Pedido" ("idMesa", "status");
                CREATE INDEX IF NOT EXISTS ix_pedido_data_abertura ON "Pedido" ("dataAbertura");
                CREATE INDEX IF NOT EXISTS ix_mesa_restaurante_status ON "Mesa" ("idRestaurante", "status");
                CREATE INDEX IF NOT EXISTS ix_cardapio_rest_status_cat ON "Cardapio" ("idRestaurante", "status", "categoria");
                CREATE INDEX IF NOT EXISTS ix_pagamento_pedido ON "Pagamento" ("idPedido");
            """))
            db.commit()
            logger.info("Migrações seguras executadas com sucesso.")
        elif bind_engine.dialect.name == "sqlite":
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_item_pedido_kds ON ItemPedido (idPedido, status, liberadoParaPreparo);
                CREATE INDEX IF NOT EXISTS ix_item_pedido_status ON ItemPedido (status);
                CREATE INDEX IF NOT EXISTS ix_item_pedido_delivery ON ItemPedido (deliveryStatus, claimedByWaiterId);
                CREATE INDEX IF NOT EXISTS ix_item_pedido_data_criacao ON ItemPedido (dataCriacao);
                CREATE INDEX IF NOT EXISTS ix_item_pedido_cardapio ON ItemPedido (idCardapio);
                CREATE INDEX IF NOT EXISTS ix_pedido_restaurante_status ON Pedido (idRestaurante, status);
                CREATE INDEX IF NOT EXISTS ix_pedido_mesa_status ON Pedido (idMesa, status);
                CREATE INDEX IF NOT EXISTS ix_pedido_data_abertura ON Pedido (dataAbertura);
                CREATE INDEX IF NOT EXISTS ix_mesa_restaurante_status ON Mesa (idRestaurante, status);
                CREATE INDEX IF NOT EXISTS ix_cardapio_rest_status_cat ON Cardapio (idRestaurante, status, categoria);
                CREATE INDEX IF NOT EXISTS ix_pagamento_pedido ON Pagamento (idPedido);
            """))
            db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Aviso durante migrações automáticas: %s", str(e))
    finally:
        if close_session:
            db.close()
