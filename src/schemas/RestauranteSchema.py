import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def validar_cnpj(cnpj: str) -> str:
    """Valida os dígitos verificadores do CNPJ e retorna formatado como XX.XXX.XXX/XXXX-XX."""
    digitos = re.sub(r"\D", "", cnpj)

    if len(digitos) != 14:
        raise ValueError("O CNPJ deve conter exatamente 14 dígitos.")

    if digitos == digitos[0] * 14:
        raise ValueError("CNPJ inválido.")

    # Cálculo do primeiro dígito verificador
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_1 = sum(int(digitos[i]) * pesos_1[i] for i in range(12))
    resto_1 = soma_1 % 11
    digito_1 = 0 if resto_1 < 2 else 11 - resto_1

    if digito_1 != int(digitos[12]):
        raise ValueError("CNPJ inválido (primeiro dígito verificador incorreto).")

    # Cálculo do segundo dígito verificador
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_2 = sum(int(digitos[i]) * pesos_2[i] for i in range(13))
    resto_2 = soma_2 % 11
    digito_2 = 0 if resto_2 < 2 else 11 - resto_2

    if digito_2 != int(digitos[13]):
        raise ValueError("CNPJ inválido (segundo dígito verificador incorreto).")

    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


def validar_cep(cep: str) -> str:
    """Valida o CEP brasileiro e retorna formatado como XXXXX-XXX."""
    digitos = re.sub(r"\D", "", cep)
    if len(digitos) != 8:
        raise ValueError("O CEP deve conter exatamente 8 dígitos.")
    return f"{digitos[:5]}-{digitos[5:]}"


def validar_telefone(telefone: str) -> str:
    """Valida e formata telefone celular ou fixo com DDD."""
    digitos = re.sub(r"\D", "", telefone)
    if len(digitos) not in (10, 11):
        raise ValueError("O telefone deve conter 10 ou 11 dígitos com DDD.")

    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"


class RestauranteBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255, description="Nome fantasia/Razão social")
    cnpj: str = Field(..., description="CNPJ válido da empresa")
    telefone: str = Field(..., description="Telefone de contato com DDD")
    email: EmailStr = Field(..., description="E-mail oficial do restaurante")
    cep: str = Field(..., description="CEP do estabelecimento")
    status: bool = Field(default=True, description="Status do restaurante (ativo/inativo)")

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("O nome deve ter no mínimo 2 caracteres.")
        return v

    @field_validator("cnpj")
    @classmethod
    def validar_campo_cnpj(cls, v: str) -> str:
        return validar_cnpj(v)

    @field_validator("cep")
    @classmethod
    def validar_campo_cep(cls, v: str) -> str:
        return validar_cep(v)

    @field_validator("telefone")
    @classmethod
    def validar_campo_telefone(cls, v: str) -> str:
        return validar_telefone(v)


class RestauranteCreate(RestauranteBase):
    pass


class RestauranteUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=255, description="Nome fantasia/Razão social")
    cnpj: str | None = Field(default=None, description="CNPJ válido")
    telefone: str | None = Field(default=None, description="Telefone de contato")
    email: EmailStr | None = Field(default=None, description="E-mail de contato")
    cep: str | None = Field(default=None, description="CEP do restaurante")
    status: bool | None = Field(default=None, description="Status do restaurante")

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("O nome deve ter no mínimo 2 caracteres.")
        return v

    @field_validator("cnpj")
    @classmethod
    def validar_campo_cnpj(cls, v: str | None) -> str | None:
        if v is not None:
            return validar_cnpj(v)
        return v

    @field_validator("cep")
    @classmethod
    def validar_campo_cep(cls, v: str | None) -> str | None:
        if v is not None:
            return validar_cep(v)
        return v

    @field_validator("telefone")
    @classmethod
    def validar_campo_telefone(cls, v: str | None) -> str | None:
        if v is not None:
            return validar_telefone(v)
        return v


class RestauranteStatusUpdate(BaseModel):
    status: bool = Field(..., description="Novo status do restaurante (True=ativo, False=inativo)")


class RestauranteResponse(BaseModel):
    idRestaurante: int
    nome: str
    cnpj: str
    telefone: str
    email: str
    cep: str
    status: bool

    model_config = ConfigDict(from_attributes=True)
