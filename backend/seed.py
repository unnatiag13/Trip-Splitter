from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.analytics import compute_trip_analytics
from backend.crud import recalculate_trip_settlements
from backend.email_service import render_member_summary_html
from backend.finance import compute_split_shares, format_inr
from backend.models import (
    EmailDelivery,
    Expense,
    ExpenseShare,
    Member,
    Notification,
    Settlement,
    Trip,
)


def seed_database_if_empty(db: Session):
    if db.query(Trip).count() > 0:
        return

    trips_spec = [
        _build_goa_trip(),
        _build_jaipur_trip(),
        _build_manali_trip(),
        _build_coorg_trip(),
        _build_pondicherry_trip(),
    ]

    for spec in trips_spec:
        trip = Trip(
            name=spec["name"],
            destination=spec["destination"],
            start_date=spec["start_date"],
            end_date=spec["end_date"],
            currency="INR",
            status="active",
        )
        db.add(trip)
        db.flush()

        member_objs = []
        for name, email in spec["members"]:
            m = Member(trip_id=trip.id, name=name, email=email)
            db.add(m)
            member_objs.append(m)
        db.flush()

        valid_ids = {m.id for m in member_objs}

        for exp_spec in spec["expenses"]:
            payer = member_objs[exp_spec["payer_idx"]]
            participants_raw = []
            for p in exp_spec["participants"]:
                if isinstance(p, int):
                    participants_raw.append({"member_id": member_objs[p].id})
                else:
                    idx, val = p
                    if exp_spec["split_method"] == "custom":
                        participants_raw.append(
                            {"member_id": member_objs[idx].id, "share_paise": val}
                        )
                    elif exp_spec["split_method"] == "percentage":
                        participants_raw.append(
                            {"member_id": member_objs[idx].id, "percentage_bps": val}
                        )
                    else:
                        participants_raw.append({"member_id": member_objs[idx].id})

            shares = compute_split_shares(
                amount_paise=exp_spec["amount_paise"],
                split_method=exp_spec["split_method"],
                participants=participants_raw,
                valid_member_ids=valid_ids,
            )

            expense = Expense(
                trip_id=trip.id,
                title=exp_spec["title"],
                amount_paise=exp_spec["amount_paise"],
                category=exp_spec["category"],
                expense_date=exp_spec["date"],
                payer_id=payer.id,
                split_method=exp_spec["split_method"],
                notes=exp_spec.get("notes"),
            )
            db.add(expense)
            db.flush()

            for sh in shares:
                db.add(
                    ExpenseShare(
                        expense_id=expense.id,
                        member_id=sh["member_id"],
                        share_paise=sh["share_paise"],
                        percentage_bps=sh["percentage_bps"],
                    )
                )

        db.flush()

        # Optional pre-recorded completed settlements
        for from_idx, to_idx, amt in spec.get("completed_settlements", []):
            db.add(
                Settlement(
                    trip_id=trip.id,
                    from_member_id=member_objs[from_idx].id,
                    to_member_id=member_objs[to_idx].id,
                    amount_paise=amt,
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                )
            )

        balances = recalculate_trip_settlements(db, trip.id)
        db.flush()

        if spec["status"] == "completed":
            trip.status = "completed"
            trip.completed_at = datetime.now(timezone.utc)
            expenses_db = db.query(Expense).filter(Expense.trip_id == trip.id).all()
            completed_st = (
                db.query(Settlement)
                .filter(Settlement.trip_id == trip.id, Settlement.status == "completed")
                .all()
            )
            suggested_st = (
                db.query(Settlement)
                .filter(Settlement.trip_id == trip.id, Settlement.status == "suggested")
                .all()
            )
            member_map = {m.id: m.name for m in member_objs}
            analytics = compute_trip_analytics(trip, member_objs, expenses_db, completed_st)
            suggested_dicts = [
                {
                    "from_member_id": s.from_member_id,
                    "to_member_id": s.to_member_id,
                    "amount_paise": s.amount_paise,
                }
                for s in suggested_st
            ]
            completed_dicts = [
                {
                    "from_member_id": s.from_member_id,
                    "to_member_id": s.to_member_id,
                    "amount_paise": s.amount_paise,
                }
                for s in completed_st
            ]
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
                )
                db.add(
                    EmailDelivery(
                        trip_id=trip.id,
                        member_id=bal["member_id"],
                        recipient_name=bal["member_name"],
                        recipient_email=bal["member_email"],
                        subject=subject,
                        html_body=html_body,
                        status="demo",
                        provider="demo",
                        error_message="Generated during initial seed in Demo Mode.",
                    )
                )

        db.add(
            Notification(
                trip_id=trip.id,
                type="trip_completed" if spec["status"] == "completed" else "balance_update",
                title=f"{trip.name} ready",
                message=f"Seeded {len(spec['expenses'])} expenses across {len(member_objs)} members in {trip.destination}.",
                is_read=True,
            )
        )

    db.commit()


def _build_goa_trip():
    # 6 members, 28 expenses
    members = [
        ("Aarav Mehta", "aarav.mehta@example.com"),
        ("Meera Nair", "meera.nair@example.com"),
        ("Kabir Sharma", "kabir.sharma@example.com"),
        ("Riya Kulkarni", "riya.kulkarni@example.com"),
        ("Dev Malhotra", "dev.malhotra@example.com"),
        ("Sana Verma", "sana.verma@example.com"),
    ]
    all_6 = [0, 1, 2, 3, 4, 5]
    expenses = [
        {"title": "Beachfront Villa Deposit", "amount_paise": 3600000, "category": "Accommodation", "date": "2026-11-12", "payer_idx": 0, "split_method": "equal", "participants": all_6},
        {"title": "Mopa Airport SUV Transfers", "amount_paise": 420000, "category": "Transport", "date": "2026-11-12", "payer_idx": 1, "split_method": "equal", "participants": all_6},
        {"title": "Thalassa Sunset Dinner", "amount_paise": 1140000, "category": "Food", "date": "2026-11-12", "payer_idx": 2, "split_method": "custom", "participants": [(0, 210000), (1, 185000), (2, 225000), (3, 175000), (4, 195000), (5, 150000)]},
        {"title": "Scooter Rentals (3 Days)", "amount_paise": 360000, "category": "Transport", "date": "2026-11-13", "payer_idx": 4, "split_method": "equal", "participants": [0, 2, 3, 4, 5], "notes": "Meera shared cab instead of scooter"},
        {"title": "Gunpowder Assagao Lunch", "amount_paise": 685000, "category": "Food", "date": "2026-11-13", "payer_idx": 3, "split_method": "equal", "participants": all_6},
        {"title": "Grande Island Scuba Session", "amount_paise": 1400000, "category": "Activities", "date": "2026-11-13", "payer_idx": 0, "split_method": "equal", "participants": [0, 2, 4, 5], "notes": "4 divers"},
        {"title": "Anjuna Flea Market Crafts", "amount_paise": 280000, "category": "Shopping", "date": "2026-11-13", "payer_idx": 5, "split_method": "equal", "participants": [5], "notes": "Personal shopping expense"},
        {"title": "Villa Breakfast Groceries", "amount_paise": 295000, "category": "Food", "date": "2026-11-14", "payer_idx": 1, "split_method": "equal", "participants": all_6},
        {"title": "Kayaking at Cola Lagoon", "amount_paise": 480000, "category": "Activities", "date": "2026-11-14", "payer_idx": 2, "split_method": "equal", "participants": [1, 2, 3, 5]},
        {"title": "Panjim Cab for Meera & Kabir", "amount_paise": 165000, "category": "Transport", "date": "2026-11-14", "payer_idx": 0, "split_method": "equal", "participants": [1, 2], "notes": "Payer excluded: Aarav paid for Meera and Kabir"},
        {"title": "Bomras Seafood Dinner", "amount_paise": 1280000, "category": "Food", "date": "2026-11-14", "payer_idx": 4, "split_method": "percentage", "participants": [(0, 2000), (1, 1500), (2, 2000), (3, 1500), (4, 1500), (5, 1500)]},
        {"title": "Villa WiFi & Power Backup Topup", "amount_paise": 120000, "category": "Utilities", "date": "2026-11-14", "payer_idx": 0, "split_method": "equal", "participants": all_6},
        {"title": "Chapora Fort Cold Coffee Stop", "amount_paise": 144000, "category": "Food", "date": "2026-11-15", "payer_idx": 5, "split_method": "equal", "participants": all_6},
        {"title": "Artjuna Brunch", "amount_paise": 540000, "category": "Food", "date": "2026-11-15", "payer_idx": 1, "split_method": "equal", "participants": all_6},
        {"title": "Mandovi Sunset Cruise", "amount_paise": 720000, "category": "Activities", "date": "2026-11-15", "payer_idx": 3, "split_method": "equal", "participants": all_6},
        {"title": "Local Cashew & Spice Boxes", "amount_paise": 390000, "category": "Shopping", "date": "2026-11-15", "payer_idx": 2, "split_method": "custom", "participants": [(0, 90000), (1, 100000), (3, 100000), (5, 100000)]},
        {"title": "Fuel Refills for Scooters", "amount_paise": 180000, "category": "Transport", "date": "2026-11-15", "payer_idx": 4, "split_method": "equal", "participants": [0, 2, 3, 4, 5]},
        {"title": "Beach Shack Snacks & Drinks", "amount_paise": 465000, "category": "Food", "date": "2026-11-16", "payer_idx": 2, "split_method": "equal", "participants": all_6},
        {"title": "Villa Extra Night Stay", "amount_paise": 1800000, "category": "Accommodation", "date": "2026-11-16", "payer_idx": 0, "split_method": "percentage", "participants": [(0, 2000), (1, 2000), (2, 1500), (3, 1500), (4, 1500), (5, 1500)]},
        {"title": "Laundry & Linen Care", "amount_paise": 95000, "category": "Utilities", "date": "2026-11-16", "payer_idx": 1, "split_method": "equal", "participants": all_6},
        {"title": "Martin's Corner Farewell Dinner", "amount_paise": 990000, "category": "Food", "date": "2026-11-16", "payer_idx": 3, "split_method": "equal", "participants": all_6},
        {"title": "Sunscreen & Pharmacy Supplies", "amount_paise": 115000, "category": "Miscellaneous", "date": "2026-11-16", "payer_idx": 5, "split_method": "equal", "participants": [1, 3, 5]},
        {"title": "Fontainhas Heritage Walk Guide", "amount_paise": 300000, "category": "Activities", "date": "2026-11-17", "payer_idx": 1, "split_method": "equal", "participants": all_6},
        {"title": "Panjim Bakery Pastries", "amount_paise": 174000, "category": "Food", "date": "2026-11-17", "payer_idx": 4, "split_method": "equal", "participants": all_6},
        {"title": "Return Airport Cabs", "amount_paise": 440000, "category": "Transport", "date": "2026-11-17", "payer_idx": 2, "split_method": "equal", "participants": all_6},
        {"title": "Baggage Storage at Madgaon", "amount_paise": 60000, "category": "Miscellaneous", "date": "2026-11-17", "payer_idx": 3, "split_method": "equal", "participants": [0, 3, 4]},
        {"title": "Airport Lounge Coffee", "amount_paise": 135000, "category": "Food", "date": "2026-11-17", "payer_idx": 5, "split_method": "equal", "participants": [1, 3, 5]},
        {"title": "Toll & Expressway Fastag", "amount_paise": 84000, "category": "Transport", "date": "2026-11-17", "payer_idx": 0, "split_method": "equal", "participants": all_6},
    ]
    return {
        "name": "Goa Coastal Retreat",
        "destination": "North & South Goa",
        "start_date": "2026-11-12",
        "end_date": "2026-11-17",
        "status": "active",
        "members": members,
        "expenses": expenses,
        "completed_settlements": [(1, 0, 200000)],
    }


def _build_jaipur_trip():
    # 5 members, 24 expenses
    members = [
        ("Vikram Joshi", "vikram.joshi@example.com"),
        ("Ananya Rao", "ananya.rao@example.com"),
        ("Rohan Sen", "rohan.sen@example.com"),
        ("Priya Menon", "priya.menon@example.com"),
        ("Ishaan Kapoor", "ishaan.kapoor@example.com"),
    ]
    all_5 = [0, 1, 2, 3, 4]
    expenses = [
        {"title": "Haveli Boutique Stay (3 Nights)", "amount_paise": 2750000, "category": "Accommodation", "date": "2026-10-20", "payer_idx": 0, "split_method": "equal", "participants": all_5},
        {"title": "Shatabdi Train Tickets", "amount_paise": 875000, "category": "Transport", "date": "2026-10-20", "payer_idx": 1, "split_method": "equal", "participants": all_5},
        {"title": "Chokhi Dhani Traditional Thali", "amount_paise": 625000, "category": "Food", "date": "2026-10-20", "payer_idx": 2, "split_method": "equal", "participants": all_5},
        {"title": "Amer Fort Entry & Audio Guide", "amount_paise": 340000, "category": "Activities", "date": "2026-10-21", "payer_idx": 3, "split_method": "equal", "participants": all_5},
        {"title": "Full Day Tempo Traveller", "amount_paise": 450000, "category": "Transport", "date": "2026-10-21", "payer_idx": 0, "split_method": "equal", "participants": all_5},
        {"title": "LMB Johari Bazaar Lunch", "amount_paise": 385000, "category": "Food", "date": "2026-10-21", "payer_idx": 4, "split_method": "custom", "participants": [(0, 85000), (1, 70000), (2, 80000), (3, 75000), (4, 75000)]},
        {"title": "Block Print Textiles", "amount_paise": 520000, "category": "Shopping", "date": "2026-10-21", "payer_idx": 1, "split_method": "custom", "participants": [(1, 260000), (3, 260000)]},
        {"title": "Nahargarh Sunset Cafe", "amount_paise": 275000, "category": "Food", "date": "2026-10-21", "payer_idx": 2, "split_method": "equal", "participants": all_5},
        {"title": "City Palace Museum Passes", "amount_paise": 400000, "category": "Activities", "date": "2026-10-22", "payer_idx": 1, "split_method": "equal", "participants": all_5},
        {"title": "Bar Palladio Dinner", "amount_paise": 960000, "category": "Food", "date": "2026-10-22", "payer_idx": 3, "split_method": "percentage", "participants": [(0, 2500), (1, 2000), (2, 2000), (3, 1500), (4, 2000)]},
        {"title": "Bapu Bazaar Mojari Shoes", "amount_paise": 190000, "category": "Shopping", "date": "2026-10-22", "payer_idx": 4, "split_method": "equal", "participants": [4], "notes": "Personal purchase"},
        {"title": "Hawa Mahal Morning Chai", "amount_paise": 75000, "category": "Food", "date": "2026-10-22", "payer_idx": 0, "split_method": "equal", "participants": all_5},
        {"title": "Hot Air Balloon Booking", "amount_paise": 1600000, "category": "Activities", "date": "2026-10-22", "payer_idx": 0, "split_method": "equal", "participants": [1, 2, 4], "notes": "Payer excluded: Vikram stayed on ground"},
        {"title": "Hotel Mini Bar & Bottled Water", "amount_paise": 110000, "category": "Utilities", "date": "2026-10-22", "payer_idx": 2, "split_method": "equal", "participants": all_5},
        {"title": "Jantar Mantar Guided Tour", "amount_paise": 150000, "category": "Activities", "date": "2026-10-23", "payer_idx": 3, "split_method": "equal", "participants": all_5},
        {"title": "Tapri Central Rooftop Brunch", "amount_paise": 335000, "category": "Food", "date": "2026-10-23", "payer_idx": 4, "split_method": "equal", "participants": all_5},
        {"title": "Blue Pottery Studio Souvenirs", "amount_paise": 410000, "category": "Shopping", "date": "2026-10-23", "payer_idx": 1, "split_method": "custom", "participants": [(0, 100000), (1, 110000), (2, 100000), (3, 100000)]},
        {"title": "Auto Rickshaw Local Hops", "amount_paise": 95000, "category": "Transport", "date": "2026-10-23", "payer_idx": 2, "split_method": "equal", "participants": [1, 2, 3]},
        {"title": "Handicrafts Packaging & Courier", "amount_paise": 140000, "category": "Miscellaneous", "date": "2026-10-23", "payer_idx": 1, "split_method": "equal", "participants": [0, 1, 3]},
        {"title": "Peacock Rooftop Dinner", "amount_paise": 580000, "category": "Food", "date": "2026-10-23", "payer_idx": 0, "split_method": "equal", "participants": all_5},
        {"title": "Portable WiFi Hotspot Rental", "amount_paise": 80000, "category": "Utilities", "date": "2026-10-23", "payer_idx": 4, "split_method": "equal", "participants": all_5},
        {"title": "Jaipur Junction Cab Drop", "amount_paise": 120000, "category": "Transport", "date": "2026-10-24", "payer_idx": 3, "split_method": "equal", "participants": all_5},
        {"title": "Rawat Kachori Travel Pack", "amount_paise": 90000, "category": "Food", "date": "2026-10-24", "payer_idx": 2, "split_method": "equal", "participants": all_5},
        {"title": "Return Train Pantry Meals", "amount_paise": 215000, "category": "Food", "date": "2026-10-24", "payer_idx": 4, "split_method": "equal", "participants": all_5},
    ]
    return {
        "name": "Jaipur Heritage Circuit",
        "destination": "Jaipur, Rajasthan",
        "start_date": "2026-10-20",
        "end_date": "2026-10-24",
        "status": "active",
        "members": members,
        "expenses": expenses,
        "completed_settlements": [],
    }


def _build_manali_trip():
    # 7 members, 32 expenses, Completed trip (read-only) with pending suggested settlements
    members = [
        ("Arjun Bhatia", "arjun.bhatia@example.com"),
        ("Neha Deshmukh", "neha.deshmukh@example.com"),
        ("Siddharth Roy", "siddharth.roy@example.com"),
        ("Tara Iyer", "tara.iyer@example.com"),
        ("Karan Gill", "karan.gill@example.com"),
        ("Zoya Khan", "zoya.khan@example.com"),
        ("Nikhil Bose", "nikhil.bose@example.com"),
    ]
    all_7 = [0, 1, 2, 3, 4, 5, 6]
    expenses = [
        {"title": "Overnight Volvo Coach Seats", "amount_paise": 1190000, "category": "Transport", "date": "2026-10-02", "payer_idx": 0, "split_method": "equal", "participants": all_7},
        {"title": "Old Manali Timber Chalet", "amount_paise": 4200000, "category": "Accommodation", "date": "2026-10-03", "payer_idx": 1, "split_method": "equal", "participants": all_7},
        {"title": "Cafe 1947 Riverside Lunch", "amount_paise": 735000, "category": "Food", "date": "2026-10-03", "payer_idx": 2, "split_method": "equal", "participants": all_7},
        {"title": "Solang Valley Cab Charter", "amount_paise": 560000, "category": "Transport", "date": "2026-10-03", "payer_idx": 4, "split_method": "equal", "participants": all_7},
        {"title": "Paragliding Tandem Flights", "amount_paise": 1750000, "category": "Activities", "date": "2026-10-03", "payer_idx": 0, "split_method": "equal", "participants": [0, 2, 3, 4, 6]},
        {"title": "Chalet Fireplace Wood & Heaters", "amount_paise": 210000, "category": "Utilities", "date": "2026-10-03", "payer_idx": 1, "split_method": "equal", "participants": all_7},
        {"title": "Johnson's Cafe Trout Dinner", "amount_paise": 945000, "category": "Food", "date": "2026-10-03", "payer_idx": 5, "split_method": "custom", "participants": [(0, 145000), (1, 130000), (2, 140000), (3, 125000), (4, 150000), (5, 130000), (6, 125000)]},
        {"title": "Atal Tunnel & Sissu Day Cab", "amount_paise": 630000, "category": "Transport", "date": "2026-10-04", "payer_idx": 3, "split_method": "equal", "participants": all_7},
        {"title": "Sissu Waterfall Maggi & Tea", "amount_paise": 140000, "category": "Food", "date": "2026-10-04", "payer_idx": 6, "split_method": "equal", "participants": all_7},
        {"title": "Snow Boots & Gloves Rental", "amount_paise": 350000, "category": "Shopping", "date": "2026-10-04", "payer_idx": 4, "split_method": "equal", "participants": [1, 2, 3, 4, 5, 6]},
        {"title": "Drifter's Inn Breakfast", "amount_paise": 490000, "category": "Food", "date": "2026-10-04", "payer_idx": 2, "split_method": "equal", "participants": all_7},
        {"title": "Hampta Pass Trek Guide Fee", "amount_paise": 840000, "category": "Activities", "date": "2026-10-05", "payer_idx": 0, "split_method": "equal", "participants": [0, 1, 3, 4, 5, 6]},
        {"title": "Trail Energy Bars & Hydration", "amount_paise": 210000, "category": "Food", "date": "2026-10-05", "payer_idx": 3, "split_method": "equal", "participants": [0, 1, 3, 4, 5, 6]},
        {"title": "Siddharth's Spa Recovery", "amount_paise": 240000, "category": "Activities", "date": "2026-10-05", "payer_idx": 2, "split_method": "equal", "participants": [2], "notes": "Personal wellness session"},
        {"title": "Lazy Dog Lounge Dinner", "amount_paise": 1050000, "category": "Food", "date": "2026-10-05", "payer_idx": 5, "split_method": "percentage", "participants": [(0, 1500), (1, 1500), (2, 1500), (3, 1500), (4, 1500), (5, 1250), (6, 1250)]},
        {"title": "Kullu Shawl Cooperative Gifts", "amount_paise": 660000, "category": "Shopping", "date": "2026-10-06", "payer_idx": 1, "split_method": "custom", "participants": [(1, 220000), (3, 220000), (5, 220000)]},
        {"title": "Beas River Rafting", "amount_paise": 900000, "category": "Activities", "date": "2026-10-06", "payer_idx": 6, "split_method": "equal", "participants": [0, 2, 3, 4, 5, 6]},
        {"title": "Dylan's Toasted & Roasted Coffee", "amount_paise": 280000, "category": "Food", "date": "2026-10-06", "payer_idx": 4, "split_method": "equal", "participants": all_7},
        {"title": "Hot Water & Chalet Cleaning", "amount_paise": 175000, "category": "Utilities", "date": "2026-10-06", "payer_idx": 1, "split_method": "equal", "participants": all_7},
        {"title": "First Aid & Altitude Meds", "amount_paise": 105000, "category": "Miscellaneous", "date": "2026-10-06", "payer_idx": 3, "split_method": "equal", "participants": all_7},
        {"title": "Vashisht Hot Springs Towels", "amount_paise": 70000, "category": "Miscellaneous", "date": "2026-10-06", "payer_idx": 0, "split_method": "equal", "participants": all_7},
        {"title": "Casa Bella Vista Woodfired Pizza", "amount_paise": 770000, "category": "Food", "date": "2026-10-06", "payer_idx": 2, "split_method": "equal", "participants": all_7},
        {"title": "Naggar Castle Heritage Entry", "amount_paise": 140000, "category": "Activities", "date": "2026-10-07", "payer_idx": 5, "split_method": "equal", "participants": all_7},
        {"title": "Roerich Art Gallery Tickets", "amount_paise": 105000, "category": "Activities", "date": "2026-10-07", "payer_idx": 3, "split_method": "equal", "participants": all_7},
        {"title": "Apple Orchard Cider & Jams", "amount_paise": 315000, "category": "Shopping", "date": "2026-10-07", "payer_idx": 6, "split_method": "equal", "participants": all_7},
        {"title": "Naggar Return Cabs", "amount_paise": 350000, "category": "Transport", "date": "2026-10-07", "payer_idx": 4, "split_method": "equal", "participants": all_7},
        {"title": "Mall Road Momos & Thukpa", "amount_paise": 245000, "category": "Food", "date": "2026-10-07", "payer_idx": 0, "split_method": "equal", "participants": all_7},
        {"title": "Himachali Bakery Travel Snacks", "amount_paise": 196000, "category": "Food", "date": "2026-10-07", "payer_idx": 1, "split_method": "equal", "participants": all_7},
        {"title": "Return Volvo Overnight Bus", "amount_paise": 1225000, "category": "Transport", "date": "2026-10-07", "payer_idx": 0, "split_method": "equal", "participants": all_7},
        {"title": "Highway Dhaba Dinner Stop", "amount_paise": 455000, "category": "Food", "date": "2026-10-07", "payer_idx": 2, "split_method": "equal", "participants": all_7},
        {"title": "Driver Tip & Highway Tolls", "amount_paise": 140000, "category": "Transport", "date": "2026-10-08", "payer_idx": 4, "split_method": "equal", "participants": all_7},
        {"title": "Delhi Arrival Metro & Cabs", "amount_paise": 175000, "category": "Transport", "date": "2026-10-08", "payer_idx": 6, "split_method": "equal", "participants": all_7},
    ]
    return {
        "name": "Manali Mountain Expedition",
        "destination": "Manali & Solang, HP",
        "start_date": "2026-10-02",
        "end_date": "2026-10-08",
        "status": "completed",
        "members": members,
        "expenses": expenses,
        "completed_settlements": [(2, 0, 150000)],
    }


def _build_coorg_trip():
    # 4 members, 22 expenses, tests rounding (10000 / 3) and zero-balance precision
    members = [
        ("Aditya Hegde", "aditya.hegde@example.com"),
        ("Kavya Shetty", "kavya.shetty@example.com"),
        ("Nitin Pai", "nitin.pai@example.com"),
        ("Shreya Kamath", "shreya.kamath@example.com"),
    ]
    all_4 = [0, 1, 2, 3]
    expenses = [
        {"title": "Coffee Estate Homestay (3 Nights)", "amount_paise": 2400000, "category": "Accommodation", "date": "2026-09-18", "payer_idx": 0, "split_method": "equal", "participants": all_4},
        {"title": "Self-Drive SUV Rental", "amount_paise": 960000, "category": "Transport", "date": "2026-09-18", "payer_idx": 1, "split_method": "equal", "participants": all_4},
        {"title": "Highway Fuel Topup", "amount_paise": 340000, "category": "Transport", "date": "2026-09-18", "payer_idx": 2, "split_method": "equal", "participants": all_4},
        {"title": "Maddur Tiffany Breakfast", "amount_paise": 160000, "category": "Food", "date": "2026-09-18", "payer_idx": 3, "split_method": "equal", "participants": all_4},
        {"title": "Estate Walk & Roasting Demo", "amount_paise": 200000, "category": "Activities", "date": "2026-09-18", "payer_idx": 0, "split_method": "equal", "participants": all_4},
        {"title": "Coorg Cuisine Pork & Pandi Curry", "amount_paise": 480000, "category": "Food", "date": "2026-09-18", "payer_idx": 1, "split_method": "custom", "participants": [(0, 140000), (1, 120000), (2, 120000), (3, 100000)]},
        {"title": "Abbey Falls Parking & Entry", "amount_paise": 40000, "category": "Miscellaneous", "date": "2026-09-19", "payer_idx": 2, "split_method": "equal", "participants": all_4},
        {"title": "Dubare Elephant Camp Ferry", "amount_paise": 100000, "category": "Activities", "date": "2026-09-19", "payer_idx": 3, "split_method": "equal", "participants": [0, 1, 2], "notes": "3-way rounding test (₹1,000 / 3) with payer excluded"},
        {"title": "Raintree Cafe Lunch", "amount_paise": 320000, "category": "Food", "date": "2026-09-19", "payer_idx": 2, "split_method": "equal", "participants": all_4},
        {"title": "Madikeri Fresh Ground Coffee", "amount_paise": 440000, "category": "Shopping", "date": "2026-09-19", "payer_idx": 0, "split_method": "percentage", "participants": [(0, 2500), (1, 2500), (2, 2500), (3, 2500)]},
        {"title": "Homestay Bonfire & Barbeque", "amount_paise": 360000, "category": "Food", "date": "2026-09-19", "payer_idx": 1, "split_method": "equal", "participants": all_4},
        {"title": "Solar Heater & Inverter Backup", "amount_paise": 80000, "category": "Utilities", "date": "2026-09-19", "payer_idx": 0, "split_method": "equal", "participants": all_4},
        {"title": "Mandalpatti Jeep Safari", "amount_paise": 480000, "category": "Activities", "date": "2026-09-20", "payer_idx": 3, "split_method": "equal", "participants": all_4},
        {"title": "Raja's Seat Morning Snacks", "amount_paise": 120000, "category": "Food", "date": "2026-09-20", "payer_idx": 2, "split_method": "equal", "participants": all_4},
        {"title": "Bylakuppe Monastery Donation", "amount_paise": 100000, "category": "Miscellaneous", "date": "2026-09-20", "payer_idx": 1, "split_method": "equal", "participants": all_4},
        {"title": "Tibetan Thukpa & Momos", "amount_paise": 240000, "category": "Food", "date": "2026-09-20", "payer_idx": 3, "split_method": "equal", "participants": all_4},
        {"title": "Coorg Honey & Pepper Jars", "amount_paise": 300000, "category": "Shopping", "date": "2026-09-20", "payer_idx": 2, "split_method": "custom", "participants": [(0, 100000), (2, 100000), (3, 100000)]},
        {"title": "Rain Ponchos & Trail Socks", "amount_paise": 160000, "category": "Shopping", "date": "2026-09-20", "payer_idx": 0, "split_method": "equal", "participants": all_4},
        {"title": "Estate Kitchen Farewell Meal", "amount_paise": 400000, "category": "Food", "date": "2026-09-20", "payer_idx": 1, "split_method": "equal", "participants": all_4},
        {"title": "Return Highway Fuel", "amount_paise": 320000, "category": "Transport", "date": "2026-09-21", "payer_idx": 2, "split_method": "equal", "participants": all_4},
        {"title": "Expressway Tolls", "amount_paise": 120000, "category": "Transport", "date": "2026-09-21", "payer_idx": 3, "split_method": "equal", "participants": all_4},
        {"title": "Kamat Upachar Return Dinner", "amount_paise": 280000, "category": "Food", "date": "2026-09-21", "payer_idx": 0, "split_method": "equal", "participants": all_4},
    ]
    return {
        "name": "Coorg Coffee & Trails",
        "destination": "Madikeri, Karnataka",
        "start_date": "2026-09-18",
        "end_date": "2026-09-21",
        "status": "active",
        "members": members,
        "expenses": expenses,
        "completed_settlements": [],
    }


def _build_pondicherry_trip():
    # 8 members, 35 expenses, Completed trip
    members = [
        ("Diya Krishnan", "diya.krishnan@example.com"),
        ("Varun Pillai", "varun.pillai@example.com"),
        ("Sneha Iyer", "sneha.iyer@example.com"),
        ("Manav Gupta", "manav.gupta@example.com"),
        ("Pooja Saxena", "pooja.saxena@example.com"),
        ("Harsh Vardhan", "harsh.vardhan@example.com"),
        ("Tanya Roy", "tanya.roy@example.com"),
        ("Omkar Patil", "omkar.patil@example.com"),
    ]
    all_8 = [0, 1, 2, 3, 4, 5, 6, 7]
    expenses = [
        {"title": "White Town French Villa (2 Nights)", "amount_paise": 4800000, "category": "Accommodation", "date": "2026-09-04", "payer_idx": 0, "split_method": "equal", "participants": all_8},
        {"title": "Chennai ECR Tempo Hire", "amount_paise": 1200000, "category": "Transport", "date": "2026-09-04", "payer_idx": 1, "split_method": "equal", "participants": all_8},
        {"title": "Mahabalipuram Stopover Breakfast", "amount_paise": 400000, "category": "Food", "date": "2026-09-04", "payer_idx": 2, "split_method": "equal", "participants": all_8},
        {"title": "Coromandel Cafe Brunch", "amount_paise": 960000, "category": "Food", "date": "2026-09-04", "payer_idx": 3, "split_method": "equal", "participants": all_8},
        {"title": "Bicycle Rentals (White Town)", "amount_paise": 240000, "category": "Transport", "date": "2026-09-04", "payer_idx": 4, "split_method": "equal", "participants": all_8},
        {"title": "Auroville Visitors Center Pass", "amount_paise": 160000, "category": "Activities", "date": "2026-09-04", "payer_idx": 5, "split_method": "equal", "participants": all_8},
        {"title": "Bread & Chocolate Croissants", "amount_paise": 360000, "category": "Food", "date": "2026-09-04", "payer_idx": 6, "split_method": "equal", "participants": all_8},
        {"title": "Villa Des Pres Dinner", "amount_paise": 1440000, "category": "Food", "date": "2026-09-04", "payer_idx": 7, "split_method": "percentage", "participants": [(0, 1250), (1, 1250), (2, 1250), (3, 1250), (4, 1250), (5, 1250), (6, 1250), (7, 1250)]},
        {"title": "Serenity Beach Surf Lesson", "amount_paise": 1000000, "category": "Activities", "date": "2026-09-05", "payer_idx": 1, "split_method": "equal", "participants": [1, 3, 5, 7]},
        {"title": "Promenade Beach Morning Gelato", "amount_paise": 280000, "category": "Food", "date": "2026-09-05", "payer_idx": 2, "split_method": "equal", "participants": all_8},
        {"title": "Pottery Workshop in Auroville", "amount_paise": 600000, "category": "Activities", "date": "2026-09-05", "payer_idx": 0, "split_method": "equal", "participants": [0, 2, 4, 6]},
        {"title": "Auroville Maroma Candles & Soap", "amount_paise": 520000, "category": "Shopping", "date": "2026-09-05", "payer_idx": 4, "split_method": "custom", "participants": [(0, 120000), (2, 140000), (4, 130000), (6, 130000)]},
        {"title": "Tanto Pizzeria Woodfired Lunch", "amount_paise": 880000, "category": "Food", "date": "2026-09-05", "payer_idx": 3, "split_method": "equal", "participants": all_8},
        {"title": "Paradise Beach Boat Ferry", "amount_paise": 320000, "category": "Transport", "date": "2026-09-05", "payer_idx": 5, "split_method": "equal", "participants": all_8},
        {"title": "Beach Umbrellas & Chairs", "amount_paise": 160000, "category": "Miscellaneous", "date": "2026-09-05", "payer_idx": 6, "split_method": "equal", "participants": all_8},
        {"title": "Villa WiFi & Extra Linen", "amount_paise": 120000, "category": "Utilities", "date": "2026-09-05", "payer_idx": 0, "split_method": "equal", "participants": all_8},
        {"title": "Cafe des Arts Crepes", "amount_paise": 480000, "category": "Food", "date": "2026-09-05", "payer_idx": 7, "split_method": "equal", "participants": all_8},
        {"title": "Le Dupleix Heritage Dinner", "amount_paise": 1600000, "category": "Food", "date": "2026-09-05", "payer_idx": 1, "split_method": "equal", "participants": all_8},
        {"title": "Zero-Balance Water & Ice Run", "amount_paise": 80000, "category": "Utilities", "date": "2026-09-05", "payer_idx": 2, "split_method": "equal", "participants": all_8},
        {"title": "Baker Street Baguettes & Coffee", "amount_paise": 440000, "category": "Food", "date": "2026-09-06", "payer_idx": 4, "split_method": "equal", "participants": all_8},
        {"title": "Pichavaram Mangrove Boating", "amount_paise": 640000, "category": "Activities", "date": "2026-09-06", "payer_idx": 3, "split_method": "equal", "participants": all_8},
        {"title": "Mangrove Highway Coconuts", "amount_paise": 120000, "category": "Food", "date": "2026-09-06", "payer_idx": 5, "split_method": "equal", "participants": all_8},
        {"title": "Chidambaram Lunch Stop", "amount_paise": 560000, "category": "Food", "date": "2026-09-06", "payer_idx": 6, "split_method": "equal", "participants": all_8},
        {"title": "Handmade Paper Journal Set", "amount_paise": 200000, "category": "Shopping", "date": "2026-09-06", "payer_idx": 2, "split_method": "equal", "participants": [2], "notes": "Personal stationery purchase"},
        {"title": "Pondicherry Museum Passes", "amount_paise": 80000, "category": "Activities", "date": "2026-09-06", "payer_idx": 7, "split_method": "equal", "participants": all_8},
        {"title": "Zuka Choco-La Hot Chocolate", "amount_paise": 320000, "category": "Food", "date": "2026-09-06", "payer_idx": 0, "split_method": "equal", "participants": all_8},
        {"title": "Satsanga Courtyard Dinner", "amount_paise": 1040000, "category": "Food", "date": "2026-09-06", "payer_idx": 3, "split_method": "equal", "participants": all_8},
        {"title": "ECR Return Fuel & Tolls", "amount_paise": 480000, "category": "Transport", "date": "2026-09-06", "payer_idx": 1, "split_method": "equal", "participants": all_8},
        {"title": "Auto Transfers to Station", "amount_paise": 160000, "category": "Transport", "date": "2026-09-06", "payer_idx": 4, "split_method": "equal", "participants": all_8},
        {"title": "Mineral Water Cases", "amount_paise": 96000, "category": "Utilities", "date": "2026-09-06", "payer_idx": 5, "split_method": "equal", "participants": all_8},
        {"title": "Photography Print Souvenirs", "amount_paise": 240000, "category": "Shopping", "date": "2026-09-06", "payer_idx": 6, "split_method": "equal", "participants": all_8},
        {"title": "Luggage Locker Rental", "amount_paise": 80000, "category": "Miscellaneous", "date": "2026-09-06", "payer_idx": 7, "split_method": "equal", "participants": all_8},
        {"title": "Sunset Tea at Le Cafe", "amount_paise": 240000, "category": "Food", "date": "2026-09-06", "payer_idx": 2, "split_method": "equal", "participants": all_8},
        {"title": "Driver Allowance & Parking", "amount_paise": 200000, "category": "Transport", "date": "2026-09-06", "payer_idx": 1, "split_method": "equal", "participants": all_8},
        {"title": "Chennai Return Snacks", "amount_paise": 320000, "category": "Food", "date": "2026-09-06", "payer_idx": 0, "split_method": "equal", "participants": all_8},
    ]
    return {
        "name": "Pondicherry Weekend Collective",
        "destination": "Puducherry & Auroville",
        "start_date": "2026-09-04",
        "end_date": "2026-09-06",
        "status": "completed",
        "members": members,
        "expenses": expenses,
        "completed_settlements": [(5, 0, 300000)],
    }
