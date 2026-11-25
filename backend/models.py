from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from backend.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    destination = Column(String(160), nullable=False)
    start_date = Column(String(20), nullable=False)
    end_date = Column(String(20), nullable=False)
    currency = Column(String(10), nullable=False, default="INR")
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    members = relationship(
        "Member",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="Member.id",
    )
    expenses = relationship(
        "Expense",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="Expense.expense_date.desc(), Expense.id.desc()",
    )
    settlements = relationship(
        "Settlement",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="Settlement.id",
    )
    notifications = relationship(
        "Notification",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="Notification.created_at.desc(), Notification.id.desc()",
    )
    email_deliveries = relationship(
        "EmailDelivery",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="EmailDelivery.created_at.desc(), EmailDelivery.id.desc()",
    )


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    trip = relationship("Trip", back_populates="members")
    paid_expenses = relationship("Expense", back_populates="payer", foreign_keys="Expense.payer_id")
    expense_shares = relationship("ExpenseShare", back_populates="member")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    amount_paise = Column(Integer, nullable=False)
    category = Column(String(60), nullable=False)
    expense_date = Column(String(20), nullable=False)
    payer_id = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, index=True)
    split_method = Column(String(20), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    trip = relationship("Trip", back_populates="expenses")
    payer = relationship("Member", back_populates="paid_expenses", foreign_keys=[payer_id])
    shares = relationship(
        "ExpenseShare",
        back_populates="expense",
        cascade="all, delete-orphan",
        order_by="ExpenseShare.id",
    )


class ExpenseShare(Base):
    __tablename__ = "expense_shares"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, index=True)
    share_paise = Column(Integer, nullable=False)
    percentage_bps = Column(Integer, nullable=True)

    expense = relationship("Expense", back_populates="shares")
    member = relationship("Member", back_populates="expense_shares")


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    from_member_id = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False)
    to_member_id = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False)
    amount_paise = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="suggested")
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    trip = relationship("Trip", back_populates="settlements")
    from_member = relationship("Member", foreign_keys=[from_member_id])
    to_member = relationship("Member", foreign_keys=[to_member_id])


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String(40), nullable=False)
    title = Column(String(160), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    trip = relationship("Trip", back_populates="notifications")


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    recipient_name = Column(String(120), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    html_body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False)
    provider = Column(String(30), nullable=False)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    trip = relationship("Trip", back_populates="email_deliveries")
    member = relationship("Member")
