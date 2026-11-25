from collections import defaultdict
from typing import Dict, List
from backend.finance import VALID_CATEGORIES, calculate_member_balances, format_inr


def compute_trip_analytics(trip, members: List, expenses: List, completed_settlements: List) -> Dict:
    total_spend_paise = sum(e.amount_paise for e in expenses)
    expense_count = len(expenses)
    avg_expense_paise = total_spend_paise // expense_count if expense_count > 0 else 0

    category_totals: Dict[str, int] = defaultdict(int)
    category_counts: Dict[str, int] = defaultdict(int)
    split_method_counts: Dict[str, int] = defaultdict(int)
    split_method_totals: Dict[str, int] = defaultdict(int)
    daily_totals: Dict[str, int] = defaultdict(int)

    personal_count = 0
    payer_excluded_count = 0
    largest_expense = None

    for exp in expenses:
        category_totals[exp.category] += exp.amount_paise
        category_counts[exp.category] += 1
        split_method_counts[exp.split_method] += 1
        split_method_totals[exp.split_method] += exp.amount_paise
        daily_totals[exp.expense_date] += exp.amount_paise

        participant_ids = {s.member_id for s in exp.shares}
        if len(participant_ids) == 1 and exp.payer_id in participant_ids:
            personal_count += 1
        if exp.payer_id not in participant_ids:
            payer_excluded_count += 1

        if largest_expense is None or exp.amount_paise > largest_expense["amount_paise"]:
            largest_expense = {
                "id": exp.id,
                "title": exp.title,
                "amount_paise": exp.amount_paise,
                "category": exp.category,
                "expense_date": exp.expense_date,
                "payer_name": exp.payer.name if exp.payer else "Unknown",
            }

    categories_sorted = sorted(
        [
            {
                "category": cat,
                "amount_paise": amt,
                "count": category_counts[cat],
                "percentage": round((amt / total_spend_paise) * 100, 1) if total_spend_paise > 0 else 0.0,
            }
            for cat, amt in category_totals.items()
        ],
        key=lambda x: (-x["amount_paise"], x["category"]),
    )

    highest_category = categories_sorted[0] if categories_sorted else None

    balances = calculate_member_balances(members, expenses, completed_settlements)
    member_contributions = sorted(
        balances,
        key=lambda b: (-b["total_paid_paise"], b["member_name"]),
    )

    most_frequent_payer = None
    if balances:
        top_payer = max(
            balances,
            key=lambda b: (b["expenses_paid_count"], b["total_paid_paise"]),
        )
        if top_payer["expenses_paid_count"] > 0:
            most_frequent_payer = {
                "member_id": top_payer["member_id"],
                "member_name": top_payer["member_name"],
                "expenses_paid_count": top_payer["expenses_paid_count"],
                "total_paid_paise": top_payer["total_paid_paise"],
            }

    daily_spending = [
        {"date": d, "amount_paise": daily_totals[d]}
        for d in sorted(daily_totals.keys())
    ]

    split_breakdown = [
        {
            "method": m,
            "count": split_method_counts[m],
            "amount_paise": split_method_totals[m],
        }
        for m in sorted(split_method_counts.keys())
    ]

    insights: List[str] = []
    if highest_category:
        insights.append(
            f"{highest_category['category']} accounts for {highest_category['percentage']}% of trip expenditure ({format_inr(highest_category['amount_paise'])} across {highest_category['count']} expenses)."
        )
    if most_frequent_payer:
        insights.append(
            f"{most_frequent_payer['member_name']} paid for the most expenses ({most_frequent_payer['expenses_paid_count']} payments totaling {format_inr(most_frequent_payer['total_paid_paise'])})."
        )
    if personal_count > 0:
        insights.append(
            f"{personal_count} personal expense(s) and {payer_excluded_count} payer-excluded expense(s) are tracked with zero cross-charging."
        )
    if members and total_spend_paise > 0:
        per_person_avg = total_spend_paise // len(members)
        insights.append(
            f"Average spend across {len(members)} members is {format_inr(per_person_avg)} per person."
        )

    return {
        "trip_id": trip.id,
        "total_spend_paise": total_spend_paise,
        "expense_count": expense_count,
        "average_expense_paise": avg_expense_paise,
        "member_count": len(members),
        "highest_category": highest_category,
        "most_frequent_payer": most_frequent_payer,
        "largest_expense": largest_expense,
        "personal_expense_count": personal_count,
        "payer_excluded_count": payer_excluded_count,
        "category_breakdown": categories_sorted,
        "member_contributions": member_contributions,
        "daily_spending": daily_spending,
        "split_breakdown": split_breakdown,
        "insights": insights,
        "all_categories": VALID_CATEGORIES,
    }
