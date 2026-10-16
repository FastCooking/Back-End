from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.core.security import criar_refresh_token, criar_token, validar_refresh_token
from src.models.Usuario import Usuario
from src.schemas.AuthSchema import LoginRequest, RefreshTokenRequest, TokenResponse
from src.services.UsuarioService import verificar_senha

MAX_TENTATIVAS = 3
BLOQUEIO_MINUTOS = 5


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def login(self, dados: LoginRequest) -> TokenResponse:
        usuario = Usuario.get_by_email(self.db, dados.email)

        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-mail ou senha inválidos.",
            )

        agora = datetime.now()

        # Verifica se está bloqueado
        if usuario.bloqueadoAte and usuario.bloqueadoAte > agora:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Conta bloqueada. Tente novamente após {usuario.bloqueadoAte.strftime('%H:%M:%S')}.",
            )

        # Verifica senha
        if not verificar_senha(dados.senha, usuario.senha):
            usuario.tentativasFalhas += 1

            if usuario.tentativasFalhas >= MAX_TENTATIVAS:
                usuario.bloqueadoAte = agora + timedelta(minutes=BLOQUEIO_MINUTOS)
                self._notificar_gerente(usuario)

            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-mail ou senha inválidos.",
            )

        if not usuario.status:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário inativo.",
            )

        if usuario.restaurante and not usuario.restaurante.status:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Restaurante inativo ou desativado.",
            )

        # Login bem-sucedido: reseta tentativas
        usuario.tentativasFalhas = 0
        usuario.bloqueadoAte = None
        self.db.commit()

        token = criar_token(usuario.idUsuario, usuario.funcao, usuario.idRestaurante)
        refresh_token = criar_refresh_token(usuario.idUsuario)
        return TokenResponse(
            access_token=token,
            refresh_token=refresh_token,
            funcao=usuario.funcao,
            idUsuario=usuario.idUsuario,
            idRestaurante=usuario.idRestaurante,
            nome=usuario.nome,
        )

    def refresh(self, dados: RefreshTokenRequest) -> TokenResponse:
        usuario = validar_refresh_token(dados.refresh_token, self.db)
        novo_access_token = criar_token(
            usuario.idUsuario, usuario.funcao, usuario.idRestaurante
        )
        novo_refresh_token = criar_refresh_token(usuario.idUsuario)
        return TokenResponse(
            access_token=novo_access_token,
            refresh_token=novo_refresh_token,
            funcao=usuario.funcao,
            idUsuario=usuario.idUsuario,
            idRestaurante=usuario.idRestaurante,
            nome=usuario.nome,
        )

    def _notificar_gerente(self, usuario: Usuario) -> None:
        """Registra a tentativa de bloqueio (log; pode evoluir para registro em tabela própria)."""
        print(
            f"[ALERTA] Usuário {usuario.email} (id={usuario.idUsuario}) foi bloqueado "
            f"após {MAX_TENTATIVAS} tentativas incorretas — notificar gerente."
        )