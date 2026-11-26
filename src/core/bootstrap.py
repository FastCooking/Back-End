import logging
import os

from sqlalchemy.orm import Session

from src.database.connection import SessionLocal
from src.models.Restaurante import Restaurante
from src.models.Usuario import Usuario
from src.services.UsuarioService import hash_senha

logger = logging.getLogger("fastcooking.bootstrap")


def garantir_usuario_admin(db: Session | None = None) -> Usuario | None:
    """
    Garante de forma idempotente que o usuário administrador exista no sistema após o deploy.
    As credenciais são obtidas exclusivamente por variáveis de ambiente:
      - DEFAULT_ADMIN_EMAIL (padrão: fastcooking@fastcooking.com.br)
      - DEFAULT_ADMIN_PASSWORD (padrão: f4stc0oking se informado em ambiente de desenvolvimento)
    Caso o usuário já exista com o e-mail informado, nenhuma modificação é feita.
    """
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "fastcooking@fastcooking.com.br").strip()
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD")

    if not admin_password:
        logger.info("DEFAULT_ADMIN_PASSWORD não configurada. Inicialização de admin ignorada.")
        return None

    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        usuario_existente = Usuario.get_by_email(db, admin_email)
        if usuario_existente:
            logger.info("Usuário administrador '%s' já existe. Nenhuma ação necessária.", admin_email)
            return usuario_existente

        # Garante um restaurante padrão para vínculo
        restaurante = db.query(Restaurante).first()
        if not restaurante:
            restaurante = Restaurante.create(
                db=db,
                nome="FastCooking Restaurante",
                cnpj="00.000.000/0001-91",
                telefone="(11) 99999-9999",
                email="contato@fastcooking.com.br",
                cep="01001-000",
                status=True,
                commit=True,
            )

        # Trata unicidade de CPF para o usuário administrador padrão
        cpf_padrao = "000.000.000-00"
        cpf_em_uso = Usuario.get_by_cpf(db, cpf_padrao)
        if cpf_em_uso:
            import time
            ts = int(time.time() * 1000) % 1000000000
            base_dig = f"{ts:09d}"
            soma1 = sum(int(base_dig[i]) * (10 - i) for i in range(9))
            d1 = 0 if (soma1 * 10) % 11 == 10 else (soma1 * 10) % 11
            soma2 = sum(int((base_dig + str(d1))[i]) * (11 - i) for i in range(10))
            d2 = 0 if (soma2 * 10) % 11 == 10 else (soma2 * 10) % 11
            cpf_padrao = f"{base_dig[:3]}.{base_dig[3:6]}.{base_dig[6:9]}-{d1}{d2}"

        senha_hash = hash_senha(admin_password)
        novo_admin = Usuario.create(
            db=db,
            idRestaurante=restaurante.idRestaurante,
            nome="Administrador FastCooking",
            cpf=cpf_padrao,
            email=admin_email,
            senha=senha_hash,
            funcao="Adm",
            commit=True,
        )
        logger.info("Usuário administrador '%s' criado com sucesso.", admin_email)

        # Garante também o usuário fastback
        if not Usuario.get_by_email(db, "fastback@fastcooking.com.br"):
            Usuario.create(
                db=db,
                idRestaurante=restaurante.idRestaurante,
                nome="FastBack Administrador",
                cpf="999.888.777-66",
                email="fastback@fastcooking.com.br",
                senha=senha_hash,
                funcao="Adm",
                commit=True,
            )
            logger.info("Usuário administrador 'fastback@fastcooking.com.br' criado com sucesso.")

        return novo_admin
    except Exception as e:
        db.rollback()
        logger.error("Erro durante o bootstrap do usuário administrador: %s", str(e))
        raise
    finally:
        if close_session:
            db.close()


def executar_migracoes_seguras(db: Session | None = None) -> None:
    """Aplica migrações DDL seguras apenas se as colunas/tabelas ainda não existirem, evitando locks exclusivos."""
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True
    try:
        from sqlalchemy import text
        bind_engine = db.get_bind()
        if bind_engine.dialect.name in ("postgresql", "postgres"):
            # Verifica primeiro apenas com SELECT (sem ACCESS EXCLUSIVE lock) se o schema já está atualizado
            ja_migrado = db.execute(
                text("""
                    SELECT (
                        EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'Pedido' AND column_name = 'desconto'
                        )
                        AND EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_name = 'LogDesconto'
                        )
                        AND EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_name = 'AuditoriaCancelamentoItem'
                        )
                        AND EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'Cardapio' AND column_name = 'tempoPreparo'
                        )
                        AND EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'ItemPedido' AND column_name = 'origem'
                        )
                    )
                """)
            ).scalar()
            db.commit()
            if ja_migrado:
                return

            db.execute(text("SET LOCAL lock_timeout = '3s';"))
            db.execute(text("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables WHERE table_name = 'Pedido'
                    ) THEN
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Pedido' AND column_name = 'idUsuarioFechamento') THEN
                            ALTER TABLE "Pedido" ADD COLUMN "idUsuarioFechamento" UUID REFERENCES "Usuarios"("idUsuario") ON UPDATE CASCADE ON DELETE SET NULL;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Pedido' AND column_name = 'desconto') THEN
                            ALTER TABLE "Pedido" ADD COLUMN "desconto" NUMERIC(10, 2) NOT NULL DEFAULT 0.0;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Pedido' AND column_name = 'tipoDesconto') THEN
                            ALTER TABLE "Pedido" ADD COLUMN "tipoDesconto" VARCHAR(20);
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Pedido' AND column_name = 'valorDescontoInformado') THEN
                            ALTER TABLE "Pedido" ADD COLUMN "valorDescontoInformado" NUMERIC(10, 2);
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Pedido' AND column_name = 'motivoDesconto') THEN
                            ALTER TABLE "Pedido" ADD COLUMN "motivoDesconto" VARCHAR(255);
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Pedido' AND column_name = 'idGerenteDesconto') THEN
                            ALTER TABLE "Pedido" ADD COLUMN "idGerenteDesconto" UUID REFERENCES "Usuarios"("idUsuario") ON UPDATE CASCADE ON DELETE SET NULL;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Pedido' AND column_name = 'dataDesconto') THEN
                            ALTER TABLE "Pedido" ADD COLUMN "dataDesconto" TIMESTAMP;
                        END IF;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.tables WHERE table_name = 'LogDesconto'
                    ) THEN
                        CREATE TABLE "LogDesconto" (
                            "idLogDesconto" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            "idRestaurante" UUID NOT NULL REFERENCES "Restaurante"("idRestaurante") ON UPDATE CASCADE ON DELETE CASCADE,
                            "idPedido" UUID REFERENCES "Pedido"("idPedido") ON UPDATE CASCADE ON DELETE CASCADE,
                            "idUsuario" UUID REFERENCES "Usuarios"("idUsuario") ON UPDATE CASCADE ON DELETE SET NULL,
                            "usuario" VARCHAR(255) NOT NULL,
                            "funcaoUsuario" VARCHAR(50),
                            "valorDesconto" NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
                            "tipoDesconto" VARCHAR(20),
                            "motivo" TEXT,
                            "sucesso" BOOLEAN NOT NULL DEFAULT TRUE,
                            "motivoFalha" VARCHAR(255),
                            "dataHora" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        );
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.tables WHERE table_name = 'AuditoriaCancelamentoItem'
                    ) THEN
                        CREATE TABLE "AuditoriaCancelamentoItem" (
                            "idAuditoria" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            "idItemPedido" UUID NOT NULL REFERENCES "ItemPedido"("idItemPedido") ON UPDATE CASCADE ON DELETE RESTRICT,
                            "idPedido" UUID NOT NULL REFERENCES "Pedido"("idPedido") ON UPDATE CASCADE ON DELETE RESTRICT,
                            "idMesa" UUID NOT NULL REFERENCES "Mesa"("idMesa") ON UPDATE CASCADE ON DELETE RESTRICT,
                            "sessao_id" VARCHAR(100),
                            "origem" VARCHAR(20) NOT NULL,
                            "idUsuario" UUID,
                            "motivo" TEXT,
                            "dataHora" TIMESTAMPTZ NOT NULL DEFAULT now(),
                            CONSTRAINT ck_auditoria_cancelamento_origem CHECK ("origem" IN ('CLIENTE', 'GARCOM', 'GERENTE', 'ADM')),
                            CONSTRAINT ck_auditoria_cancelamento_responsavel_motivo CHECK (
                                ("origem" = 'CLIENTE' AND "idUsuario" IS NULL AND "motivo" IS NULL)
                                OR ("origem" IN ('GARCOM', 'GERENTE', 'ADM') AND "idUsuario" IS NOT NULL AND "motivo" IS NOT NULL AND length(trim("motivo")) > 0)
                            )
                        );
                    END IF;

                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables WHERE table_name = 'Cardapio'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns WHERE table_name = 'Cardapio' AND column_name = 'tempoPreparo'
                    ) THEN
                        ALTER TABLE "Cardapio" ADD COLUMN "tempoPreparo" INTEGER NOT NULL DEFAULT 15;
                    END IF;

                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables WHERE table_name = 'ItemPedido'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns WHERE table_name = 'ItemPedido' AND column_name = 'origem'
                    ) THEN
                        ALTER TABLE "ItemPedido" ADD COLUMN "origem" VARCHAR(20) NOT NULL DEFAULT 'CLIENTE';
                    END IF;
                END $$;
            """))
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
                CREATE INDEX IF NOT EXISTS "idx_LogDesconto_Pedido" ON "LogDesconto" ("idPedido");
                CREATE INDEX IF NOT EXISTS "idx_LogDesconto_Restaurante" ON "LogDesconto" ("idRestaurante");
                CREATE INDEX IF NOT EXISTS ix_auditoria_cancelamento_item ON "AuditoriaCancelamentoItem" ("idItemPedido");
                CREATE INDEX IF NOT EXISTS ix_auditoria_cancelamento_pedido ON "AuditoriaCancelamentoItem" ("idPedido");
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
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.warning("Aviso durante migrações automáticas: %s", str(e))
    finally:
        if close_session:
            db.close()
