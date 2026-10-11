import unicodedata
from datetime import UTC, datetime

# Peso e tempo limite em minutos por categoria.
REGRAS_CATEGORIA = {
    "bebida": {"peso": 2.0, "limite": 3},
    "entrada": {"peso": 1.5, "limite": 10},
    "prato principal": {"peso": 1.0, "limite": 20},
    "sobremesa": {"peso": 0.5, "limite": 5},
}

# Categoria desconhecida: regra neutra de fallback.
REGRA_PADRAO = {"peso": 1.0, "limite": 20}


def normalizar_categoria(categoria: str | None) -> str:
    """Padroniza acentos, maiúsculas, espaços e plural."""
    texto = unicodedata.normalize("NFKD", categoria or "")
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    texto = " ".join(texto.casefold().split())

    aliases = {
        "bebidas": "bebida",
        "entradas": "entrada",
        "pratos principais": "prato principal",
        "prato principal": "prato principal",
        "sobremesas": "sobremesa",
    }
    return aliases.get(texto, texto)


def eh_sobremesa(categoria: str | None) -> bool:
    return normalizar_categoria(categoria) == "sobremesa"


def calcular_pontuacao(
    categoria: str | None,
    data_criacao: datetime,
    agora: datetime | None = None,
) -> tuple[float, float]:
    """
    Retorna (tempo de espera em minutos, pontuação dinâmica).
    Pontuação maior significa maior prioridade na fila.
    """
    regra = REGRAS_CATEGORIA.get(
        normalizar_categoria(categoria),
        REGRA_PADRAO,
    )

    agora = agora or datetime.now(UTC)

    # Compatibilidade com datas sem informação de fuso horário.
    if data_criacao.tzinfo is None:
        data_criacao = data_criacao.replace(tzinfo=UTC)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=UTC)

    segundos = max(0.0, (agora - data_criacao).total_seconds())
    espera = segundos / 60.0
    pontuacao = regra["peso"] * (1 + espera / regra["limite"])

    return round(espera, 2), round(pontuacao, 4)
