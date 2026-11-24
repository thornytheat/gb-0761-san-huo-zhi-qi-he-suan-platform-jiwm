import hashlib
import json


def certify(snapshot):
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    evidence = snapshot["results"]
    ledger = evidence["ledger"]
    reversal = ledger.get("reversal") or {}
    return {"snapshot": snapshot, "integrity_sha256": hashlib.sha256(payload).hexdigest(),
            "can_settle": ledger["complete"] and not evidence["clock"]["missing"]
            and not ledger["differences"] and evidence["clock"]["balanced"]
            and ledger.get("direction_settled", True) and not reversal.get("required"),
            "direction": ledger.get("direction"),
            "reversal": reversal,
            "evidence_counts": {"intervals": len(evidence["clock"]["rows"]), "tiers": len(ledger["rows"]),
                                "isolated": len(evidence["intake"]["isolated"])}}
