import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import unittest


class TestLiveAPIE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.tmp_db.close()
        cls.port = 18099
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls._start_server()

    @classmethod
    def _start_server(cls):
        env = dict(os.environ)
        env["TRIPLEDGER_DB_PATH"] = cls.tmp_db.name
        cls.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{cls.base_url}/api/health", timeout=1) as resp:
                    if resp.status == 200:
                        return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("FastAPI test server failed to start")

    @classmethod
    def _stop_server(cls):
        if cls.proc and cls.proc.poll() is None:
            cls.proc.terminate()
            cls.proc.wait(timeout=5)

    @classmethod
    def tearDownClass(cls):
        cls._stop_server()
        if os.path.exists(cls.tmp_db.name):
            os.unlink(cls.tmp_db.name)

    def _req(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        req = urllib.request.Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                if "application/json" in ctype:
                    return resp.status, json.loads(raw.decode("utf-8"))
                return resp.status, raw.decode("utf-8")
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8", errors="ignore")
            try:
                return err.code, json.loads(raw)
            except Exception:
                return err.code, raw

    def test_full_rest_workflow_and_persistence(self):
        # 1. Dashboard starts empty with 0 trips
        status, dash = self._req("GET", "/api/dashboard")
        self.assertEqual(status, 200)
        self.assertEqual(dash["total_trips"], 0)

        # 2. Create a new trip
        status, trip = self._req(
            "POST",
            "/api/trips",
            {
                "name": "Kerala Backwaters",
                "destination": "Alleppey",
                "start_date": "2026-11-20",
                "end_date": "2026-11-23",
                "members": [
                    {"name": "Dev", "email": "dev@example.com"},
                    {"name": "Nisha", "email": "nisha@example.com"},
                    {"name": "Kabir", "email": "kabir@example.com"},
                ],
            },
        )
        self.assertEqual(status, 201)
        tid = trip["id"]
        dev, nisha, kabir = trip["members"]

        # 3. Add equal, custom, percentage, personal, and payer-excluded expenses
        s, _ = self._req(
            "POST",
            f"/api/trips/{tid}/expenses",
            {
                "title": "Houseboat Stay",
                "amount_paise": 10000,
                "category": "Accommodation",
                "expense_date": "2026-11-20",
                "payer_id": dev["id"],
                "split_method": "equal",
                "participants": [
                    {"member_id": dev["id"]},
                    {"member_id": nisha["id"]},
                    {"member_id": kabir["id"]},
                ],
            },
        )
        self.assertEqual(s, 201)

        s, _ = self._req(
            "POST",
            f"/api/trips/{tid}/expenses",
            {
                "title": "Shikara Ride for Nisha & Kabir",
                "amount_paise": 6000,
                "category": "Activities",
                "expense_date": "2026-11-21",
                "payer_id": dev["id"],
                "split_method": "percentage",
                "participants": [
                    {"member_id": nisha["id"], "percentage": 40},
                    {"member_id": kabir["id"], "percentage": 60},
                ],
            },
        )
        self.assertEqual(s, 201)

        s, trip_detail = self._req("GET", f"/api/trips/{tid}")
        self.assertEqual(s, 200)
        self.assertEqual(sum(b["remaining_net_paise"] for b in trip_detail["balances"]), 0)
        self.assertEqual(len(trip_detail["settlements"]["suggested"]), 2)

        # 4. Restart server to verify SQLite persistence
        self._stop_server()
        self._start_server()
        s, persisted_trip = self._req("GET", f"/api/trips/{tid}")
        self.assertEqual(s, 200)
        self.assertEqual(persisted_trip["name"], "Kerala Backwaters")
        self.assertEqual(len(persisted_trip["expenses"]), 2)

        # 5. End Trip -> generates 3 personalized HTML emails in Demo Mode, locks read-only, keeps settlements suggested
        s, ended = self._req("POST", f"/api/trips/{tid}/end")
        self.assertEqual(s, 200)
        self.assertEqual(ended["status"], "completed")
        self.assertEqual(len(ended["email_deliveries"]), 3)
        self.assertEqual(len(ended["settlements"]["suggested"]), 2)
        self.assertEqual(len(ended["settlements"]["completed"]), 0)

        # Download HTML summary & inline view HTML summary
        dl_id = ended["email_deliveries"][0]["id"]
        s, html_doc = self._req("GET", f"/api/trips/{tid}/emails/{dl_id}/download")
        self.assertEqual(s, 200)
        self.assertIn("Kerala Backwaters", html_doc)

        s, view_doc = self._req("GET", f"/api/trips/{tid}/emails/{dl_id}/view")
        self.assertEqual(s, 200)
        self.assertIn("Kerala Backwaters", view_doc)

        # Create simplified trip (name + start_date only, no destination or end_date)
        s, simple_trip = self._req(
            "POST",
            "/api/trips",
            {
                "name": "Coorg Weekend",
                "start_date": "2026-11-25",
                "members": [
                    {"name": "Riya", "email": "riya@example.com"},
                    {"name": "Arjun", "email": "arjun@example.com"},
                ],
            },
        )
        self.assertEqual(s, 201)
        self.assertEqual(simple_trip["destination"], "Coorg Weekend")
        self.assertEqual(simple_trip["end_date"], "2026-11-25")

        # Verify completed trip blocks expense creation
        s, blocked = self._req(
            "POST",
            f"/api/trips/{tid}/expenses",
            {
                "title": "Should Block",
                "amount_paise": 500,
                "category": "Food",
                "expense_date": "2026-11-22",
                "payer_id": dev["id"],
                "split_method": "equal",
                "participants": [{"member_id": dev["id"]}],
            },
        )
        self.assertEqual(s, 403)

        # Reopen trip and clean up
        s, reopened = self._req("POST", f"/api/trips/{tid}/reopen")
        self.assertEqual(s, 200)
        self.assertEqual(reopened["status"], "active")


if __name__ == "__main__":
    unittest.main(verbosity=2)
