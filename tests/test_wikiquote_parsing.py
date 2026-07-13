from sisyphus.clients.wikiquote import parse_quotes
from sisyphus.schemas import QuoteCategory


def test_extrai_muitas_frases(camus_html: str) -> None:
    quotes = parse_quotes(camus_html, autor="Albert Camus", page_url="http://x")
    assert len(quotes) > 50


def test_wikilinks_resolvidos_sem_markup(camus_html: str) -> None:
    quotes = parse_quotes(camus_html, autor="Albert Camus", page_url="http://x")
    for q in quotes:
        assert "[[" not in q.texto
        assert "]]" not in q.texto
        assert not q.texto.startswith('"')


def test_secao_sobre_e_ruido_excluidos(camus_html: str) -> None:
    quotes = parse_quotes(camus_html, autor="Albert Camus", page_url="http://x")
    obras = {q.obra for q in quotes if q.categoria is QuoteCategory.obra}
    assert "Sobre" not in obras
    assert "Ligações externas" not in obras
    assert "Referências" not in obras


def test_categorias_derivadas_da_secao(camus_html: str) -> None:
    quotes = parse_quotes(camus_html, autor="Albert Camus", page_url="http://x")
    cats = {q.categoria for q in quotes}
    assert QuoteCategory.verificada in cats  # seção "Verificadas"
    assert QuoteCategory.obra in cats  # seções de obra (ex.: "A Peste (1947)")
    # frase de obra carrega o título da obra
    de_obra = [q for q in quotes if q.categoria is QuoteCategory.obra]
    assert all(q.obra for q in de_obra)


def test_atribuicao_presente(camus_html: str) -> None:
    quotes = parse_quotes(camus_html, autor="Albert Camus", page_url="http://x")
    assert quotes[0].fonte.fonte == "Wikiquote"
    assert "BY-SA" in quotes[0].fonte.licenca
