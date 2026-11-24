from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
HALF = Decimal("0.5")


def money(value):
    """Quantize a Decimal to USD cents, rounding half up."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def money_text(value):
    return f"{money(value):.2f}"


def signed(value):
    """Format a signed USD amount; a zero never carries a sign."""
    value = money(value)
    return "0.00" if value == 0 else f"{value:.2f}"


def rate_text(value):
    """Exact per-minute rate for display, keeping at least two decimals.

    A half of an odd-cent tier rate (e.g. 0.17 / 2 = 0.085) must not be rounded
    away in the shown rate, or the displayed rate would not reproduce the total.
    """
    value = Decimal(value)
    text = format(value.normalize(), "f")
    if "." not in text:
        return text + ".00"
    return text + "0" * max(0, 2 - len(text.split(".")[1]))


def despatch_rate(term):
    """Speed-money rate is half of the first demurrage tier."""
    return Decimal(term["rate1_usd_min"]) * HALF


def demurrage_tiers(term, overtime):
    overtime = max(0, int(overtime))
    first = min(overtime, int(term["tier1_min"]))
    for tier, duration in enumerate((first, overtime - first), 1):
        rate = Decimal(term[f"rate{tier}_usd_min"])
        yield tier, duration, rate, rate * duration


def tier_costs(term, overtime):
    for tier, duration, rate, cost in demurrage_tiers(term, overtime):
        yield {"tier": tier, "minutes": duration, "rate_usd_min": rate_text(rate),
               "expected_usd": money_text(cost)}


def demurrage_total(term, overtime):
    return money(sum((cost for _, _, _, cost in demurrage_tiers(term, overtime)), Decimal(0)))
