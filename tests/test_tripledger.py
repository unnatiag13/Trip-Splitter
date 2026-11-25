import os
import tempfile
import unittest

# Configure isolated temporary database before importing backend modules
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["TRIPLEDGER_DB_PATH"] = _TMP_DB.name

from backend import crud
from backend.database import Base, SessionLocal, engine
from backend.finance import calculate_member_balances, compute_split_shares
from backend.models import Trip
from backend.seed import seed_database_if_empty
from backend.settlement import compute_minimum_settlements


class TestTripLedgerCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
        if os.path.exists(_TMP_DB.name):
            os.unlink(_TMP_DB.name)

    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_splits_and_rounding(self):
        valid = {1, 2, 3, 4}
        # Equal split with remainder: 10000 paise among 3 -> 3334, 3333, 3333
        eq = compute_split_shares(
            10000,
            "equal",
            [{"member_id": 1}, {"member_id": 2}, {"member_id": 3}],
            valid,
        )
        self.assertEqual([s["share_paise"] for s in eq], [3334, 3333, 3333])
        self.assertEqual(sum(s["share_paise"] for s in eq), 10000)

        # Custom split exact validation
        cu = compute_split_shares(
            5000,
            "custom",
            [
                {"member_id": 1, "share_paise": 3500},
                {"member_id": 2, "share_paise": 1500},
            ],
            valid,
        )
        self.assertEqual(sum(s["share_paise"] for s in cu), 5000)
        with self.assertRaises(ValueError):
            compute_split_shares(
                5000,
                "custom",
                [
                    {"member_id": 1, "share_paise": 3000},
                    {"member_id": 2, "share_paise": 1500},
                ],
                valid,
            )

        # Percentage split with largest remainder rounding: 100 paise at 33.33%, 33.33%, 33.34%
        pct = compute_split_shares(
            100,
            "percentage",
            [
                {"member_id": 1, "percentage": 33.33},
                {"member_id": 2, "percentage": 33.33},
                {"member_id": 3, "percentage": 33.34},
            ],
            valid,
        )
        self.assertEqual(sum(s["share_paise"] for s in pct), 100)

    def test_settlement_consolidation_and_minimum_tx(self):
        # Reciprocal debts consolidate:
        # A->B 500, B->A 200 => net A -300, B +300 => 1 tx
        txs = compute_minimum_settlements({1: -30000, 2: 30000})
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0], {"from_member_id": 1, "to_member_id": 2, "amount_paise": 30000})

        # Subset-sum non-greedy case:
        # Debtors: -30, -20, -40. Creditors: +50, +15, +25.
        # Greedy largest-to-largest takes 5 transactions; optimal backtracking takes 4!
        optimal = compute_minimum_settlements(
            {
                1: -3000,
                2: -2000,
                3: -4000,
                4: 5000,
                5: 1500,
                6: 2500,
            }
        )
        self.assertEqual(len(optimal), 4)
        for tx in optimal:
            self.assertGreater(tx["amount_paise"], 0)
            self.assertNotEqual(tx["from_member_id"], tx["to_member_id"])

        # Zero-balance trip produces 0 transactions
        self.assertEqual(compute_minimum_settlements({1: 0, 2: 0, 3: 0}), [])

    def test_partial_personal_payer_excluded_edit_delete_and_completion(self):
        trip = crud.create_trip(
            self.db,
            {
                "name": "Test Expedition",
                "destination": "Udaipur",
                "start_date": "2026-11-01",
                "end_date": "2026-11-03",
                "members": [
                    {"name": "Alice", "email": "alice@example.com"},
                    {"name": "Bob", "email": "bob@example.com"},
                    {"name": "Carol", "email": "carol@example.com"},
                ],
            },
        )
        alice, bob, carol = trip.members

        # 1. Payer excluded: Alice pays 6000 for Bob and Carol only
        e1 = crud.create_expense(
            self.db,
            trip.id,
            {
                "title": "Cab for Bob & Carol",
                "amount_paise": 6000,
                "category": "Transport",
                "expense_date": "2026-11-01",
                "payer_id": alice.id,
                "split_method": "equal",
                "participants": [{"member_id": bob.id}, {"member_id": carol.id}],
            },
        )
        # 2. Personal expense: Bob pays 2000 for Bob only (net impact 0)
        e2 = crud.create_expense(
            self.db,
            trip.id,
            {
                "title": "Bob Coffee",
                "amount_paise": 2000,
                "category": "Food",
                "expense_date": "2026-11-01",
                "payer_id": bob.id,
                "split_method": "equal",
                "participants": [{"member_id": bob.id}],
            },
        )
        trip = crud.get_trip_or_raise(self.db, trip.id)
        balances = {
            b["member_id"]: b["remaining_net_paise"]
            for b in calculate_member_balances(trip.members, trip.expenses, [])
        }
        self.assertEqual(balances[alice.id], 6000)
        self.assertEqual(balances[bob.id], -3000)
        self.assertEqual(balances[carol.id], -3000)
        self.assertEqual(sum(balances.values()), 0)

        # 3. Edit e1 to 9000 split across all 3
        crud.update_expense(
            self.db,
            trip.id,
            e1.id,
            {
                "title": "Cab for All",
                "amount_paise": 9000,
                "category": "Transport",
                "expense_date": "2026-11-01",
                "payer_id": alice.id,
                "split_method": "equal",
                "participants": [
                    {"member_id": alice.id},
                    {"member_id": bob.id},
                    {"member_id": carol.id},
                ],
            },
        )
        # 4. Delete e2
        crud.delete_expense(self.db, trip.id, e2.id)
        trip = crud.get_trip_or_raise(self.db, trip.id)
        balances = {
            b["member_id"]: b["remaining_net_paise"]
            for b in calculate_member_balances(trip.members, trip.expenses, [])
        }
        self.assertEqual(balances[alice.id], 6000)
        self.assertEqual(balances[bob.id], -3000)
        self.assertEqual(balances[carol.id], -3000)

        # 5. End trip: generates 3 personalized emails, sets status completed, does NOT mark settlements completed
        res = crud.end_trip_and_send_emails(self.db, trip.id)
        ended_trip = res["trip"]
        self.assertEqual(ended_trip.status, "completed")
        self.assertEqual(len(res["deliveries"]), 3)
        suggested = [s for s in ended_trip.settlements if s.status == "suggested"]
        completed = [s for s in ended_trip.settlements if s.status == "completed"]
        self.assertEqual(len(suggested), 2)
        self.assertEqual(len(completed), 0)

        # Verify personalized HTML content for Alice and Bob (including itemized expense breakdown & group overview)
        alice_email = next(d for d in res["deliveries"] if d.member_id == alice.id)
        bob_email = next(d for d in res["deliveries"] if d.member_id == bob.id)
        self.assertIn("₹60.00", alice_email.html_body)
        self.assertIn("Receive from Bob", alice_email.html_body)
        self.assertIn("Pay Alice", bob_email.html_body)
        self.assertIn("₹30.00", bob_email.html_body)
        self.assertIn("Cab for All", bob_email.html_body)
        self.assertIn("Group Member Balances Overview", bob_email.html_body)
        self.assertNotIn("—", alice_email.html_body)

        # Verify SMTP takes priority over Resend when both are configured
        from backend.email_service import get_email_provider_status
        saved_env = {k: os.environ.get(k) for k in ("RESEND_API_KEY", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD")}
        try:
            os.environ["RESEND_API_KEY"] = "re_dummy"
            os.environ["SMTP_HOST"] = "smtp.gmail.com"
            os.environ["SMTP_PORT"] = "587"
            os.environ["SMTP_USER"] = "user@gmail.com"
            os.environ["SMTP_PASSWORD"] = "apppassword"
            status = get_email_provider_status()
            self.assertEqual(status["provider"], "smtp")
            self.assertTrue(status["configured"])
        finally:
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        # 6. Completed trip restrictions block mutations
        with self.assertRaises(PermissionError):
            crud.create_expense(
                self.db,
                trip.id,
                {
                    "title": "Blocked",
                    "amount_paise": 1000,
                    "category": "Food",
                    "expense_date": "2026-11-02",
                    "payer_id": alice.id,
                    "split_method": "equal",
                    "participants": [{"member_id": alice.id}],
                },
            )

        # 7. Reopen trip restores mutability
        reopened = crud.reopen_trip(self.db, trip.id)
        self.assertEqual(reopened.status, "active")

    def test_seed_5_trips_balances_zero(self):
        seed_database_if_empty(self.db)
        trips = self.db.query(Trip).all()
        self.assertEqual(len(trips), 5)
        for t in trips:
            full = crud.get_trip_or_raise(self.db, t.id)
            self.assertGreaterEqual(len(full.members), 4)
            self.assertLessEqual(len(full.members), 8)
            self.assertGreaterEqual(len(full.expenses), 20)
            self.assertLessEqual(len(full.expenses), 40)
            completed = [s for s in full.settlements if s.status == "completed"]
            balances = calculate_member_balances(full.members, full.expenses, completed)
            self.assertEqual(sum(b["expense_net_paise"] for b in balances), 0)
            self.assertEqual(sum(b["remaining_net_paise"] for b in balances), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
