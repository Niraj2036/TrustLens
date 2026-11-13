import copy
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import zipfile

from app import Application, make_handler
from trustlens.models import validate_dataset
from trustlens.store import ConflictError

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "datasets/trustlens_dataset.json").read_text(encoding="utf-8"))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.application = Application(Path(self.temp.name) / "test.db", seed=False)
        self.store = self.application.store
        self.dataset = validate_dataset({"metadata":{"synthetic":True},"listings":[DATA["listings"][3]]})
        self.store.import_dataset(self.dataset)

    def tearDown(self):
        self.application.close()
        self.temp.cleanup()

    def test_import_analyze_and_review_persist(self):
        report = self.store.analyze("TL-1004")
        detail = self.store.detail("TL-1004")
        self.assertEqual(detail["report"], report)
        self.store.decide("TL-1004", "reviewed", "Checked all evidence.", detail["summary"]["version"])
        reopened = Application(Path(self.temp.name) / "test.db", seed=False)
        saved = reopened.store.detail("TL-1004")
        self.assertEqual(saved["summary"]["status"], "reviewed")
        self.assertEqual(saved["notes"], "Checked all evidence.")
        self.assertTrue(any(e["kind"] == "review" for e in saved["events"]))
        reopened.close()

    def test_stale_review_conflicts(self):
        self.store.decide("TL-1004","reviewed","First",1)
        with self.assertRaises(ConflictError):
            self.store.decide("TL-1004","open","Stale",1)
        self.assertEqual(self.store.detail("TL-1004")["notes"], "First")

    def test_reimport_keeps_notes_and_previous_input(self):
        self.store.decide("TL-1004","reviewed","Retain this note",1)
        self.dataset["listings"][0]["price"] = 600
        self.store.import_dataset(self.dataset)
        detail = self.store.detail("TL-1004")
        self.assertEqual(detail["notes"], "Retain this note")
        self.assertEqual(detail["summary"]["status"], "open")
        self.assertIsNone(detail["report"])
        report = self.store.analyze("TL-1004")
        self.assertTrue(any(c["field"] == "price" for c in report["agents"]["seller"]["changes"]))

    def test_filtering_sorting_and_pagination_clamp(self):
        self.store.import_dataset(validate_dataset(DATA))
        page = self.store.listing_page({"q":"ultracharge","page":"999"})
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["page"], 1)
        self.assertEqual(page["items"][0]["id"], "TL-1001")

    def test_invalid_decision_is_atomic(self):
        with self.assertRaises(ValueError):
            self.store.decide("TL-1004","delisted","no",1)
        self.assertEqual(self.store.detail("TL-1004")["summary"]["version"], 1)

    def test_report_history_is_retained(self):
        self.store.analyze("TL-1004")
        self.store.analyze("TL-1004")
        self.assertIsNotNone(self.store.detail("TL-1004")["previous_report"])

    def test_zip_contains_matching_json_and_schema(self):
        with zipfile.ZipFile(ROOT / "trustlens_dataset.zip") as archive:
            self.assertIsNone(archive.testzip())
            actual = json.loads(archive.read("trustlens_dataset/trustlens_dataset.json"))
            self.assertEqual(actual, DATA)
            self.assertIn("trustlens_dataset/schema.json", archive.namelist())


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.application = Application(Path(cls.temp.name) / "api.db", seed=False)
        cls.server = ThreadingHTTPServer(("127.0.0.1",0), make_handler(cls.application))
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.application.close()
        cls.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = json.dumps(body).encode() if body is not None else None
        request_headers = {"Content-Type":"application/json", **(headers or {})}
        connection.request(method,path,body=data,headers=request_headers)
        response = connection.getresponse()
        content = response.read()
        status = response.status
        response_headers = dict(response.getheaders())
        connection.close()
        parsed = json.loads(content) if "application/json" in response_headers.get("Content-Type","") else content
        return status, parsed, response_headers

    def test_complete_import_analysis_review_export_flow(self):
        status, imported, _ = self.request("POST","/api/import",{"listings":[DATA["listings"][0]]})
        self.assertEqual(status,201)
        status, job, _ = self.request("POST","/api/analyze",{"listing_ids":imported["listing_ids"]})
        self.assertEqual(status,202)
        deadline = time.monotonic()+10
        while time.monotonic()<deadline:
            status, progress, _ = self.request("GET","/api/jobs/"+job["id"])
            if progress["status"] in ("completed","partial"):
                break
            time.sleep(.03)
        self.assertEqual(progress["status"],"completed")
        status, detail, _ = self.request("GET","/api/listings/TL-1001")
        self.assertEqual(detail["report"]["scoring"]["risk"],"high")
        status, saved, _ = self.request("POST","/api/listings/TL-1001/decision",
            {"status":"needs_review","notes":"Request certification evidence.","version":detail["summary"]["version"]})
        self.assertEqual(status,200)
        self.assertEqual(saved["summary"]["status"],"needs_review")
        status, report, headers = self.request("GET","/api/listings/TL-1001/report")
        self.assertEqual(status,200)
        self.assertEqual(report["listing_id"],"TL-1001")
        self.assertIn("attachment",headers["Content-Disposition"])

    def test_invalid_import_does_not_add_records(self):
        before = self.application.store.count()
        status, body, _ = self.request("POST","/api/import",{"listings":[{"id":"invalid"}]})
        self.assertEqual(status,400)
        self.assertIn("missing",body["error"])
        self.assertEqual(self.application.store.count(),before)

    def test_untrusted_host_and_cross_origin_are_rejected(self):
        self.assertEqual(self.request("GET","/api/health",headers={"Host":"evil.example"})[0],403)
        self.assertEqual(self.request("POST","/api/import",{},{"Origin":"https://evil.example"})[0],403)

    def test_wrong_content_type_rejected(self):
        self.assertEqual(self.request("POST","/api/import",{},{"Content-Type":"text/plain"})[0],415)

    def test_static_and_dataset_responses(self):
        status, html, headers = self.request("GET","/")
        self.assertEqual(status,200)
        self.assertIn(b"TrustLens",html)
        self.assertIn("frame-ancestors 'none'",headers["Content-Security-Policy"])
        status, data, _ = self.request("GET","/api/dataset")
        self.assertEqual(status,200)
        self.assertEqual(len(data["listings"]),12)

    def test_unknown_resources_return_404(self):
        for path in ("/api/listings/NO-SUCH-ID","/api/jobs/NO-SUCH-ID","/../app.py"):
            self.assertEqual(self.request("GET",path)[0],404)

    def test_invalid_pagination_returns_400(self):
        self.assertEqual(self.request("GET","/api/listings?page=abc")[0],400)

    def test_unknown_analysis_id_rejected(self):
        self.assertEqual(self.request("POST","/api/analyze",{"listing_ids":["NO-SUCH-ID"]})[0],400)

    def test_health(self):
        status, data, _ = self.request("GET","/api/health")
        self.assertEqual(status,200)
        self.assertEqual(data["status"],"ok")
