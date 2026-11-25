from typing import Dict, List, Optional


VALID_CATEGORIES = [
    "Food",
    "Accommodation",
    "Transport",
    "Shopping",
    "Activities",
    "Utilities",
    "Miscellaneous",
]

VALID_SPLIT_METHODS = ["equal", "custom", "percentage"]


def compute_split_shares(
    amount_paise: int,
    split_method: str,
    participants: List[Dict],
    valid_member_ids: set,
) -> List[Dict]:
    """
    Calculate integer paise shares for each selected participant.
    Ensures exact sum == amount_paise with deterministic remainder handling.
    """
    if amount_paise <= 0:
        raise ValueError("Expense amount must be greater than zero.")

    if split_method not in VALID_SPLIT_METHODS:
        raise ValueError(f"Unsupported split method: {split_method}")

    if not participants:
        raise ValueError("At least one participant must be selected.")

    seen_ids = set()
    for p in participants:
        mid = p["member_id"]
        if mid not in valid_member_ids:
            raise ValueError(f"Member {mid} does not belong to this trip.")
        if mid in seen_ids:
            raise ValueError(f"Duplicate participant member {mid}.")
        seen_ids.add(mid)

    n = len(participants)

    if split_method == "equal":
        base = amount_paise // n
        remainder = amount_paise % n
        result = []
        for idx, p in enumerate(participants):
            share = base + (1 if idx < remainder else 0)
            result.append(
                {
                    "member_id": p["member_id"],
                    "share_paise": share,
                    "percentage_bps": None,
                }
            )
        assert sum(r["share_paise"] for r in result) == amount_paise
        return result

    if split_method == "custom":
        result = []
        total = 0
        for p in participants:
            share = p.get("share_paise")
            if share is None or not isinstance(share, int) or share < 0:
                raise ValueError("Custom split requires non-negative integer paise shares.")
            total += share
            result.append(
                {
                    "member_id": p["member_id"],
                    "share_paise": share,
                    "percentage_bps": None,
                }
            )
        if total != amount_paise:
            diff = amount_paise - total
            raise ValueError(
                f"Custom split total ({total} paise) must equal expense amount ({amount_paise} paise, difference {diff} paise)."
            )
        return result

    # percentage split using exact integer basis points (100.00% = 10000 bps)
    bps_list = []
    for p in participants:
        if p.get("percentage_bps") is not None:
            bps = int(p["percentage_bps"])
        elif p.get("percentage") is not None:
            bps = int(round(float(p["percentage"]) * 100))
        else:
            raise ValueError("Percentage split requires a percentage value for every participant.")
        if bps < 0:
            raise ValueError("Percentage cannot be negative.")
        bps_list.append(bps)

    total_bps = sum(bps_list)
    if total_bps != 10000:
        raise ValueError(
            f"Percentages must total 100.00% (currently {total_bps / 100:.2f}%)."
        )

    exact_numerators = [amount_paise * bps for bps in bps_list]
    base_shares = [num // 10000 for num in exact_numerators]
    remainders = sorted(
        [(num % 10000, idx) for idx, num in enumerate(exact_numerators)],
        key=lambda item: (-item[0], item[1]),
    )
    leftover = amount_paise - sum(base_shares)
    for i in range(leftover):
        _, target_idx = remainders[i]
        base_shares[target_idx] += 1

    result = []
    for idx, p in enumerate(participants):
        result.append(
            {
                "member_id": p["member_id"],
                "share_paise": base_shares[idx],
                "percentage_bps": bps_list[idx],
            }
        )
    assert sum(r["share_paise"] for r in result) == amount_paise
    return result


def calculate_member_balances(
    members: List,
    expenses: List,
    completed_settlements: Optional[List] = None,
) -> List[Dict]:
    """
    Compute each member's financial ledger in integer paise:
    - expense_net_paise = total_paid_paise - total_share_paise
    - remaining_net_paise = expense_net_paise + settlement_paid_paise - settlement_received_paise
    Both expense_net_paise and remaining_net_paise strictly sum to zero across the trip.
    """
    completed_settlements = completed_settlements or []
    ledger: Dict[int, Dict] = {}
    for m in members:
        ledger[m.id] = {
            "member_id": m.id,
            "member_name": m.name,
            "member_email": m.email,
            "total_paid_paise": 0,
            "total_share_paise": 0,
            "expense_net_paise": 0,
            "settlement_paid_paise": 0,
            "settlement_received_paise": 0,
            "remaining_net_paise": 0,
            "expenses_paid_count": 0,
            "expenses_participated_count": 0,
        }

    for exp in expenses:
        if exp.payer_id in ledger:
            ledger[exp.payer_id]["total_paid_paise"] += exp.amount_paise
            ledger[exp.payer_id]["expenses_paid_count"] += 1
        for sh in exp.shares:
            if sh.member_id in ledger:
                ledger[sh.member_id]["total_share_paise"] += sh.share_paise
                ledger[sh.member_id]["expenses_participated_count"] += 1

    for st in completed_settlements:
        if st.status != "completed":
            continue
        if st.from_member_id in ledger:
            ledger[st.from_member_id]["settlement_paid_paise"] += st.amount_paise
        if st.to_member_id in ledger:
            ledger[st.to_member_id]["settlement_received_paise"] += st.amount_paise

    rows = []
    expense_sum = 0
    remaining_sum = 0
    for m in members:
        row = ledger[m.id]
        row["expense_net_paise"] = row["total_paid_paise"] - row["total_share_paise"]
        row["remaining_net_paise"] = (
            row["expense_net_paise"]
            + row["settlement_paid_paise"]
            - row["settlement_received_paise"]
        )
        expense_sum += row["expense_net_paise"]
        remaining_sum += row["remaining_net_paise"]
        rows.append(row)

    if members:
        assert expense_sum == 0, f"Expense net balances do not sum to zero: {expense_sum}"
        assert remaining_sum == 0, f"Remaining net balances do not sum to zero: {remaining_sum}"

    return rows


def format_inr(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    abs_p = abs(paise)
    rupees = abs_p // 100
    cents = abs_p % 100
    s = str(rupees)
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.append(rest)
        formatted_rupees = ",".join(reversed(parts)) + "," + last3
    else:
        formatted_rupees = s
    return f"{sign}₹{formatted_rupees}.{cents:02d}"
