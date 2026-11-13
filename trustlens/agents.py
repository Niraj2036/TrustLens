"""Ten focused agents with explicit handoffs, evidence, retries, and partial results.

The default engine is deterministic NLP/statistical screening. No claim is made that
these heuristics prove fraud or that a language model has verified supplied evidence.
"""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
import math
import re
import time

from .models import timestamp

AGENTS = [
    {"id": "ingestion", "name": "Listing ingestion", "role": "Normalize listing, price history, and seller records.", "stage": "Ingest"},
    {"id": "segmentation", "name": "Review segmentation", "role": "Group reviews into UTC weeks and purchase cohorts.", "stage": "Ingest"},
    {"id": "compliance", "name": "Listing compliance", "role": "Screen claims using illustrative regional review rules.", "stage": "Detect"},
    {"id": "claims", "name": "Claim extraction", "role": "Extract specs, materials, certifications, and warranty terms.", "stage": "Detect"},
    {"id": "authenticity", "name": "Review authenticity", "role": "Detect bursts, similar text, incentives, and reviewer clusters.", "stage": "Detect"},
    {"id": "seller", "name": "Seller behavior", "role": "Inspect account age, relisting, price drift, and history.", "stage": "Detect"},
    {"id": "images", "name": "Image signals", "role": "Compare supplied fingerprints and brand metadata.", "stage": "Detect"},
    {"id": "scoring", "name": "Risk aggregation", "role": "Combine severity and confidence into a weighted score.", "stage": "Decide"},
    {"id": "report", "name": "Reviewer report", "role": "Rank evidence and draft specific follow-up questions.", "stage": "Report"},
    {"id": "orchestrator", "name": "Orchestrator", "role": "Route handoffs, retry once, and preserve partial analysis.", "stage": "Coordinate"},
]
WEIGHTS = {"compliance": .25, "authenticity": .40, "seller": .25, "images": .10}
RULES = {
    "IN": {"name": "India screening preset", "medical_impact": 32},
    "US": {"name": "United States screening preset", "medical_impact": 36},
    "EU": {"name": "European Union screening preset", "medical_impact": 36},
    "Global": {"name": "General screening preset", "medical_impact": 28},
}
STOP = set("the a an and is it to of for in with this was very my i as on at be are but has have".split())


def result(findings=None, metrics=None, available=True, limitations=None, **extra):
    findings = findings or []
    deduction = sum(f["impact"] * f["confidence"] for f in findings)
    return {"score": round(max(0, 100 - deduction)), "available": available,
            "findings": findings, "metrics": metrics or {}, "limitations": limitations or [], **extra}


def finding(code, title, severity, detail, evidence, action, impact, confidence=.9):
    return {"code": code, "title": title, "severity": severity, "detail": detail,
            "evidence": evidence, "action": action, "impact": impact, "confidence": confidence}


def listing_ingestion(item, context):
    points = sorted(item["price_history"], key=lambda p: timestamp(p["date"]))
    return result(metrics={"review_count": len(item["reviews"]), "price_points": len(points),
                           "image_records": len(item["images"]), "stock_events": len(item.get("stock_history", []))},
                  normalized={"listing_id": item["id"], "seller_id": item["seller"]["id"],
                              "price_history": points, "category": item["category"], "region": item["region"]})


def review_segmentation(item, context):
    buckets = defaultdict(list)
    cohorts = Counter()
    for review in item["reviews"]:
        moment = timestamp(review["date"])
        monday = (moment - timedelta(days=moment.weekday())).date().isoformat()
        buckets[monday].append(review)
        cohorts["verified" if review.get("verified_purchase") is True else
                "unverified" if review.get("verified_purchase") is False else "unknown"] += 1
    weekly = [{"week": key, "count": len(values),
               "average_rating": round(sum(r["rating"] for r in values) / len(values), 2),
               "unverified": sum(r.get("verified_purchase") is False for r in values)}
              for key, values in sorted(buckets.items())]
    reviews = item["reviews"]
    return result(metrics={"total": len(reviews), "cohorts": dict(cohorts),
                           "average_rating": round(sum(r["rating"] for r in reviews) / len(reviews), 2) if reviews else None},
                  weekly=weekly, available=bool(reviews),
                  limitations=[] if reviews else ["No reviews were supplied; authenticity cannot be assessed."])


def claim_extraction(item, context):
    content = item["title"] + ". " + item["description"]
    claims = []
    patterns = [
        ("Capacity", r"\b\d[\d,]*(?:\.\d+)?\s*(?:mAh|Wh|mL|litres?|liters?|GB|TB)\b"),
        ("Material", r"\b(?:stainless steel|organic cotton|genuine leather|medical grade|BPA[- ]free|aluminium|aluminum)\b"),
        ("Certification", r"\b(?:(?:CE|UL|ISO\s*\d+)\s*(?:certified|approved)|FDA\s*approved)\b"),
        ("Warranty", r"\b\d+[- ](?:year|month)s?\s+warranty\b"),
        ("Returns", r"\b\d+[- ]day\s+(?:returns?|return policy|money[- ]back)\b"),
    ]
    for kind, expression in patterns:
        for match in re.finditer(expression, content, re.I):
            value = match.group()
            documents = [c.get("document_reference") for c in item["certifications"]
                         if c.get("document_reference") and
                         re.search(r"\b" + re.escape(str(c["name"])) + r"\b", value, re.I)]
            claims.append({"type": kind, "text": value, "source": "seller-stated",
                           "status": "Document supplied" if documents else "Unverified",
                           "documents": documents, "confidence": .95 if kind != "Material" else .85})
    unique = list({(c["type"], c["text"].lower()): c for c in claims}.values())
    return result(metrics={"extracted": len(unique), "documents_supplied": sum(bool(c["documents"]) for c in unique)},
                  claims=unique,
                  limitations=["Supplied document references are not independent verification."])


def listing_compliance(item, context):
    content = item["title"] + ". " + item["description"]
    signals = []
    rules = RULES[item["region"]]
    certificates = {c["name"].upper(): c for c in item["certifications"]}
    for label in ("CE", "UL", "FDA"):
        if re.search(r"\b" + label + r"\s*(?:certified|approved)\b", content, re.I):
            record = certificates.get(label, {})
            if not record.get("document_reference"):
                signals.append(finding("claim_" + label.lower(), f"Unsupported {label} claim", "high",
                    f"The listing states {label} approval or certification without a supporting document reference.",
                    {"claim": label, "region": item["region"], "document_reference": None},
                    f"Request the {label} documentation and match its model number to this product.", 24, .98))
    medical = re.findall(r"\b(?:cures?\s+(?:diabetes|cancer|arthritis)|guaranteed\s+(?:weight loss|cure)|medical grade|clinically proven)\b", content, re.I)
    if medical:
        signals.append(finding("medical_claim", "Health claim needs specialist review", "high",
            "Health or medical language requires supporting evidence and a qualified human review.",
            {"phrases": list(dict.fromkeys(medical)), "screening_preset": rules["name"]},
            "Request substantiation; have a policy specialist review the exact claim before approval.",
            rules["medical_impact"], .95))
    if re.search(r"\b(?:100%\s*(?:authentic|genuine)|original brand)\b", content, re.I) and not item.get("brand_authorization"):
        signals.append(finding("authenticity_claim", "Brand authorization is missing", "medium",
            "Authenticity is asserted, but no authorization reference was supplied.",
            {"brand": item.get("brand", "Not specified")},
            "Request a brand authorization letter or traceable supplier invoice.", 15, .8))
    if len(item["description"]) < 80:
        signals.append(finding("listing_quality", "Listing details are incomplete", "low",
            "The supplied description contains fewer than 80 characters.",
            {"description_characters": len(item["description"])},
            "Add model specifications, warranty terms, and return details.", 10, .85))
    return result(signals, {"preset": rules["name"], "region": item["region"]},
                  limitations=["Illustrative academic screening rules; not a legal or marketplace-policy determination."])


def review_authenticity(item, context):
    reviews = item["reviews"]
    signals, flagged = [], set()
    metrics = {"duplicate_reviews": 0, "incentivized_reviews": 0, "burst_count": 0,
               "unverified_share": 0, "near_duplicate_comparisons": 0}
    if not reviews:
        return result(available=False, metrics=metrics, limitations=["No customer reviews were provided."],
                      flagged_reviewer_ids=[])
    dates = sorted((timestamp(r["date"]), idx) for idx, r in enumerate(reviews))
    left, peak = 0, []
    for right, (date, idx) in enumerate(dates):
        while date - dates[left][0] > timedelta(hours=48):
            left += 1
        if right - left + 1 > len(peak):
            peak = dates[left:right + 1]
    span = max(3, (dates[-1][0] - dates[0][0]).total_seconds() / 86400)
    baseline_per_48h = max(1, (len(reviews) - len(peak)) / max(1, span - 2) * 2)
    ratio = len(peak) / baseline_per_48h
    metrics.update({"burst_count": len(peak), "burst_ratio": round(ratio, 2),
                    "baseline_per_48h": round(baseline_per_48h, 2)})
    if len(peak) >= 12 and len(peak) >= len(reviews) * .25 and ratio >= 3:
        signals.append(finding("review_burst", "Unusual 48-hour review burst", "high",
            f"{len(peak)} of {len(reviews)} reviews arrived within 48 hours, {ratio:.1f}× the remaining-period baseline.",
            {"count": len(peak), "window_start": peak[0][0].isoformat(), "window_end": peak[-1][0].isoformat(),
             "baseline_per_48h": round(baseline_per_48h, 2), "review_ids": [reviews[i]["id"] for _, i in peak[:12]]},
            "Compare the spike with actual orders, promotions, and fulfilment records.", 34, .9))

    normalized = [" ".join(re.findall(r"\w+", r["text"].lower())) for r in reviews]
    exact = defaultdict(list)
    for idx, value in enumerate(normalized):
        exact[value].append(idx)
    parents = list(range(len(reviews)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def join(a, b):
        parents[root(a)] = root(b)

    for indices in exact.values():
        for idx in indices[1:]:
            join(indices[0], idx)
    tokens = [set(value.split()) - STOP for value in normalized]
    inverted, compared = defaultdict(list), set()
    budget = 40000
    capped = False
    for idx, value in enumerate(normalized):
        words = value.split()
        shingles = {" ".join(words[n:n + 4]) for n in range(max(0, len(words) - 3))}
        candidates = set()
        for shingle in sorted(shingles)[:16]:
            candidates.update(inverted[shingle][-20:])
        for other in sorted(candidates):
            pair = (other, idx)
            if len(compared) >= budget:
                capped = True
                break
            if pair in compared or root(other) == root(idx):
                continue
            compared.add(pair)
            union = tokens[idx] | tokens[other]
            if len(union) >= 8 and len(tokens[idx] & tokens[other]) / len(union) >= .82:
                join(idx, other)
        for shingle in sorted(shingles)[:16]:
            inverted[shingle].append(idx)
    groups = defaultdict(list)
    for idx in range(len(reviews)):
        groups[root(idx)].append(idx)
    groups = [g for g in groups.values() if len({reviews[i]["reviewer_id"] for i in g}) >= 3]
    duplicate_indices = {idx for g in groups for idx in g}
    duplicate_share = len(duplicate_indices) / len(reviews)
    metrics.update({"duplicate_reviews": len(duplicate_indices), "duplicate_share": round(duplicate_share, 3),
                    "near_duplicate_comparisons": len(compared)})
    if len(duplicate_indices) >= 6 and duplicate_share >= .08:
        examples = sorted(groups, key=len, reverse=True)[:3]
        signals.append(finding("duplicate_phrasing", "Repeated review templates", "high" if duplicate_share >= .15 else "medium",
            f"{len(duplicate_indices)} reviews belong to exact or near-duplicate text clusters across distinct reviewers.",
            {"count": len(duplicate_indices), "share": round(duplicate_share, 3),
             "examples": [{"text": reviews[g[0]]["text"], "count": len(g),
                           "review_ids": [reviews[i]["id"] for i in g[:8]]} for g in examples]},
            "Sample the clustered reviews and examine reviewer independence and purchase records.", 38 if duplicate_share >= .15 else 22, .92))
        flagged.update(reviews[i]["reviewer_id"] for i in duplicate_indices)
    incentives = [r for r in reviews if re.search(
        r"\b(?:free product|gift card|paid review|in exchange for|seller (?:paid|offered)|five stars for|refund for)\b", r["text"], re.I)]
    metrics["incentivized_reviews"] = len(incentives)
    if incentives:
        signals.append(finding("incentivized_language", "Incentive language in reviews", "high",
            f"{len(incentives)} reviews mention compensation, free products, or rating incentives.",
            {"count": len(incentives), "review_ids": [r["id"] for r in incentives[:8]],
             "sample": incentives[0]["text"]},
            "Review compensation disclosures and investigate whether ratings were influenced.", 24 if len(incentives) >= 3 else 12, .95))
        flagged.update(r["reviewer_id"] for r in incentives)
    unverified = [r for r in reviews if r.get("verified_purchase") is False]
    metrics["unverified_share"] = round(len(unverified) / len(reviews), 3)
    if len(unverified) >= 10 and len(unverified) / len(reviews) > .55:
        signals.append(finding("unverified_cohort", "Large unverified-purchase cohort", "medium",
            f"{len(unverified)} of {len(reviews)} reviews explicitly lack verified-purchase status. This is contextual evidence only.",
            {"count": len(unverified), "total": len(reviews)},
            "Cross-check review eligibility and purchase verification with marketplace records.", 12, .65))
    networks = defaultdict(list)
    for review in reviews:
        if review.get("network_hash"):
            networks[review["network_hash"]].append(review)
    cluster = max(networks.values(), key=len, default=[])
    if len({r["reviewer_id"] for r in cluster}) >= 8:
        signals.append(finding("network_cluster", "Shared reviewer network identifier", "medium",
            f"{len(cluster)} reviews share a supplied pseudonymous network hash; shared networks can have legitimate causes.",
            {"count": len(cluster), "review_ids": [r["id"] for r in cluster[:8]]},
            "Ask the platform to check the cluster against household, workplace, and campaign explanations.", 15, .7))
        flagged.update(r["reviewer_id"] for r in cluster)
    memory = context.get("reviewer_memory", {})
    matches = {r["reviewer_id"]: sorted(set(memory[r["reviewer_id"]]) - {item["id"]})
               for r in reviews if r["reviewer_id"] in memory and set(memory[r["reviewer_id"]]) - {item["id"]}}
    if len(matches) >= 3:
        signals.append(finding("reviewer_memory", "Reviewer cluster seen on other flagged listings", "medium",
            f"{len(matches)} reviewers also occur in text, incentive, or network clusters in earlier local analyses.",
            {"reviewer_ids": list(matches)[:12], "other_listings": sorted({v for values in matches.values() for v in values})},
            "Review the connected listings together; shared reviewers alone do not establish coordination.", 15, .75))
    limitations = ["Near-duplicate detection uses token overlap, not a trained authenticity model.",
                   "Review velocity has not been reconciled with actual order volume."]
    if capped:
        limitations.append("Near-duplicate comparison budget reached; exact text grouping still covers all reviews.")
    if not networks:
        limitations.append("No pseudonymous network metadata supplied; network clustering was unavailable.")
    return result(signals, metrics, limitations=limitations, flagged_reviewer_ids=sorted(flagged))


def seller_behavior(item, context):
    seller, signals = item["seller"], []
    now = context.get("now", datetime.now(timezone.utc))
    age = max(0, (now - timestamp(seller["created_at"])).days)
    if age < 45 and len(item["reviews"]) >= 80:
        signals.append(finding("new_seller_velocity", "Review volume outpaces seller history", "high",
            f"A {age}-day-old seller account is associated with {len(item['reviews'])} reviews.",
            {"account_age_days": age, "review_count": len(item["reviews"]), "seller_id": seller["id"]},
            "Validate seller identity and compare order history with review growth.", 28, .8))
    if seller.get("relisting_count", 0) >= 4:
        signals.append(finding("listing_churn", "Frequent relisting activity", "medium",
            f"The supplied seller history records {seller['relisting_count']} relistings.",
            {"relisting_count": seller["relisting_count"]},
            "Compare old listing IDs, buyer complaints, and reasons for relisting.", 22, .85))
    if seller.get("prior_takedowns", 0) > 0:
        signals.append(finding("prior_takedowns", "Prior seller takedowns recorded", "high",
            f"Supplied history records {seller['prior_takedowns']} prior takedowns; reasons are not independently verified.",
            {"prior_takedowns": seller["prior_takedowns"]},
            "Request the reasons and appeal outcomes for earlier enforcement actions.", 30, .9))
    previous = item.get("previous_version") or context.get("previous_listing") or {}
    changes = []
    for key in ("title", "description"):
        if previous.get(key) and previous[key] != item.get(key):
            changes.append({"field": key, "before": previous[key], "after": item.get(key)})
    old_seller = previous.get("seller_id") or previous.get("seller", {}).get("id")
    if old_seller and old_seller != seller["id"]:
        changes.append({"field": "seller", "before": old_seller, "after": seller["id"]})
        signals.append(finding("seller_swap", "Seller identity changed", "high",
            "The current seller differs from the supplied previous listing version.",
            {"previous_seller": old_seller, "current_seller": seller["id"]},
            "Confirm ownership transfer and revalidate supplier documentation.", 30, .95))
    history = sorted(item["price_history"], key=lambda p: timestamp(p["date"]))
    old_price = previous.get("price") or (history[-2]["price"] if len(history) > 1 else None)
    if old_price is not None and old_price != item["price"]:
        changes.append({"field": "price", "before": old_price, "after": item["price"]})
        drop = (old_price - item["price"]) / max(old_price, .01)
        if drop >= .35:
            signals.append(finding("price_drop", "Sharp price drop", "medium",
                f"The price fell {drop:.0%} from the preceding available price.",
                {"previous_price": old_price, "current_price": item["price"], "drop_share": round(drop, 3)},
                "Check promotion records, supplier changes, and possible substitution.", 18, .85))
    return result(signals, {"account_age_days": age, "sales_count": seller.get("sales_count"),
                            "relisting_count": seller.get("relisting_count"), "prior_takedowns": seller.get("prior_takedowns")},
                  changes=changes, previous=previous,
                  limitations=["Seller history is supplied input, not an independently queried enforcement database."])


def image_signals(item, context):
    images, signals = item["images"], []
    usable = [image for image in images if image.get("fingerprint") or (image.get("catalog_brand") and image.get("observed_brand"))]
    if not usable:
        return result(available=False, metrics={"image_records": len(images)}, limitations=["No comparable image fingerprints or brand metadata supplied. Pixel analysis and reverse-image search were not performed."])
    reused = []
    for image in images:
        fingerprint = image.get("fingerprint")
        others = [v for v in context.get("image_index", {}).get(fingerprint, []) if v != item["id"]] if fingerprint else []
        if others:
            reused.append({"fingerprint": fingerprint, "other_listing_ids": others})
        if image.get("catalog_brand") and image.get("observed_brand") and image["catalog_brand"].lower() != image["observed_brand"].lower():
            signals.append(finding("brand_metadata_mismatch", "Image brand metadata differs", "high",
                "Supplied catalog and observed-brand labels disagree.",
                {"catalog_brand": image["catalog_brand"], "observed_brand": image["observed_brand"]},
                "Inspect the original image and packaging against an authorized catalog.", 32, .75))
    if reused:
        signals.append(finding("image_reuse", "Image fingerprint reused across listings", "medium",
            f"{len(reused)} supplied fingerprints also occur on other locally imported listings.",
            {"matches": reused},
            "Check whether reuse is authorized stock imagery or misleading product representation.", 22, .85))
    return result(signals, {"image_records": len(images), "reused_fingerprints": len(reused)},
                  limitations=["Metadata/fingerprint comparison only. No pixels, logos, certificate authenticity, or live reverse-image search were verified."])


def aggregate(outputs):
    components, numerator, denominator = [], 0, 0
    for key, weight in WEIGHTS.items():
        output = outputs.get(key, {})
        available = output.get("available", False)
        components.append({"agent": key, "weight": weight, "score": output.get("score") if available else None,
                           "available": available})
        if available:
            numerator += weight * output["score"]
            denominator += weight
    score = round(numerator / denominator) if denominator else None
    # Image metadata is partial coverage, even when supplied.
    coverage = sum(c["weight"] * (.4 if c["agent"] == "images" else 1)
                   for c in components if c["available"])
    risk = "insufficient" if coverage < .5 else "high" if score < 50 else "medium" if score < 75 else "low"
    findings = [dict(f, agent=key) for key, value in outputs.items() for f in value.get("findings", [])]
    findings.sort(key=lambda f: ({"high": 0, "medium": 1, "low": 2}[f["severity"]], -f["impact"] * f["confidence"]))
    weighted_score = score
    guardrails = []
    critical_health = any(f["code"] == "medical_claim" and any(re.search(r"cures?|guaranteed", phrase, re.I) for phrase in f["evidence"].get("phrases", [])) for f in findings)
    if score is not None and coverage >= .5:
        cap = 49 if critical_health else 74 if any(f["severity"] == "high" and f["confidence"] >= .85 and f["impact"] >= 20 for f in findings) else 100
        if score > cap:
            score = cap
            guardrails.append({"cap": cap, "reason": "Potentially dangerous health claim" if critical_health else "High-severity, high-confidence finding requires review"})
        risk = "high" if score < 50 else "medium" if score < 75 else "low"
    return {"trust_score": score, "weighted_score": weighted_score, "guardrails": guardrails, "risk": risk, "coverage": round(coverage, 2),
            "components": components, "findings": findings, "weights": WEIGHTS}


def seller_evidence_question(item, signal):
    code, evidence = signal["code"], signal["evidence"]
    listing_id = item["id"]
    if code.startswith("claim_"):
        label = evidence.get("claim", code.removeprefix("claim_").upper())
        return f"Please provide the {label} certificate or approval documentation for {listing_id}, including the issuer, document number, and matching product model."
    if code == "medical_claim":
        phrases = "; ".join(evidence.get("phrases", []))
        return f"Please provide substantiation for the stated claims on {listing_id}: {phrases}."
    if code == "review_burst":
        return f"Please provide order and promotion records for {listing_id} covering {evidence.get('window_start')} to {evidence.get('window_end')} so the review spike can be reconciled with sales."
    if code == "duplicate_phrasing":
        return f"Please explain how reviews for {listing_id} were collected, including any review-writing templates, shared campaigns, or third-party services."
    if code == "incentivized_language":
        return f"Please provide the review solicitation and compensation policy for {listing_id}, including any gifts, refunds, or rewards offered for reviews."
    if code == "seller_swap":
        return f"Please provide documentation authorizing the seller change on {listing_id} from {evidence.get('previous_seller')} to {evidence.get('current_seller')}."
    if code == "price_drop":
        return f"Please explain the price change on {listing_id} from {evidence.get('previous_price')} to {evidence.get('current_price')} {item['currency']}, including any promotion or supplier change."
    if code in ("image_reuse", "brand_metadata_mismatch", "authenticity_claim"):
        return f"Please provide original product photographs and brand or supplier authorization for {listing_id}, with the product model clearly identified."
    return f"For {listing_id}, please provide supporting records addressing this review concern: {signal['title']}."


def plain_report(item, outputs, scoring):
    findings = scoring["findings"]
    score = scoring["trust_score"]
    prefix = f"{item['title']} has a trust score of {score}/100" if score is not None else f"{item['title']} has insufficient evidence"
    summary = prefix + f", with {len(findings)} screening finding{'s' if len(findings) != 1 else ''}."
    if findings:
        summary += " Prioritize " + findings[0]["title"].lower() + " for human review."
    else:
        summary += " No configured red flags were detected in the supplied data."
    questions = []
    for signal in findings[:5]:
        questions.append({"finding": signal["code"], "question": seller_evidence_question(item, signal)})
    edits = []
    for claim in outputs.get("claims", {}).get("claims", []):
        if claim["type"] == "Certification" and not claim["documents"]:
            edits.append({"before": claim["text"], "after": "[Remove until supporting documentation is reviewed]",
                          "reason": "Unsubstantiated certification claim"})
    limitations = list(dict.fromkeys(v for output in outputs.values() for v in output.get("limitations", [])))
    limitations.extend(["Signals are leads for a human reviewer, not proof of fraud or counterfeit goods.",
                        "No listing was approved, removed, or changed on an external marketplace."])
    seller_request = ""
    if questions:
        seller_request = f"Evidence request for {item['title']} ({item['id']})\n\n"
        seller_request += "Please provide the following information for the listing review:\n\n"
        seller_request += "\n\n".join(f"{index + 1}. {question['question']}" for index, question in enumerate(questions))
        seller_request += f"\n\nPlease reference {item['id']} in your response."
    return {"summary": summary, "seller_request": seller_request, "recommended_action": "Request missing evidence" if scoring["risk"] == "insufficient" else
            "Prioritize manual audit" if scoring["risk"] == "high" else
            "Review flagged evidence" if scoring["risk"] == "medium" else "Routine review; retain monitoring",
            "questions": questions, "suggested_edits": edits, "limitations": limitations,
            "engine": "Explainable rules + statistical NLP (no LLM)", "human_review_required": True}


class Orchestrator:
    """Retry failed agents once. Independent detection agents run concurrently."""

    def __init__(self, overrides=None):
        self.functions = {"ingestion": listing_ingestion, "segmentation": review_segmentation,
                          "compliance": listing_compliance, "claims": claim_extraction,
                          "authenticity": review_authenticity, "seller": seller_behavior, "images": image_signals}
        self.functions.update(overrides or {})

    def run(self, item, context=None):
        context = context or {}
        outputs, logs = {}, []
        start = time.perf_counter()

        def call(key):
            begin = time.perf_counter()
            for attempt in (1, 2):
                try:
                    output = self.functions[key](item, context)
                    return key, output, {"agent": key, "status": "completed", "attempts": attempt,
                        "duration_ms": round((time.perf_counter() - begin) * 1000, 2),
                        "finding_count": len(output.get("findings", []))}
                except Exception:
                    if attempt == 2:
                        return key, result(available=False, limitations=[f"{key} failed after two attempts; its evidence was excluded."]), {
                            "agent": key, "status": "failed", "attempts": 2,
                            "duration_ms": round((time.perf_counter() - begin) * 1000, 2), "finding_count": 0}

        for key in ("ingestion", "segmentation"):
            name, output, log = call(key)
            outputs[name] = output
            logs.append(log)
        with ThreadPoolExecutor(max_workers=5, thread_name_prefix="trustlens-agent") as executor:
            futures = [executor.submit(call, key) for key in ("compliance", "claims", "authenticity", "seller", "images")]
            for future in as_completed(futures):
                name, output, log = future.result()
                outputs[name] = output
                logs.append(log)
        begin = time.perf_counter()
        scoring = aggregate(outputs)
        logs.append({"agent": "scoring", "status": "completed", "attempts": 1,
                     "duration_ms": round((time.perf_counter() - begin) * 1000, 2), "finding_count": len(scoring["findings"])})
        begin = time.perf_counter()
        report = plain_report(item, outputs, scoring)
        logs.append({"agent": "report", "status": "completed", "attempts": 1,
                     "duration_ms": round((time.perf_counter() - begin) * 1000, 2), "finding_count": 0})
        duration = round((time.perf_counter() - start) * 1000, 2)
        partial = any(log["status"] == "failed" for log in logs)
        logs.append({"agent": "orchestrator", "status": "partial" if partial else "completed",
                     "attempts": 1, "duration_ms": duration, "finding_count": 0})
        order = {agent["id"]: n for n, agent in enumerate(AGENTS)}
        logs.sort(key=lambda log: order[log["agent"]])
        return {"schema_version": "1.0", "listing_id": item["id"],
                "generated_at": datetime.now(timezone.utc).isoformat(), "partial": partial,
                "input_digest": hashlib.sha256(repr(item).encode()).hexdigest(),
                "duration_ms": duration, "scoring": scoring, "agents": outputs,
                "report": report, "execution": logs}
