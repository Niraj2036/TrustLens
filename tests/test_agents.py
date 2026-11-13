import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from trustlens.agents import Orchestrator, aggregate, claim_extraction, image_signals, review_authenticity, RULES
from trustlens.models import validate_dataset, ValidationError

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "datasets/trustlens_dataset.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)


class AgentTests(unittest.TestCase):
    def analyze(self, index):
        return Orchestrator().run(copy.deepcopy(DATA["listings"][index]), {"now": NOW})

    def test_pipeline_has_ten_recorded_agents(self):
        report = self.analyze(0)
        self.assertEqual(len(report["execution"]), 10)
        self.assertTrue(all(log["status"] == "completed" for log in report["execution"]))
        self.assertTrue(report["report"]["human_review_required"])

    def test_detects_burst_templates_and_incentives(self):
        report = self.analyze(0)
        codes = {f["code"] for f in report["scoring"]["findings"]}
        self.assertTrue({"review_burst", "duplicate_phrasing", "incentivized_language"} <= codes)
        self.assertGreaterEqual(report["agents"]["authenticity"]["metrics"]["burst_count"], 210)
        self.assertEqual(report["scoring"]["risk"], "high")

    def test_ordinary_listing_has_no_flags(self):
        report = self.analyze(3)
        self.assertEqual(report["scoring"]["findings"], [])
        self.assertEqual(report["scoring"]["risk"], "low")

    def test_dangerous_health_claim_caps_score(self):
        report = self.analyze(1)
        self.assertLessEqual(report["scoring"]["trust_score"], 49)
        self.assertEqual(report["scoring"]["risk"], "high")
        self.assertEqual(report["scoring"]["guardrails"][0]["cap"], 49)

    def test_high_severity_certification_requires_review(self):
        report = self.analyze(4)
        self.assertEqual(report["scoring"]["risk"], "medium")
        self.assertLessEqual(report["scoring"]["trust_score"], 74)
        self.assertGreater(report["scoring"]["weighted_score"], 74)

    def test_missing_reviews_do_not_get_authenticity_score(self):
        item = copy.deepcopy(DATA["listings"][3])
        item["reviews"] = []
        item["images"] = []
        report = Orchestrator().run(item, {"now": NOW})
        authenticity = next(c for c in report["scoring"]["components"] if c["agent"] == "authenticity")
        self.assertFalse(authenticity["available"])
        self.assertIsNone(authenticity["score"])
        self.assertEqual(report["scoring"]["coverage"], .5)
        self.assertTrue(any("No customer reviews" in l for l in report["report"]["limitations"]))

    def test_partial_agent_failure_retried_and_excluded(self):
        calls = []
        def fail(item, context):
            calls.append(1)
            raise RuntimeError("secret raw stack trace")
        report = Orchestrator({"authenticity": fail}).run(DATA["listings"][0], {"now": NOW})
        self.assertEqual(len(calls), 2)
        self.assertTrue(report["partial"])
        log = next(l for l in report["execution"] if l["agent"] == "authenticity")
        self.assertEqual(log["status"], "failed")
        self.assertNotIn("secret raw stack trace", json.dumps(report))

    def test_transient_failure_recovers_on_second_attempt(self):
        calls = []
        from trustlens.agents import listing_compliance
        def once(item, context):
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("transient")
            return listing_compliance(item, context)
        report = Orchestrator({"compliance": once}).run(DATA["listings"][3], {"now": NOW})
        self.assertFalse(report["partial"])
        self.assertEqual(next(l for l in report["execution"] if l["agent"] == "compliance")["attempts"], 2)

    def test_scenario_label_never_affects_score(self):
        item = copy.deepcopy(DATA["listings"][3])
        first = Orchestrator().run(item, {"now": NOW})["scoring"]
        item["synthetic_scenario"] = {"intended_risk": "high"}
        second = Orchestrator().run(item, {"now": NOW})["scoring"]
        self.assertEqual(first, second)

    def test_image_matches_are_supplied_metadata(self):
        item = DATA["listings"][2]
        fp = item["images"][0]["fingerprint"]
        result = image_signals(item, {"image_index": {fp: [item["id"], "OTHER-1"]}})
        self.assertTrue(any(f["code"] == "image_reuse" for f in result["findings"]))
        self.assertTrue(any("No pixels" in l for l in result["limitations"]))

    def test_document_reference_is_not_independent_verification(self):
        item = copy.deepcopy(DATA["listings"][0])
        item["certifications"] = [{"name": "UL", "document_reference": "seller-document-123"}]
        claims = claim_extraction(item, {})["claims"]
        self.assertEqual(next(c for c in claims if c["text"].lower() == "ul certified")["status"], "Document supplied")
        self.assertTrue(all(c["source"] == "seller-stated" for c in claims))

    def test_drift_detects_seller_swap_and_price_drop(self):
        report = self.analyze(8)
        codes = {f["code"] for f in report["scoring"]["findings"]}
        self.assertTrue({"seller_swap", "price_drop"} <= codes)

    def test_low_coverage_is_insufficient(self):
        report = aggregate({"compliance": {"score":100,"available":True,"findings":[]}})
        self.assertEqual(report["risk"], "insufficient")
        self.assertEqual(report["trust_score"], 100)
        self.assertEqual(report["coverage"], .25)

    def test_all_unavailable_produces_no_score(self):
        report = aggregate({})
        self.assertIsNone(report["trust_score"])
        self.assertEqual(report["risk"], "insufficient")

    def test_cross_listing_reviewer_memory(self):
        item = copy.deepcopy(DATA["listings"][2])
        memory = {r["reviewer_id"]: ["TL-1001"] for r in item["reviews"][:10]}
        output = review_authenticity(item, {"reviewer_memory": memory})
        self.assertIn("reviewer_memory", {f["code"] for f in output["findings"]})

    def test_region_presets_change_medical_impact(self):
        item = copy.deepcopy(DATA["listings"][6])
        item["region"] = "Global"
        first = Orchestrator().run(item, {"now": NOW})
        item["region"] = "US"
        second = Orchestrator().run(item, {"now": NOW})
        self.assertLess(second["agents"]["compliance"]["score"], first["agents"]["compliance"]["score"])


    def test_seller_request_targets_the_listing_and_claim_documents(self):
        report = self.analyze(0)["report"]
        self.assertIn("TL-1001", report["seller_request"])
        self.assertIn("UL", report["seller_request"])
        self.assertIn("\n\n", report["seller_request"])
        self.assertIn("matching product model", report["seller_request"])
        self.assertTrue(all(q["question"].startswith("Please") for q in report["questions"]))

    def test_seller_request_is_absent_when_no_findings_exist(self):
        report = self.analyze(3)["report"]
        self.assertEqual(report["seller_request"], "")
        self.assertEqual(report["questions"], [])

    def test_health_request_asks_for_substantiation(self):
        report = self.analyze(1)["report"]
        self.assertIn("substantiation", report["seller_request"])
        self.assertIn("Cures diabetes", report["seller_request"])
        self.assertTrue(report["human_review_required"])


class ValidationTests(unittest.TestCase):
    def test_dataset_has_declared_counts(self):
        data = validate_dataset(DATA)
        self.assertEqual(len(data["listings"]), 12)
        self.assertEqual(sum(len(i["reviews"]) for i in data["listings"]), 1268)

    def test_rejects_duplicate_listing_ids(self):
        with self.assertRaises(ValidationError):
            validate_dataset({"listings":[DATA["listings"][0], DATA["listings"][0]]})

    def test_rejects_duplicate_review_ids(self):
        item = copy.deepcopy(DATA["listings"][3])
        item["reviews"].append(item["reviews"][0])
        with self.assertRaises(ValidationError):
            validate_dataset({"listings":[item]})

    def test_rejects_invalid_numeric_fields(self):
        for value in (float("nan"), float("inf"), -1, True, "100"):
            item = copy.deepcopy(DATA["listings"][3])
            item["price"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_dataset({"listings":[item]})

    def test_rejects_string_purchase_verification(self):
        item = copy.deepcopy(DATA["listings"][3])
        item["reviews"][0]["verified_purchase"] = "true"
        with self.assertRaises(ValidationError):
            validate_dataset({"listings":[item]})

    def test_rejects_invalid_date_and_region(self):
        for key, value in (("listed_at", "yesterday"), ("region", "INVALID")):
            item = copy.deepcopy(DATA["listings"][3])
            item[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_dataset({"listings":[item]})

    def test_input_is_not_mutated(self):
        item = copy.deepcopy(DATA["listings"][3])
        del item["images"]
        validate_dataset({"listings":[item]})
        self.assertNotIn("images", item)
