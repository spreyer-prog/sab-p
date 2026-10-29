"""Pure selection policy; no ORM writes and no guessed currency conversion."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


class PriceBindingConflict(ValueError):
    """The existing project data do not establish one safe selling price."""


@dataclass(frozen=True)
class PriceCandidate:
    line_id: int
    source_kind: str
    source_id: int
    currency_id: int
    unit_price: float
    reference: str


def select_project_price(candidates: Iterable[PriceCandidate], *, source_kind: str,
                         source_id: int, currency_id: int):
    """Return the oldest consistent source, including a genuine zero price.

    Caller must already restrict the candidates to the same company, project,
    commercial customer and exact LV/NTG code. Different codes are not synonyms.
    """
    rows = tuple(candidates)
    if not rows:
        return None
    amounts = set()
    for row in rows:
        if (row.source_kind, row.source_id) != (source_kind, source_id):
            raise PriceBindingConflict(
                "Diese LV-/NTG-Position ist bereits einem anderen Artikel zugeordnet. "
                "Bitte eine eigene Projektposition verwenden.")
        if row.currency_id != currency_id:
            raise PriceBindingConflict(
                "Für diese Projektposition besteht bereits ein Preis in einer anderen "
                "Währung. Eine automatische Übernahme oder Umrechnung ist gesperrt.")
        amount = Decimal(str(row.unit_price))
        if not amount.is_finite():
            raise PriceBindingConflict("Der vorhandene Projektpreis ist keine endliche Zahl.")
        amounts.add(amount)
    if len(amounts) != 1:
        references = ", ".join(dict.fromkeys(row.reference for row in rows))
        raise PriceBindingConflict(
            "Für dieselbe LV-/NTG-Position bestehen unterschiedliche Einzelpreise "
            "(%s). Bestehende Angebote werden nicht automatisch geändert. "
            "Bitte den Preiswiderspruch zuerst klären." % references)
    return min(rows, key=lambda row: row.line_id)
