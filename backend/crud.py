from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session, joinedload

from backend.analytics import compute_trip_analytics
from backend.email_service import render_member_summary_html, send_email_message
from backend.finance import (
    VALID_CATEGORIES,
    calculate_member_balances,
    compute_split_shares,
    format_inr,
)
from backend.models import (
    EmailDelivery,
    Expense,
    ExpenseShare,
    Member,
    Notification,
    Settlement,
    Trip,
)
from backend.settlement import compute_minimum_settlements


def utc_now():
    return datetime.now(timezone.utc)


def get_trip_or_raise(db: Session, trip_id: int) -> Trip:
    trip = (
        db.query(Trip)
        .options(
            joinedload(Trip.members),
            joinedload(Trip.expenses).joinedload(Expense.shares),
            joinedload(Trip.expenses).joinedload(Expense.payer),
            joinedload(Trip.settlements).joinedload(Settlement.from_member),
            joinedload(Trip.settlements).joinedload(Settlement.to_member),
        )
        .filter(Trip.id == trip_id)
        .first()
    )
    if not trip:
        raise LookupError(f"Trip {trip_id} not found.")
    return trip


def assert_trip_active(trip: Trip):
    if trip.status == "completed":
        raise PermissionError("Trip is completed and read-only. Reopen the trip to make changes.")


def create_notification(
    db: Session,
    trip_id: Optional[int],
    notif_type: str,
    title: str,
    message: str,
) -> Notification:
    notif = Notification(
        trip_id=trip_id,
        type=notif_type,
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notif)
    return notif


def recalculate_trip_settlements(db: Session, trip_id: int) -> List[Dict]:
    members = db.query(Member).filter(Member.trip_id == trip_id).order_by(Member.id).all()
    expenses = (
        db.query(Expense)
        .options(joinedload(Expense.shares))
        .populate_existing()
        .filter(Expense.trip_id == trip_id)
        .all()
    )
    completed_settlements = (
        db.query(Settlement)
        .filter(Settlement.trip_id == trip_id, Settlement.status == "completed")
        .all()
    )

    balances = calculate_member_balances(members, expenses, completed_settlements)
    remaining_map = {b["member_id"]: b["remaining_net_paise"] for b in balances}

    old_suggested = (
        db.query(Settlement)
        .filter(Settlement.trip_id == trip_id, Settlement.status == "suggested")
        .all()
    )
    for old_st in old_suggested:
        db.delete(old_st)
    db.flush()

    suggested = compute_minimum_settlements(remaining_map)
    for tx in suggested:
        db.add(
            Settlement(
                trip_id=trip_id,
                from_member_id=tx["from_member_id"],
                to_member_id=tx["to_member_id"],
                amount_paise=tx["amount_paise"],
                status="suggested",
            )
        )
    db.flush()
    db.expire_all()
    return balances


def create_trip(db: Session, data: Dict) -> Trip:
    members_input = data.get("members", [])
    if len(members_input) < 2:
        raise ValueError("A trip requires at least 2 members.")

    clean_name = data["name"].strip()
    clean_dest = (data.get("destination") or "").strip() or clean_name
    clean_start = data["start_date"].strip()
    clean_end = (data.get("end_date") or "").strip() or clean_start

    trip = Trip(
        name=clean_name,
        destination=clean_dest,
        start_date=clean_start,
        end_date=clean_end,
        currency=data.get("currency", "INR").strip() or "INR",
        status="active",
    )
    db.add(trip)
    db.flush()

    seen_emails = set()
    for m in members_input:
        name = m["name"].strip()
        email = m["email"].strip().lower()
        if not name or not email:
            raise ValueError("Each member must have both a name and an email address.")
        if email in seen_emails:
            raise ValueError(f"Duplicate member email: {email}")
        seen_emails.add(email)
        db.add(Member(trip_id=trip.id, name=name, email=email))

    create_notification(
        db,
        trip.id,
        "trip_created",
        f"Trip created: {trip.name}",
        f"{trip.name} was created with {len(members_input)} members.",
    )
    db.commit()
    return get_trip_or_raise(db, trip.id)


def update_trip(db: Session, trip_id: int, data: Dict) -> Trip:
    trip = get_trip_or_raise(db, trip_id)
    assert_trip_active(trip)

    if "name" in data and data["name"] is not None:
        trip.name = data["name"].strip()
        if "destination" not in data or not data.get("destination"):
            trip.destination = trip.name
    if "destination" in data and data["destination"] is not None and data["destination"].strip():
        trip.destination = data["destination"].strip()
    if "start_date" in data and data["start_date"] is not None:
        trip.start_date = data["start_date"].strip()
        if "end_date" not in data or not data.get("end_date"):
            trip.end_date = trip.start_date
    if "end_date" in data and data["end_date"] is not None and data["end_date"].strip():
        trip.end_date = data["end_date"].strip()

    db.commit()
    return get_trip_or_raise(db, trip_id)


def delete_trip(db: Session, trip_id: int):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise LookupError(f"Trip {trip_id} not found.")
    db.delete(trip)
    db.commit()


def add_member(db: Session, trip_id: int, name: str, email: str) -> Member:
    trip = get_trip_or_raise(db, trip_id)
    assert_trip_active(trip)

    clean_name = name.strip()
    clean_email = email.strip().lower()
    if not clean_name or not clean_email:
        raise ValueError("Member name and email are required.")

    for existing in trip.members:
        if existing.email.lower() == clean_email:
            raise ValueError(f"A member with email {clean_email} already exists in this trip.")

    member = Member(trip_id=trip_id, name=clean_name, email=clean_email)
    db.add(member)
    db.flush()

    create_notification(
        db,
        trip_id,
        "member_added",
        f"Member added: {clean_name}",
        f"{clean_name} ({clean_email}) joined {trip.name}.",
    )
    recalculate_trip_settlements(db, trip_id)
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, trip_id: int, member_id: int):
    trip = get_trip_or_raise(db, trip_id)
    assert_trip_active(trip)

    member = next((m for m in trip.members if m.id == member_id), None)
    if not member:
        raise LookupError(f"Member {member_id} not found in trip {trip_id}.")

    if len(trip.members) <= 2:
        raise ValueError("A trip must keep at least 2 members.")

    paid_count = db.query(Expense).filter(Expense.trip_id == trip_id, Expense.payer_id == member_id).count()
    share_count = (
        db.query(ExpenseShare)
        .join(Expense, Expense.id == ExpenseShare.expense_id)
        .filter(Expense.trip_id == trip_id, ExpenseShare.member_id == member_id)
        .count()
    )
    completed_settlement_count = (
        db.query(Settlement)
        .filter(
            Settlement.trip_id == trip_id,
            Settlement.status == "completed",
            (Settlement.from_member_id == member_id) | (Settlement.to_member_id == member_id),
        )
        .count()
    )

    if paid_count > 0 or share_count > 0 or completed_settlement_count > 0:
        raise ValueError(
            f"Cannot remove {member.name} because they are linked to {paid_count} paid expenses, {share_count} expense shares, or {completed_settlement_count} completed settlements."
        )

    db.delete(member)
    db.flush()
    recalculate_trip_settlements(db, trip_id)
    create_notification(
        db,
        trip_id,
        "member_removed",
        f"Member removed: {member.name}",
        f"{member.name} was removed from {trip.name}.",
    )
    db.commit()


def create_expense(db: Session, trip_id: int, data: Dict) -> Expense:
    trip = get_trip_or_raise(db, trip_id)
    assert_trip_active(trip)

    valid_member_ids = {m.id for m in trip.members}
    payer_id = data["payer_id"]
    if payer_id not in valid_member_ids:
        raise ValueError("Selected payer does not belong to this trip.")

    category = data["category"].strip()
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(VALID_CATEGORIES)}")

    shares = compute_split_shares(
        amount_paise=data["amount_paise"],
        split_method=data["split_method"],
        participants=data["participants"],
        valid_member_ids=valid_member_ids,
    )

    expense = Expense(
        trip_id=trip_id,
        title=data["title"].strip(),
        amount_paise=data["amount_paise"],
        category=category,
        expense_date=data["expense_date"].strip(),
        payer_id=payer_id,
        split_method=data["split_method"],
        notes=(data.get("notes") or "").strip() or None,
    )
    db.add(expense)
    db.flush()

    for s in shares:
        db.add(
            ExpenseShare(
                expense_id=expense.id,
                member_id=s["member_id"],
                share_paise=s["share_paise"],
                percentage_bps=s["percentage_bps"],
            )
        )
    db.flush()

    payer_name = next((m.name for m in trip.members if m.id == payer_id), "Member")
    recalculate_trip_settlements(db, trip_id)
    create_notification(
        db,
        trip_id,
        "expense_added",
        f"Expense added: {expense.title}",
        f"{payer_name} paid {format_inr(expense.amount_paise)} for {expense.title} ({len(shares)} participants). Balances recalculated.",
    )
    db.commit()
    return (
        db.query(Expense)
        .options(joinedload(Expense.shares), joinedload(Expense.payer))
        .filter(Expense.id == expense.id)
        .first()
    )


def update_expense(db: Session, trip_id: int, expense_id: int, data: Dict) -> Expense:
    trip = get_trip_or_raise(db, trip_id)
    assert_trip_active(trip)

    expense = (
        db.query(Expense)
        .options(joinedload(Expense.shares))
        .filter(Expense.id == expense_id, Expense.trip_id == trip_id)
        .first()
    )
    if not expense:
        raise LookupError(f"Expense {expense_id} not found in trip {trip_id}.")

    valid_member_ids = {m.id for m in trip.members}
    payer_id = data["payer_id"]
    if payer_id not in valid_member_ids:
        raise ValueError("Selected payer does not belong to this trip.")

    category = data["category"].strip()
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(VALID_CATEGORIES)}")

    shares = compute_split_shares(
        amount_paise=data["amount_paise"],
        split_method=data["split_method"],
        participants=data["participants"],
        valid_member_ids=valid_member_ids,
    )

    expense.title = data["title"].strip()
    expense.amount_paise = data["amount_paise"]
    expense.category = category
    expense.expense_date = data["expense_date"].strip()
    expense.payer_id = payer_id
    expense.split_method = data["split_method"]
    expense.notes = (data.get("notes") or "").strip() or None
    expense.updated_at = utc_now()

    expense.shares.clear()
    db.flush()
    for s in shares:
        expense.shares.append(
            ExpenseShare(
                member_id=s["member_id"],
                share_paise=s["share_paise"],
                percentage_bps=s["percentage_bps"],
            )
        )
    db.flush()

    recalculate_trip_settlements(db, trip_id)
    create_notification(
        db,
        trip_id,
        "expense_updated",
        f"Expense updated: {expense.title}",
        f"{expense.title} was updated to {format_inr(expense.amount_paise)} ({expense.split_method} split). Balances and settlements updated.",
    )
    db.commit()
    return (
        db.query(Expense)
        .options(joinedload(Expense.shares), joinedload(Expense.payer))
        .filter(Expense.id == expense.id)
        .first()
    )


def delete_expense(db: Session, trip_id: int, expense_id: int):
    trip = get_trip_or_raise(db, trip_id)
    assert_trip_active(trip)

    expense = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.trip_id == trip_id)
        .first()
    )
    if not expense:
        raise LookupError(f"Expense {expense_id} not found in trip {trip_id}.")

    title = expense.title
    amt = expense.amount_paise
    db.delete(expense)
    db.flush()

    recalculate_trip_settlements(db, trip_id)
    create_notification(
        db,
        trip_id,
        "expense_deleted",
        f"Expense deleted: {title}",
        f"Removed {title} ({format_inr(amt)}) from {trip.name}. Balances recalculated.",
    )
    db.commit()


def mark_settlement_completed(db: Session, trip_id: int, settlement_id: int) -> Settlement:
    trip = get_trip_or_raise(db, trip_id)
    assert_trip_active(trip)

    settlement = (
        db.query(Settlement)
        .filter(Settlement.id == settlement_id, Settlement.trip_id == trip_id)
        .first()
    )
    if not settlement:
        raise LookupError(f"Settlement {settlement_id} not found in trip {trip_id}.")
    if settlement.status == "completed":
        raise ValueError("Settlement is already marked as completed.")

    settlement.status = "completed"
    settlement.completed_at = utc_now()
    db.flush()

    from_name = next((m.name for m in trip.members if m.id == settlement.from_member_id), "Member")
    to_name = next((m.name for m in trip.members if m.id == settlement.to_member_id), "Member")

    recalculate_trip_settlements(db, trip_id)
    create_notification(
        db,
        trip_id,
        "settlement_completed",
        "Settlement recorded",
        f"{from_name} paid {to_name} {format_inr(settlement.amount_paise)}.",
    )
    db.commit()
    db.refresh(settlement)
    return settlement


def reopen_completed_settlement(db: Session, trip_id: int, settlement_id: int):
    trip = get_trip_or_raise(db, trip_id)
    assert_trip_active(trip)

    settlement = (
        db.query(Settlement)
        .filter(Settlement.id == settlement_id, Settlement.trip_id == trip_id)
        .first()
    )
    if not settlement:
        raise LookupError(f"Settlement {settlement_id} not found in trip {trip_id}.")
    if settlement.status != "completed":
        raise ValueError("Only completed settlements can be reverted.")

    db.delete(settlement)
    db.flush()
    recalculate_trip_settlements(db, trip_id)
    create_notification(
        db,
        trip_id,
        "balance_update",
        "Completed settlement reverted",
        f"A recorded payment of {format_inr(settlement.amount_paise)} in {trip.name} was marked unpaid.",
    )
    db.commit()


def send_settlement_reminders(db: Session, trip_id: int) -> List[Notification]:
    trip = get_trip_or_raise(db, trip_id)
    suggested = [s for s in trip.settlements if s.status == "suggested"]
    created = []
    if not suggested:
        notif = create_notification(
            db,
            trip_id,
            "settlement_reminder",
            f"All settled: {trip.name}",
            f"Everyone in {trip.name} has a zero remaining balance.",
        )
        created.append(notif)
    else:
        for s in suggested:
            from_name = s.from_member.name if s.from_member else "Member"
            to_name = s.to_member.name if s.to_member else "Member"
            notif = create_notification(
                db,
                trip_id,
                "settlement_reminder",
                f"Settlement reminder: {from_name} to {to_name}",
                f"Reminder for {trip.name}: {from_name} owes {to_name} {format_inr(s.amount_paise)}.",
            )
            created.append(notif)
    db.commit()
    return created


def end_trip_and_send_emails(db: Session, trip_id: int) -> Dict:
    trip = get_trip_or_raise(db, trip_id)
    if trip.status == "completed":
        raise ValueError("Trip is already completed.")

    # Recalculate final consolidated balances and suggested settlements
    # without marking any suggested payments as completed.
    balances = recalculate_trip_settlements(db, trip_id)
    db.flush()

    trip = get_trip_or_raise(db, trip_id)
    completed_settlements = [s for s in trip.settlements if s.status == "completed"]
    suggested_settlements = [s for s in trip.settlements if s.status == "suggested"]

    suggested_dicts = [
        {
            "from_member_id": s.from_member_id,
            "to_member_id": s.to_member_id,
            "amount_paise": s.amount_paise,
        }
        for s in suggested_settlements
    ]
    completed_dicts = [
        {
            "from_member_id": s.from_member_id,
            "to_member_id": s.to_member_id,
            "amount_paise": s.amount_paise,
        }
        for s in completed_settlements
    ]

    member_map = {m.id: m.name for m in trip.members}
    analytics = compute_trip_analytics(trip, trip.members, trip.expenses, completed_settlements)

    deliveries: List[EmailDelivery] = []
    for bal in balances:
        subject, html_body = render_member_summary_html(
            trip=trip,
            member_balance=bal,
            suggested_settlements=suggested_dicts,
            completed_settlements=completed_dicts,
            member_map=member_map,
            total_trip_spend_paise=analytics["total_spend_paise"],
            expense_count=analytics["expense_count"],
            category_breakdown=analytics["category_breakdown"],
            all_balances=balances,
        )
        result = send_email_message(
            to_email=bal["member_email"],
            subject=subject,
            html_body=html_body,
        )
        delivery = EmailDelivery(
            trip_id=trip.id,
            member_id=bal["member_id"],
            recipient_name=bal["member_name"],
            recipient_email=bal["member_email"],
            subject=subject,
            html_body=html_body,
            status=result["status"],
            provider=result["provider"],
            error_message=result["error_message"],
            sent_at=result["sent_at"],
        )
        db.add(delivery)
        deliveries.append(delivery)

    trip.status = "completed"
    trip.completed_at = utc_now()

    sent_count = sum(1 for d in deliveries if d.status == "sent")
    demo_count = sum(1 for d in deliveries if d.status == "demo")
    failed_count = sum(1 for d in deliveries if d.status == "failed")

    if demo_count == len(deliveries):
        summary_msg = (
            f"{trip.name} marked completed (read-only). Generated {demo_count} personalized HTML summaries in Demo Mode."
        )
    elif failed_count > 0:
        summary_msg = (
            f"{trip.name} marked completed (read-only). {sent_count} emails sent, {failed_count} failed."
        )
    else:
        summary_msg = (
            f"{trip.name} marked completed (read-only). Sent {sent_count} personalized settlement emails."
        )

    create_notification(
        db,
        trip.id,
        "trip_completed",
        f"Trip ended: {trip.name}",
        summary_msg,
    )
    db.commit()
    return {
        "trip": get_trip_or_raise(db, trip.id),
        "deliveries": deliveries,
    }


def resend_email_delivery(db: Session, trip_id: int, delivery_id: int) -> EmailDelivery:
    delivery = (
        db.query(EmailDelivery)
        .filter(EmailDelivery.id == delivery_id, EmailDelivery.trip_id == trip_id)
        .first()
    )
    if not delivery:
        raise LookupError(f"Email delivery {delivery_id} not found.")

    result = send_email_message(
        to_email=delivery.recipient_email,
        subject=delivery.subject,
        html_body=delivery.html_body,
    )
    delivery.status = result["status"]
    delivery.provider = result["provider"]
    delivery.error_message = result["error_message"]
    delivery.sent_at = result["sent_at"]
    db.commit()
    db.refresh(delivery)
    return delivery


def reopen_trip(db: Session, trip_id: int) -> Trip:
    trip = get_trip_or_raise(db, trip_id)
    if trip.status != "completed":
        raise ValueError("Trip is already active.")

    trip.status = "active"
    trip.completed_at = None
    create_notification(
        db,
        trip.id,
        "trip_reopened",
        f"Trip reopened: {trip.name}",
        f"{trip.name} was reopened for editing.",
    )
    db.commit()
    return get_trip_or_raise(db, trip_id)
