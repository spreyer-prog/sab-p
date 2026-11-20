"""Pure reference for the supplied Excel quote formulas; not a live price update.

Column semantics come from row 30. No offer/customer defaults are inferred.
Existing quotations must keep their stored snapshots when this reference is
integrated. This file does not read or write any Odoo models.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


def dec(value):
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Non-finite calculation input")
    return result


@dataclass(frozen=True)
class QuoteFactors:
    material: Decimal
    material_discount: Decimal
    auxiliary: Decimal
    terminal_material_deduction: Decimal
    hourly_rate: Decimal
    time: Decimal
    difficulty: Decimal
    planning_hourly_rate: Decimal
    planning: Decimal
    terminal_time_deduction: Decimal
    metal: Decimal
    packaging: Decimal
    transport: Decimal
    margin: Decimal
    sales: Decimal
    supplement: Decimal
    trade: tuple

    @property
    def commercial(self):
        # Ang00!X7: first add the two surcharges, then multiply margin/sales.
        return (dec(self.packaging) + dec(self.transport) - 1) * dec(self.margin) * dec(self.sales)


def calculate_quote_reference(*, factors, material_price, price_unit, discount_factor,
                              minutes, auxiliary, metal=0, quantity=1, mode="M",
                              supplement=False, terminal_time_quantity=0,
                              terminal_material_quantity=0):
    """Match W:AE and U:V; retain precision until Excel's explicit ROUND calls."""
    mode = str(mode).upper()  # Excel text equality is case-insensitive.
    unit = dec(price_unit)
    if unit <= 0:
        raise ValueError("Price unit / VE must be greater than zero")
    rebate = dec(1 if discount_factor is None else discount_factor)
    net = dec(material_price) / unit * rebate
    effective_minutes = dec(minutes) - dec(terminal_time_quantity) * dec(factors.terminal_time_deduction)
    w = dec(metal) * dec(factors.metal)
    x = net * dec(factors.material) * dec(factors.material_discount)
    y = (dec(auxiliary) - dec(terminal_material_quantity) * dec(factors.terminal_material_deduction)) * dec(factors.auxiliary)
    z = effective_minutes * dec(factors.hourly_rate) / 60 * dec(factors.time) * dec(factors.difficulty)
    aa = (Decimal(0) if mode == "O" else
          effective_minutes * dec(factors.planning_hourly_rate) / 60 * (dec(factors.planning) - 1))
    ab = w + x + y + z + aa
    ac = (w * dec(factors.sales) + (ab - w) * factors.commercial).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if mode in ("H1", "H2", "H3", "H4", "H5", "H6"):
        index = int(mode[1]) - 1
        if len(factors.trade) != 6:
            raise ValueError("Six trade factors are required for H1-H6")
        u = (net * dec(factors.trade[index])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        u = ac * (dec(factors.supplement) if supplement else 1)
    qty = dec(quantity)
    return {
        "net_material": net, "W": w, "X": x, "Y": y, "Z": z, "AA": aa,
        "AB": ab, "AC": ac, "U": u, "V": Decimal(0) if mode == "A" else qty * u,
        "AD": Decimal(0) if mode == "A" else effective_minutes * dec(factors.time) * dec(factors.difficulty) * qty,
        "AE": Decimal(0) if mode == "A" else effective_minutes * qty * (dec(factors.planning) - 1),
    }
