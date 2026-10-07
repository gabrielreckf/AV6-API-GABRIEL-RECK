"""TAREFA DO ALUNO -- os cinco testes que faltam para os >= 8 do entregavel."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, localcontext

from app.dominio.motor_emergia import calcular_indices
from app.dominio.tipos import CategoriaFluxo, FluxoEmergetico


def test_regressao_numerica_contra_a_planilha(fluxos_golden):
    """Compara os seis indices com o inventario de referencia."""
    resultado = calcular_indices(fluxos_golden, Decimal("1000"))

    assert abs(resultado.y - Decimal("200.000000")) <= Decimal("1E-6")
    assert abs(resultado.eyr - Decimal("4.000000")) <= Decimal("1E-6")
    assert abs(resultado.elr - Decimal("0.739130")) <= Decimal("1E-6")
    assert abs(resultado.esi - Decimal("5.411765")) <= Decimal("1E-6")
    assert abs(resultado.eii - Decimal("0.184783")) <= Decimal("1E-6")
    assert abs(resultado.percentual_r - Decimal("57.500000")) <= Decimal("1E-6")


def test_quantizacao_unica_no_final():
    """Prova que arredondar resultados intermediarios altera o resultado final."""
    seis_casas = Decimal("1E-6")

    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_EVEN

        # Valores do inventario de referencia:
        # Y = 200, F = 50, renovaveis = 115, nao renovaveis = 85.
        eyr_exato = Decimal("200") / Decimal("50")
        elr_exato = Decimal("85") / Decimal("115")

        # Forma incorreta: arredonda antes da operacao final.
        eyr_intermediario = eyr_exato.quantize(seis_casas)
        elr_intermediario = elr_exato.quantize(seis_casas)
        esi_com_arredondamento_intermediario = (
            eyr_intermediario / elr_intermediario
        ).quantize(seis_casas)

        # Forma usada pelo motor: mantem precisao e quantiza apenas no final.
        esi_quantizado_no_final = (eyr_exato / elr_exato).quantize(seis_casas)

    assert esi_com_arredondamento_intermediario != esi_quantizado_no_final
    assert esi_quantizado_no_final == Decimal("5.411765")


def test_ordem_da_soma_com_magnitudes_divergentes():
    """Exercita Decimal com magnitudes muito diferentes sob precisao 28."""
    grande = FluxoEmergetico(
        "fluxo_grande",
        CategoriaFluxo.R,
        Decimal("1E20"),
    )
    pequeno = FluxoEmergetico(
        "fluxo_pequeno",
        CategoriaFluxo.MR,
        Decimal("1E-5"),
    )

    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_EVEN

        soma_grande_primeiro = grande.emergia_sej + pequeno.emergia_sej
        soma_pequeno_primeiro = pequeno.emergia_sej + grande.emergia_sej

    # Com estas magnitudes, 28 digitos ainda sao suficientes para preservar
    # a parcela pequena. A precisao do contexto e o limite da representacao;
    # por isso a ordem do inventario nao deve ser deixada ao acaso quando
    # magnitudes ainda mais divergentes forem aceitas pelo dominio.
    assert soma_grande_primeiro == soma_pequeno_primeiro
    assert soma_grande_primeiro == Decimal("100000000000000000000.00001")


def test_erro_de_dominio_responde_problem_json(cliente, corpo_golden):
    """Inventario sem fluxo renovavel deve sair 422 em application/problem+json."""
    corpo = {
        "fluxos": [
            {
                "recurso": "solo",
                "categoria": "N",
                "emergia_sej": "50",
            },
            {
                "recurso": "diesel",
                "categoria": "MN",
                "emergia_sej": "20",
            },
        ],
        "energia_produto_j": corpo_golden["energia_produto_j"],
    }

    resposta = cliente.post("/v1/safras/42/calculos", json=corpo)

    assert resposta.status_code == 422
    assert resposta.headers["content-type"].startswith(
        "application/problem+json"
    )

    problema = resposta.json()

    assert problema["type"].endswith("/fluxos-insuficientes")
    assert problema["title"] == "Fluxos insuficientes"
    assert problema["status"] == 422
    assert "detail" in problema
    assert problema["instance"] == "/v1/safras/42/calculos"


def test_campo_extra_no_corpo_da_requisicao_e_rejeitado(
    cliente,
    corpo_golden,
):
    """Campo desconhecido deve ser rejeitado com 422."""
    corpo = dict(corpo_golden)
    corpo["energia_produto_jj"] = "1000"

    resposta = cliente.post("/v1/safras/42/calculos", json=corpo)

    assert resposta.status_code == 422
    assert resposta.headers["content-type"].startswith(
        "application/problem+json"
    )

    problema = resposta.json()

    assert problema["status"] == 422
    assert problema["type"].endswith("/requisicao-invalida")

    erros = problema["erros"]

    assert any(
        erro["campo"] == "body.energia_produto_jj"
        for erro in erros
    )