from sisyphus.dates import parse_wikidata_time


def test_data_completa() -> None:
    d = parse_wikidata_time("+1913-11-07T00:00:00Z", 11)
    assert d is not None
    assert d.precisao == "dia"
    assert d.exibicao == "07/11/1913"


def test_ano_apenas() -> None:
    d = parse_wikidata_time("+1844-00-00T00:00:00Z", 9)
    assert d is not None
    assert d.precisao == "ano"
    assert d.exibicao == "1844"


def test_seculo_antes_de_cristo() -> None:
    # Sun Tzu: nascimento em -0544, precisão de século (7)
    d = parse_wikidata_time("-0544-00-00T00:00:00Z", 7)
    assert d is not None
    assert d.precisao == "seculo"
    assert d.exibicao == "século VI a.C."


def test_ano_antes_de_cristo() -> None:
    d = parse_wikidata_time("-0496-00-00T00:00:00Z", 9)
    assert d is not None
    assert d.exibicao == "496 a.C."


def test_valor_invalido() -> None:
    assert parse_wikidata_time("qualquer coisa", 11) is None
