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
