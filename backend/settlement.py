from typing import Dict, List, Tuple


def compute_minimum_settlements(balances: Dict[int, int]) -> List[Dict]:
    """
    Compute globally minimum-transaction settlements using backtracking with pruning.

    Args:
        balances: mapping of member_id -> net_balance_paise
                  (> 0 receives money, < 0 owes money).
                  Must sum to zero.

    Returns:
        List of dicts: [{"from_member_id": int, "to_member_id": int, "amount_paise": int}, ...]
        Guaranteed:
          - Globally minimum number of transactions.
          - No self-payments or zero-value transactions.
          - Direct debtor -> creditor transfers only (no pass-through intermediaries).
    """
    total = sum(balances.values())
    if total != 0:
        raise ValueError(f"Net balances must sum to zero before settlement (got {total}).")

    debtors: List[List[int]] = []
    creditors: List[List[int]] = []
    for mid, amt in sorted(balances.items()):
        if amt < 0:
            debtors.append([mid, -amt])
        elif amt > 0:
            creditors.append([mid, amt])

    if not debtors or not creditors:
        return []

    fixed_txs: List[Dict] = []

    # Exact magnitude pair elimination: if a debtor owes X and a creditor is owed X,
    # settling them in 1 transaction is always part of a globally optimal solution.
    matched_d = set()
    matched_c = set()
    for di, (d_id, d_amt) in enumerate(debtors):
        for ci, (c_id, c_amt) in enumerate(creditors):
            if ci in matched_c:
                continue
            if d_amt == c_amt:
                fixed_txs.append(
                    {
                        "from_member_id": d_id,
                        "to_member_id": c_id,
                        "amount_paise": d_amt,
                    }
                )
                matched_d.add(di)
                matched_c.add(ci)
                break

    rem_debtors = [debtors[i] for i in range(len(debtors)) if i not in matched_d]
    rem_creditors = [creditors[i] for i in range(len(creditors)) if i not in matched_c]

    if not rem_debtors or not rem_creditors:
        return fixed_txs

    # Sort descending by magnitude to find tight upper bounds quickly
    rem_debtors.sort(key=lambda x: -x[1])
    rem_creditors.sort(key=lambda x: -x[1])

    # Build unified non-zero list: negative for debtors, positive for creditors
    # Keep track of active non-zero balances
    d_vals = [d[1] for d in rem_debtors]
    d_ids = [d[0] for d in rem_debtors]
    c_vals = [c[1] for c in rem_creditors]
    c_ids = [c[0] for c in rem_creditors]

    # Upper bound from greedy solution so pruning starts tight
    greedy_txs = _greedy_baseline(
        list(zip(d_ids, d_vals)),
        list(zip(c_ids, c_vals)),
    )
    best_txs: List[Tuple[int, int, int]] = greedy_txs
    best_count = len(greedy_txs)

    n_d = len(d_vals)
    n_c = len(c_vals)

    def count_nonzero(arr: List[int]) -> int:
        return sum(1 for v in arr if v > 0)

    def backtrack(d_idx: int, c_start: int, current_txs: List[Tuple[int, int, int]]):
        nonlocal best_txs, best_count

        while d_idx < n_d and d_vals[d_idx] == 0:
            d_idx += 1
            c_start = 0

        if d_idx == n_d:
            if len(current_txs) < best_count:
                best_count = len(current_txs)
                best_txs = list(current_txs)
            return

        rem_d_cnt = count_nonzero(d_vals[d_idx:])
        rem_c_cnt = count_nonzero(c_vals)
        lower_bound = max(rem_d_cnt, rem_c_cnt)
        if len(current_txs) + lower_bound >= best_count:
            return

        need = d_vals[d_idx]
        seen_c_vals = set()

        # Prioritize exact match if available among remaining creditors
        for ci in range(c_start, n_c):
            if c_vals[ci] == need:
                c_vals[ci] = 0
                d_vals[d_idx] = 0
                current_txs.append((d_ids[d_idx], c_ids[ci], need))
                backtrack(d_idx + 1, 0, current_txs)
                current_txs.pop()
                d_vals[d_idx] = need
                c_vals[ci] = need
                return

        for ci in range(c_start, n_c):
            avail = c_vals[ci]
            if avail == 0 or avail in seen_c_vals:
                continue
            seen_c_vals.add(avail)

            transfer = need if need < avail else avail
            d_vals[d_idx] -= transfer
            c_vals[ci] -= transfer
            current_txs.append((d_ids[d_idx], c_ids[ci], transfer))

            if d_vals[d_idx] == 0:
                backtrack(d_idx + 1, 0, current_txs)
            else:
                backtrack(d_idx, ci + 1, current_txs)

            current_txs.pop()
            d_vals[d_idx] += transfer
            c_vals[ci] += transfer

    backtrack(0, 0, [])

    result = list(fixed_txs)
    for from_id, to_id, amt in best_txs:
        if amt > 0 and from_id != to_id:
            result.append(
                {
                    "from_member_id": from_id,
                    "to_member_id": to_id,
                    "amount_paise": amt,
                }
            )
    return result


def _greedy_baseline(
    debtors: List[Tuple[int, int]],
    creditors: List[Tuple[int, int]],
) -> List[Tuple[int, int, int]]:
    d = [[mid, amt] for mid, amt in debtors if amt > 0]
    c = [[mid, amt] for mid, amt in creditors if amt > 0]
    txs: List[Tuple[int, int, int]] = []
    i, j = 0, 0
    while i < len(d) and j < len(c):
        amt = min(d[i][1], c[j][1])
        if amt > 0:
            txs.append((d[i][0], c[j][0], amt))
            d[i][1] -= amt
            c[j][1] -= amt
        if d[i][1] == 0:
            i += 1
        if c[j][1] == 0:
            j += 1
    return txs
