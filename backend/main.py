import re
from contextlib import asynccontextmanager
from typing import Dict, List
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from backend import crud
from backend.analytics import compute_trip_analytics
from backend.database import Base, engine, get_db
from backend.email_service import get_email_provider_status
from backend.finance import calculate_member_balances
from backend.models import EmailDelivery, Expense, Member, Notification, Settlement, Trip
from backend.schemas import ExpenseCreate, ExpenseUpdate, MemberCreate, TripCreate, TripUpdate


def init_db():
    Base.metadata.create_all(bind=engine)


init_db()

app = FastAPI(title="TripLedger API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _handle_domain_error(exc: Exception):
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


def _serialize_expense(exp: Expense, member_map: Dict[int, str]) -> Dict:
    return {
        "id": exp.id,
        "trip_id": exp.trip_id,
        "title": exp.title,
        "amount_paise": exp.amount_paise,
        "category": exp.category,
        "expense_date": exp.expense_date,
        "payer_id": exp.payer_id,
        "payer_name": member_map.get(exp.payer_id, exp.payer.name if exp.payer else "Unknown"),
        "split_method": exp.split_method,
        "notes": exp.notes,
        "created_at": exp.created_at.isoformat() if exp.created_at else None,
        "updated_at": exp.updated_at.isoformat() if exp.updated_at else None,
        "shares": [
            {
                "id": sh.id,
                "member_id": sh.member_id,
                "member_name": member_map.get(sh.member_id, "Unknown"),
                "share_paise": sh.share_paise,
                "percentage_bps": sh.percentage_bps,
            }
            for sh in exp.shares
        ],
    }


def _serialize_settlement(st: Settlement, member_map: Dict[int, str]) -> Dict:
    return {
        "id": st.id,
        "trip_id": st.trip_id,
        "from_member_id": st.from_member_id,
        "from_member_name": member_map.get(st.from_member_id, "Unknown"),
        "to_member_id": st.to_member_id,
        "to_member_name": member_map.get(st.to_member_id, "Unknown"),
        "amount_paise": st.amount_paise,
        "status": st.status,
        "completed_at": st.completed_at.isoformat() if st.completed_at else None,
        "created_at": st.created_at.isoformat() if st.created_at else None,
    }


def _serialize_email_delivery(d: EmailDelivery) -> Dict:
    return {
        "id": d.id,
        "trip_id": d.trip_id,
        "member_id": d.member_id,
        "recipient_name": d.recipient_name,
        "recipient_email": d.recipient_email,
        "subject": d.subject,
        "html_body": d.html_body,
        "status": d.status,
        "provider": d.provider,
        "error_message": d.error_message,
        "sent_at": d.sent_at.isoformat() if d.sent_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _serialize_trip_summary(trip: Trip) -> Dict:
    completed_settlements = [s for s in trip.settlements if s.status == "completed"]
    suggested_settlements = [s for s in trip.settlements if s.status == "suggested"]
    total_spend_paise = sum(e.amount_paise for e in trip.expenses)
    pending_settlement_paise = sum(s.amount_paise for s in suggested_settlements)
    return {
        "id": trip.id,
        "name": trip.name,
        "destination": trip.destination,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "currency": trip.currency,
        "status": trip.status,
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
        "completed_at": trip.completed_at.isoformat() if trip.completed_at else None,
        "member_count": len(trip.members),
        "expense_count": len(trip.expenses),
        "total_spend_paise": total_spend_paise,
        "pending_settlement_paise": pending_settlement_paise,
        "suggested_settlement_count": len(suggested_settlements),
        "completed_settlement_count": len(completed_settlements),
    }


def _serialize_trip_detail(db: Session, trip: Trip) -> Dict:
    member_map = {m.id: m.name for m in trip.members}
    completed_settlements = [s for s in trip.settlements if s.status == "completed"]
    suggested_settlements = [s for s in trip.settlements if s.status == "suggested"]
    balances = calculate_member_balances(trip.members, trip.expenses, completed_settlements)
    analytics = compute_trip_analytics(trip, trip.members, trip.expenses, completed_settlements)
    deliveries = (
        db.query(EmailDelivery)
        .filter(EmailDelivery.trip_id == trip.id)
        .order_by(EmailDelivery.id.asc())
        .all()
    )

    return {
        **_serialize_trip_summary(trip),
        "members": [
            {
                "id": m.id,
                "trip_id": m.trip_id,
                "name": m.name,
                "email": m.email,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in trip.members
        ],
        "expenses": [_serialize_expense(e, member_map) for e in trip.expenses],
        "balances": balances,
        "settlements": {
            "suggested": [_serialize_settlement(s, member_map) for s in suggested_settlements],
            "completed": [_serialize_settlement(s, member_map) for s in completed_settlements],
        },
        "analytics": analytics,
        "email_deliveries": [_serialize_email_delivery(d) for d in deliveries],
        "email_provider": get_email_provider_status(),
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "email_provider": get_email_provider_status()}


@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    trips = (
        db.query(Trip)
        .options(
            joinedload(Trip.members),
            joinedload(Trip.expenses).joinedload(Expense.shares),
            joinedload(Trip.expenses).joinedload(Expense.payer),
            joinedload(Trip.settlements),
        )
        .order_by(Trip.start_date.desc(), Trip.id.desc())
        .all()
    )

    trip_summaries = [_serialize_trip_summary(t) for t in trips]
    total_expenditure_paise = sum(t["total_spend_paise"] for t in trip_summaries)
    total_pending_paise = sum(t["pending_settlement_paise"] for t in trip_summaries)
    pending_count = sum(t["suggested_settlement_count"] for t in trip_summaries)
    completed_count = sum(t["completed_settlement_count"] for t in trip_summaries)

    all_expenses: List[Dict] = []
    category_map: Dict[str, int] = {}
    for t in trips:
        member_map = {m.id: m.name for m in t.members}
        for e in t.expenses:
            category_map[e.category] = category_map.get(e.category, 0) + e.amount_paise
            all_expenses.append(
                {
                    "id": e.id,
                    "trip_id": t.id,
                    "trip_name": t.name,
                    "trip_destination": t.destination,
                    "title": e.title,
                    "amount_paise": e.amount_paise,
                    "category": e.category,
                    "expense_date": e.expense_date,
                    "payer_name": member_map.get(e.payer_id, "Unknown"),
                    "split_method": e.split_method,
                    "participant_count": len(e.shares),
                }
            )

    all_expenses.sort(key=lambda x: (x["expense_date"], x["id"]), reverse=True)
    category_totals = sorted(
        [{"category": k, "amount_paise": v} for k, v in category_map.items()],
        key=lambda x: -x["amount_paise"],
    )

    unread_notifications_count = (
        db.query(Notification).filter(Notification.is_read == False).count()
    )

    return {
        "total_trips": len(trips),
        "active_trips": sum(1 for t in trips if t.status == "active"),
        "completed_trips": sum(1 for t in trips if t.status == "completed"),
        "total_expenditure_paise": total_expenditure_paise,
        "total_owed_paise": total_pending_paise,
        "total_receivable_paise": total_pending_paise,
        "pending_settlement_count": pending_count,
        "completed_settlement_count": completed_count,
        "unread_notifications_count": unread_notifications_count,
        "email_provider": get_email_provider_status(),
        "trips": trip_summaries,
        "recent_expenses": all_expenses[:12],
        "category_totals": category_totals,
    }


@app.get("/api/trips")
def list_trips(db: Session = Depends(get_db)):
    trips = (
        db.query(Trip)
        .options(
            joinedload(Trip.members),
            joinedload(Trip.expenses),
            joinedload(Trip.settlements),
        )
        .order_by(Trip.start_date.desc(), Trip.id.desc())
        .all()
    )
    return [_serialize_trip_summary(t) for t in trips]


@app.post("/api/trips", status_code=201)
def create_trip_endpoint(payload: TripCreate, db: Session = Depends(get_db)):
    try:
        trip = crud.create_trip(db, payload.dict())
        return _serialize_trip_detail(db, trip)
    except Exception as exc:
        _handle_domain_error(exc)


@app.get("/api/trips/{trip_id}")
def get_trip_endpoint(trip_id: int, db: Session = Depends(get_db)):
    try:
        trip = crud.get_trip_or_raise(db, trip_id)
        return _serialize_trip_detail(db, trip)
    except Exception as exc:
        _handle_domain_error(exc)


@app.patch("/api/trips/{trip_id}")
def update_trip_endpoint(trip_id: int, payload: TripUpdate, db: Session = Depends(get_db)):
    try:
        trip = crud.update_trip(db, trip_id, payload.dict(exclude_unset=True))
        return _serialize_trip_detail(db, trip)
    except Exception as exc:
        _handle_domain_error(exc)


@app.delete("/api/trips/{trip_id}")
def delete_trip_endpoint(trip_id: int, db: Session = Depends(get_db)):
    try:
        crud.delete_trip(db, trip_id)
        return {"deleted": True, "trip_id": trip_id}
    except Exception as exc:
        _handle_domain_error(exc)


@app.post("/api/trips/{trip_id}/members", status_code=201)
def add_member_endpoint(trip_id: int, payload: MemberCreate, db: Session = Depends(get_db)):
    try:
        member = crud.add_member(db, trip_id, payload.name, payload.email)
        return {
            "id": member.id,
            "trip_id": member.trip_id,
            "name": member.name,
            "email": member.email,
        }
    except Exception as exc:
        _handle_domain_error(exc)


@app.delete("/api/trips/{trip_id}/members/{member_id}")
def remove_member_endpoint(trip_id: int, member_id: int, db: Session = Depends(get_db)):
    try:
        crud.remove_member(db, trip_id, member_id)
        return {"deleted": True, "member_id": member_id}
    except Exception as exc:
        _handle_domain_error(exc)


@app.post("/api/trips/{trip_id}/expenses", status_code=201)
def create_expense_endpoint(trip_id: int, payload: ExpenseCreate, db: Session = Depends(get_db)):
    try:
        exp = crud.create_expense(db, trip_id, payload.dict())
        trip = crud.get_trip_or_raise(db, trip_id)
        member_map = {m.id: m.name for m in trip.members}
        return _serialize_expense(exp, member_map)
    except Exception as exc:
        _handle_domain_error(exc)


@app.put("/api/trips/{trip_id}/expenses/{expense_id}")
def update_expense_endpoint(
    trip_id: int, expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db)
):
    try:
        exp = crud.update_expense(db, trip_id, expense_id, payload.dict())
        trip = crud.get_trip_or_raise(db, trip_id)
        member_map = {m.id: m.name for m in trip.members}
        return _serialize_expense(exp, member_map)
    except Exception as exc:
        _handle_domain_error(exc)


@app.delete("/api/trips/{trip_id}/expenses/{expense_id}")
def delete_expense_endpoint(trip_id: int, expense_id: int, db: Session = Depends(get_db)):
    try:
        crud.delete_expense(db, trip_id, expense_id)
        return {"deleted": True, "expense_id": expense_id}
    except Exception as exc:
        _handle_domain_error(exc)


@app.get("/api/trips/{trip_id}/balances")
def get_balances_endpoint(trip_id: int, db: Session = Depends(get_db)):
    try:
        trip = crud.get_trip_or_raise(db, trip_id)
        completed = [s for s in trip.settlements if s.status == "completed"]
        return calculate_member_balances(trip.members, trip.expenses, completed)
    except Exception as exc:
        _handle_domain_error(exc)


@app.get("/api/trips/{trip_id}/settlements")
def get_settlements_endpoint(trip_id: int, db: Session = Depends(get_db)):
    try:
        trip = crud.get_trip_or_raise(db, trip_id)
        member_map = {m.id: m.name for m in trip.members}
        suggested = [s for s in trip.settlements if s.status == "suggested"]
        completed = [s for s in trip.settlements if s.status == "completed"]
        return {
            "suggested": [_serialize_settlement(s, member_map) for s in suggested],
            "completed": [_serialize_settlement(s, member_map) for s in completed],
        }
    except Exception as exc:
        _handle_domain_error(exc)


@app.post("/api/trips/{trip_id}/settlements/{settlement_id}/complete")
def complete_settlement_endpoint(trip_id: int, settlement_id: int, db: Session = Depends(get_db)):
    try:
        st = crud.mark_settlement_completed(db, trip_id, settlement_id)
        trip = crud.get_trip_or_raise(db, trip_id)
        member_map = {m.id: m.name for m in trip.members}
        return _serialize_settlement(st, member_map)
    except Exception as exc:
        _handle_domain_error(exc)


@app.delete("/api/trips/{trip_id}/settlements/{settlement_id}/complete")
def revert_settlement_endpoint(trip_id: int, settlement_id: int, db: Session = Depends(get_db)):
    try:
        crud.reopen_completed_settlement(db, trip_id, settlement_id)
        return {"reverted": True, "settlement_id": settlement_id}
    except Exception as exc:
        _handle_domain_error(exc)


@app.post("/api/trips/{trip_id}/settlements/remind")
def remind_settlements_endpoint(trip_id: int, db: Session = Depends(get_db)):
    try:
        created = crud.send_settlement_reminders(db, trip_id)
        return {"created_count": len(created)}
    except Exception as exc:
        _handle_domain_error(exc)


@app.get("/api/trips/{trip_id}/analytics")
def get_analytics_endpoint(trip_id: int, db: Session = Depends(get_db)):
    try:
        trip = crud.get_trip_or_raise(db, trip_id)
        completed = [s for s in trip.settlements if s.status == "completed"]
        return compute_trip_analytics(trip, trip.members, trip.expenses, completed)
    except Exception as exc:
        _handle_domain_error(exc)


@app.post("/api/trips/{trip_id}/end")
def end_trip_endpoint(trip_id: int, db: Session = Depends(get_db)):
    try:
        res = crud.end_trip_and_send_emails(db, trip_id)
        return _serialize_trip_detail(db, res["trip"])
    except Exception as exc:
        _handle_domain_error(exc)


@app.post("/api/trips/{trip_id}/reopen")
def reopen_trip_endpoint(trip_id: int, db: Session = Depends(get_db)):
    try:
        trip = crud.reopen_trip(db, trip_id)
        return _serialize_trip_detail(db, trip)
    except Exception as exc:
        _handle_domain_error(exc)


@app.get("/api/trips/{trip_id}/emails")
def list_emails_endpoint(trip_id: int, db: Session = Depends(get_db)):
    try:
        crud.get_trip_or_raise(db, trip_id)
        deliveries = (
            db.query(EmailDelivery)
            .filter(EmailDelivery.trip_id == trip_id)
            .order_by(EmailDelivery.id.asc())
            .all()
        )
        return {
            "email_provider": get_email_provider_status(),
            "deliveries": [_serialize_email_delivery(d) for d in deliveries],
        }
    except Exception as exc:
        _handle_domain_error(exc)


@app.post("/api/trips/{trip_id}/emails/{delivery_id}/resend")
def resend_email_endpoint(trip_id: int, delivery_id: int, db: Session = Depends(get_db)):
    try:
        d = crud.resend_email_delivery(db, trip_id, delivery_id)
        return _serialize_email_delivery(d)
    except Exception as exc:
        _handle_domain_error(exc)


@app.get("/api/trips/{trip_id}/emails/{delivery_id}/view")
def view_email_html(trip_id: int, delivery_id: int, db: Session = Depends(get_db)):
    delivery = (
        db.query(EmailDelivery)
        .filter(EmailDelivery.id == delivery_id, EmailDelivery.trip_id == trip_id)
        .first()
    )
    if not delivery:
        raise HTTPException(status_code=404, detail="Email summary not found.")
    return Response(
        content=delivery.html_body,
        media_type="text/html; charset=utf-8",
    )


@app.get("/api/trips/{trip_id}/emails/{delivery_id}/download")
def download_email_html(trip_id: int, delivery_id: int, db: Session = Depends(get_db)):
    delivery = (
        db.query(EmailDelivery)
        .filter(EmailDelivery.id == delivery_id, EmailDelivery.trip_id == trip_id)
        .first()
    )
    if not delivery:
        raise HTTPException(status_code=404, detail="Email summary not found.")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", delivery.recipient_name.strip()).strip("_") or "member"
    filename = f"tripledger_trip_{trip_id}_{safe_name}.html"
    return Response(
        content=delivery.html_body,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/notifications")
def list_notifications(db: Session = Depends(get_db)):
    rows = (
        db.query(Notification)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(80)
        .all()
    )
    unread_count = db.query(Notification).filter(Notification.is_read == False).count()
    return {
        "unread_count": unread_count,
        "items": [
            {
                "id": n.id,
                "trip_id": n.trip_id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in rows
        ],
    }


@app.post("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found.")
    n.is_read = True
    db.commit()
    return {"id": n.id, "is_read": True}


@app.post("/api/notifications/read-all")
def mark_all_notifications_read(db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"updated": True}
