from datetime import UTC, datetime, timedelta

import pytest

from src.services.PrioridadeKDS import (
    calcular_pontuacao,
    eh_sobremesa,
    normalizar_categoria,
)


@pytest.mark.parametrize(
    ("categoria", "peso", "limite"),
    [
        ("Bebidas", 2.0, 3),
        ("Entrada", 1.5, 10),
        ("Pratos principais", 1.0, 20),
        ("Sobremesas", 0.5, 5),
    ],
)
def test_pontuacao_por_categoria(categoria, peso, limite):
    agora = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    criacao = agora - timedelta(minutes=limite)

    espera, pontuacao = calcular_pontuacao(categoria, criacao, agora)

    assert espera == limite
    assert pontuacao == pytest.approx(peso * 2)


def test_categoria_ignora_acento_espacos_e_maiusculas():
    assert normalizar_categoria("  SOBREMÉSAS  ") == "sobremesa"
    assert normalizar_categoria("BEBIDAS") == "bebida"
    assert normalizar_categoria(" Pratos principais ") == "prato principal"


def test_categoria_desconhecida_usa_regra_neutra():
    agora = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    criacao = agora - timedelta(minutes=20)

    espera, pontuacao = calcular_pontuacao("Categoria desconhecida", criacao, agora)

    assert espera == 20
    assert pontuacao == pytest.approx(2.0)


def test_identifica_sobremesa():
    assert eh_sobremesa("Sobremesa")
    assert eh_sobremesa("SOBREMESAS")
    assert not eh_sobremesa("Bebidas")
