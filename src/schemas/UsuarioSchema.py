import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


def validar_cpf(cpf: str) -> str:
    """Valida os dígitos verificadores do CPF e retorna formatado como XXX.XXX.XXX-XX."""
    digitos = re.sub(r"\D", "", cpf)

    if len(digitos) != 11:
        raise ValueError("O CPF deve conter exatamente 11 dígitos.")

    if digitos == digitos[0] * 11:
        raise ValueError("CPF inválido.")

    # Cálculo do primeiro dígito verificador
    soma = sum(int(digitos[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    digito_1 = 0 if resto == 10 else resto

    if digito_1 != int(digitos[9]):
        raise ValueError("CPF inválido (primeiro dígito verificador incorreto).")

    # Cálculo do segundo dígito verificador
    soma = sum(int(digitos[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    digito_2 = 0 if resto == 10 else resto

    if digito_2 != int(digitos[10]):
        raise ValueError("CPF inválido (segundo dígito verificador incorreto).")

    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


FuncaoUsuario = Literal["Garcom", "Cozinheiro", "Gerente", "Adm"]


class UsuarioBase(BaseModel):
    idRestaurante: int | None = Field(default=None, description="ID do Restaurante vinculado")
    nome: str = Field(..., min_length=2, max_length=255, description="Nome completo do usuário")
    cpf: str | None = Field(default=None, description="CPF válido do usuário")
    email: EmailStr = Field(..., description="E-mail único do usuário")
    funcao: FuncaoUsuario = Field(..., description="Função/Cargo (Garcom, Cozinheiro, Gerente, Adm)")
    status: bool = Field(default=True, description="Status do usuário (ativo/inativo)")

    @model_validator(mode="before")
    @classmethod
    def preparar_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "login" in data and "email" not in data:
                data["email"] = data["login"]
            if "perfil" in data and "funcao" not in data:
                data["funcao"] = data["perfil"]
        return data

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("O nome deve ter no mínimo 2 caracteres.")
        return v

    @field_validator("cpf")
    @classmethod
    def validar_campo_cpf(cls, v: str | None) -> str | None:
        if v is not None:
            return validar_cpf(v)
        return v


class UsuarioCreate(UsuarioBase):
    senha: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Senha de acesso em texto plano (mínimo 6 caracteres)"
    )


class UsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=255, description="Nome completo")
    cpf: str | None = Field(default=None, description="CPF válido")
    email: EmailStr | None = Field(default=None, description="E-mail único")
    senha: str | None = Field(default=None, min_length=6, max_length=128, description="Nova senha")
    funcao: FuncaoUsuario | None = Field(default=None, description="Nova função/cargo")

    @model_validator(mode="before")
    @classmethod
    def preparar_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "login" in data and "email" not in data:
                data["email"] = data["login"]
            if "perfil" in data and "funcao" not in data:
                data["funcao"] = data["perfil"]
        return data

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("O nome deve ter no mínimo 2 caracteres.")
        return v

    @field_validator("cpf")
    @classmethod
    def validar_campo_cpf(cls, v: str | None) -> str | None:
        if v is not None:
            return validar_cpf(v)
        return v


class UsuarioStatusUpdate(BaseModel):
    status: bool = Field(..., description="Novo status do usuário (True para ativo, False para inativo)")


class UsuarioResponse(BaseModel):
    idUsuario: int
    idRestaurante: int
    nome: str
    cpf: str
    email: str
    funcao: str
    status: bool

    @computed_field
    @property
    def login(self) -> str:
        return self.email

    @computed_field
    @property
    def perfil(self) -> str:
        return self.funcao

    model_config = ConfigDict(from_attributes=True)
