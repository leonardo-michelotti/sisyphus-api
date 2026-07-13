import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def camus_html() -> str:
    return (FIXTURES / "camus_quotes.html").read_text(encoding="utf-8")


@pytest.fixture
def nietzsche_entity() -> dict[str, Any]:
    data = json.loads((FIXTURES / "nietzsche_entity.json").read_text(encoding="utf-8"))
    return data["entities"]["Q9358"]


@pytest.fixture
def nietzsche_labels() -> dict[str, str]:
    return json.loads((FIXTURES / "nietzsche_labels.json").read_text(encoding="utf-8"))
