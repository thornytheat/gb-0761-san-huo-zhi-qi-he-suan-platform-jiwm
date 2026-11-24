from decimal import Decimal

from .rates import despatch_rate, demurrage_total, money, money_text, rate_text, signed, tier_costs


def _bounds(counted, missing, allowance):
    """Verified-minute bounds for each direction while the gap stays open.

    GAP minutes are unverified: they may turn out to be working time or exempt
    time, so the true counted total lies in ``[counted, counted + missing]``.
    Anything tied to the gap is therefore a range, never a settled number.
    """
    return {
        "demurrage_low": max(0, counted - allowance),
        "demurrage_high": max(0, counted + missing - allowance),
        "despatch_low": max(0, allowance - counted - missing),
        "despatch_high": max(0, allowance - counted),
    }


def _direction(bounds):
    if bounds["demurrage_low"] > 0:
        # Even counting no gap minute, the ship is already over the allowance.
        return "DEMURRAGE"
    if bounds["demurrage_high"] > 0:
        # Demurrage is still reachable if the gap turns out to be working time,
        # so the result can flip to demurrage once evidence arrives. Never call
        # despatch (or zero) final here.
        return "UNDETERMINED"
    # Demurrage is impossible even counting every gap minute.
    return "BALANCED" if bounds["despatch_high"] == 0 else "DESPATCH"


def compare(notice, clock, invoice, quarantined):
    term = notice["term"]
    counted, missing, allowance = clock["counted"], clock["missing"], clock["allowance_min"]
    bounds = _bounds(counted, missing, allowance)
    direction = _direction(bounds)
    settled = direction != "UNDETERMINED"
    rate = despatch_rate(term)

    demurrage_low = demurrage_total(term, bounds["demurrage_low"])
    demurrage_high = demurrage_total(term, bounds["demurrage_high"])
    despatch_low = money(rate * bounds["despatch_low"])
    despatch_high = money(rate * bounds["despatch_high"])

    # Confirmable amount is a positive magnitude in the settled direction; while
    # the direction can still flip it confirms nothing at all.
    if direction == "DEMURRAGE":
        confirmable, confirmed_minutes = demurrage_low, bounds["demurrage_low"]
    elif direction == "DESPATCH":
        confirmable, confirmed_minutes = despatch_low, bounds["despatch_low"]
    elif direction == "BALANCED":
        confirmable, confirmed_minutes = Decimal("0"), 0
    else:
        confirmable, confirmed_minutes = None, 0

    # What the open gap can still add on each side, kept apart so the reader sees
    # that the same minutes cannot be both despatch and demurrage.
    pending_demurrage = demurrage_high - demurrage_low
    pending_despatch = despatch_high - despatch_low

    actuals = {item["tier"]: item for item in invoice}
    rows = []
    for tier in tier_costs(term, clock["overtime_min"]):
        actual = actuals.get(tier["tier"])
        disputed = [q["line"] for q in quarantined if q["source"] == "invoice" and q["code"] == "KEY_CONFLICT"
                    and q["key"] == tier["tier"]]
        if actual is None:
            code = "INVOICE_CONFLICT" if disputed else "INVOICE_MISSING"
            rows.append({**tier, "code": code, "invoice_line": None, "conflict_lines": disputed,
                         "actual_usd": None, "actual_minutes": None, "delta_usd": None})
            continue
        delta = Decimal(tier["expected_usd"]) - Decimal(actual["usd"])
        code = "MATCH" if not delta and tier["minutes"] == actual["minutes"] else "TIER_DIFFERENCE"
        rows.append({**tier, "code": code, "invoice_line": actual["line"], "actual_usd": actual["usd"],
                     "actual_minutes": actual["minutes"], "delta_usd": f"{delta:.2f}"})
    complete = all(r["delta_usd"] is not None for r in rows)
    expected = sum(Decimal(r["expected_usd"]) for r in rows)
    seen = sum(Decimal(r["actual_usd"]) for r in rows if r["actual_usd"] is not None)

    # A demurrage invoice must be reversed in full, never netted to zero, once
    # demurrage is ruled out. Only a run that is not already demurrage has a
    # reversal to consider; while the direction can still flip, or the invoice
    # is incomplete/conflicting, the invoice stays on hold rather than booked.
    reason = None
    if seen > 0 and direction != "DEMURRAGE":
        if not complete:
            reason = "INVOICE_INCOMPLETE"
        elif direction == "UNDETERMINED":
            reason = "DIRECTION_UNSETTLED"
        else:
            reason = "OPPOSITE_DIRECTION" if direction == "DESPATCH" else "NO_LIABILITY"
    required = reason in {"OPPOSITE_DIRECTION", "NO_LIABILITY"}
    reversal = {
        "required": required,
        "pending": reason in {"DIRECTION_UNSETTLED", "INVOICE_INCOMPLETE"},
        "invoice_usd": f"{seen:.2f}" if complete else None,
        "usd": f"{-seen:.2f}" if required else None,
        "reason": reason,
    }

    # Tier comparison is "port expected demurrage minus ship invoiced". It is
    # only booked once the direction is settled and every tier is present;
    # otherwise a gap could still flip the figure and it must stay unbooked,
    # never quietly reported as zero. When the result is despatch/balance the
    # expected demurrage is zero, so the ship's whole invoice shows here as a
    # negative delta -- the same amount the reversal books explicitly.
    delta = (expected - seen) if (complete and settled) else None

    return {"expected_usd": f"{expected:.2f}", "seen_invoice_usd": f"{seen:.2f}",
            "delta_usd": signed(delta) if delta is not None else None,
            "complete": complete, "differences": sum(r["code"] != "MATCH" for r in rows),
            "direction": direction, "direction_settled": settled,
            "confirmable_usd": signed(confirmable) if confirmable is not None else None,
            "confirmed_minutes": confirmed_minutes,
            "pending": {"minutes": missing,
                        "demurrage_usd": money_text(pending_demurrage),
                        "despatch_usd": money_text(pending_despatch),
                        "at_risk_usd": money_text(pending_demurrage + pending_despatch),
                        "demurrage_total_usd": money_text(demurrage_high),
                        "despatch_total_usd": money_text(despatch_high)},
            "despatch": {"rate_usd_min": rate_text(rate),
                         "confirmed_usd": money_text(despatch_low),
                         "possible_usd": money_text(despatch_high),
                         "minutes_confirmed": bounds["despatch_low"],
                         "minutes_possible": bounds["despatch_high"]},
            "reversal": reversal,
            "rows": rows}
