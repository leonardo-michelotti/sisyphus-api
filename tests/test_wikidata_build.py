from typing import Any

from sisyphus.clients.wikidata import build_thinker, collect_referenced_ids


def test_perfil_basico(nietzsche_entity: dict[str, Any], nietzsche_labels: dict[str, str]) -> None:
    t = build_thinker("Q9358", "Friedrich Nietzsche", nietzsche_entity, nietzsche_labels)
    assert t.qid == "Q9358"
    assert t.descricao and "filósofo" in t.descricao
    assert t.nascimento and t.nascimento.exibicao == "15/10/1844"
    assert t.morte and t.morte.exibicao == "25/08/1900"
    assert "filósofo" in t.ocupacoes


def test_labels_ausentes_nao_vazam_qid(
    nietzsche_entity: dict[str, Any], nietzsche_labels: dict[str, str]
) -> None:
    t = build_thinker("Q9358", "Friedrich Nietzsche", nietzsche_entity, nietzsche_labels)
    todos = [
        *t.ocupacoes,
        *t.correntes,
        *t.formacao,
        *t.nacionalidade,
        *(w.titulo for w in t.obras),
    ]
    # nenhum valor pode ser um QID cru (ex.: "Q120609061")
    assert not any(v.startswith("Q") and v[1:].isdigit() for v in todos)


def test_atribuicao_wikidata(
    nietzsche_entity: dict[str, Any], nietzsche_labels: dict[str, str]
) -> None:
    t = build_thinker("Q9358", "Friedrich Nietzsche", nietzsche_entity, nietzsche_labels)
    assert t.fontes[0].fonte == "Wikidata"
    assert t.fontes[0].licenca == "CC0 1.0"


def test_collect_refs_pega_obras(nietzsche_entity: dict[str, Any]) -> None:
    refs = collect_referenced_ids(nietzsche_entity["claims"])
    assert refs  # há entidades referenciadas
    assert all(r.startswith("Q") for r in refs)
