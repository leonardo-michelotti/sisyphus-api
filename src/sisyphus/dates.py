"""Formatação de datas do Wikidata.

O Wikidata entrega um valor `time` com `precision` (ver PILARES_TECNICOS.md):
6=milênio, 7=século, 8=década, 9=ano, 10=mês, 11=dia. Datas AEC vêm com sinal
negativo (ex.: Sun Tzu `-0544`). Truncar string quebra — usar sempre a precisão.
"""

from __future__ import annotations

import re

from .schemas import PartialDate

# +1913-11-07T00:00:00Z  /  -0544-00-00T00:00:00Z
_TIME_RE = re.compile(r"^([+-])(\d+)-(\d{2})-(\d{2})")
_ROMAN = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


def _roman(n: int) -> str:
    out = []
    for value, sym in _ROMAN:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def parse_wikidata_time(time: str, precision: int) -> PartialDate | None:
    """Converte um valor `time`/`precision` do Wikidata em `PartialDate`.

    Retorna None se o valor não for parseável.
    """
    m = _TIME_RE.match(time)
    if not m:
        return None
    sign, year_s, month, day = m.groups()
    year = int(year_s)
    bce = sign == "-"
    sufixo = " a.C." if bce else ""

    if precision >= 11 and month != "00" and day != "00":
        exibicao = f"{day}/{month}/{year:04d}{sufixo}"
        precisao = "dia"
    elif precision == 10 and month != "00":
        exibicao = f"{month}/{year:04d}{sufixo}"
        precisao = "mes"
    elif precision == 9 or (precision >= 10):
        # ano (ou mês/dia ausentes na prática)
        exibicao = f"{year}{sufixo}"
        precisao = "ano"
    elif precision == 7:
        seculo = (year - 1) // 100 + 1
        exibicao = f"século {_roman(seculo)}{sufixo}"
        precisao = "seculo"
    elif precision == 8:
        exibicao = f"década de {year // 10 * 10}{sufixo}"
        precisao = "decada"
    else:  # milênio / mais grosseiro — cai para o ano bruto
        exibicao = f"{year}{sufixo}"
        precisao = "ano"

    valor = f"{sign if bce else ''}{year:04d}-{month}-{day}"
    return PartialDate(valor=valor, precisao=precisao, exibicao=exibicao)
