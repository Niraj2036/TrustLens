"""Recreate the original, synthetic classroom dataset with a fixed random seed."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import hashlib
import json
import random
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets"
NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)
RNG = random.Random(11013)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


SPECS = [
    ("TL-1001", "UltraCharge Pro 20000mAh Power Bank", "Electronics", 1299, 340, "high", "VoltEdge Deals", 14,
     "UltraCharge Pro 20000mAh power bank with CE certified and UL certified safety. Medical grade casing, 2-year warranty and 30-day returns. Dual USB ports for everyday charging.", "powerbank"),
    ("TL-1002", "VitaPure Daily Herbal Capsules", "Health & wellness", 899, 94, "high", "VitaPure Direct", 22,
     "Clinically proven herbal capsules. Cures diabetes with guaranteed weight loss. FDA approved formula. A 30-day return policy applies to unopened packs. Store in a cool place.", "bottle"),
    ("TL-1003", "SoundPeak Air Wireless Earbuds", "Electronics", 1599, 156, "high", "AudioRush Store", 31,
     "Original brand wireless earbuds, 100% authentic. Noise isolation, pocket charging case, and touch controls. 1-year warranty with 14-day returns. CE certified.", "earbuds"),
    ("TL-1004", "TerraSip Insulated Steel Bottle", "Home & kitchen", 749, 64, "low", "Terra Home", 840,
     "750mL stainless steel bottle with a screw-top lid. BPA-free cap, reusable packaging, and an easy-clean opening. 1-year warranty and 30-day returns. Wash by hand.", "flask"),
    ("TL-1005", "LumaDesk Adjustable LED Lamp", "Home & kitchen", 1199, 88, "medium", "Bright Living", 290,
     "Adjustable desk lamp with three brightness levels and a flexible neck. UL certified electronics. A 1-year warranty covers manufacturing defects. Includes USB cable; 14-day returns.", "lamp"),
    ("TL-1006", "TrailForm Everyday Backpack", "Fashion & accessories", 1899, 72, "low", "TrailForm Outfitters", 1150,
     "Everyday backpack with padded laptop sleeve, adjustable shoulder straps, and a water-resistant outer layer. 2-year warranty on stitching. 30-day returns on unused items.", "backpack"),
    ("TL-1007", "DewKind Hydrating Face Serum", "Beauty & care", 649, 110, "medium", "DewKind Beauty", 210,
     "Lightweight daily serum for a moisturized skin feel. Clinically proven hydration and medical grade ingredients. Fragrance free. Patch test before use. 14-day returns on sealed products.", "serum"),
    ("TL-1008", "LinkLine Braided USB-C Cable", "Electronics", 349, 54, "low", "LinkLine Official", 980,
     "A 1.5 metre braided charging cable with reinforced connectors. Supports compatible USB-C devices. 1-year warranty covers manufacturing defects, with 30-day returns.", "cable"),
    ("TL-1009", "PulseFit Active Smartwatch", "Electronics", 1999, 96, "high", "Pulse Deals", 18,
     "Activity watch with step tracking, heart-rate estimates, and phone notifications. 1-year warranty and 7-day returns. Not intended for medical diagnosis. Water resistance is seller-stated.", "watch"),
    ("TL-1010", "BrewMill Manual Coffee Grinder", "Home & kitchen", 2199, 80, "low", "BrewMill Studio", 730,
     "Manual coffee grinder with stainless steel body and adjustable ceramic burrs. Suitable for home brewing. Replacement parts are available. 2-year warranty and 30-day returns.", "grinder"),
    ("TL-1011", "Grounded Everyday Yoga Mat", "Sports & outdoors", 999, 48, "low", "Grounded Goods", 650,
     "Six millimetre exercise mat with a textured surface and carry strap. Wipe clean after use and allow to dry before rolling. 1-year warranty and 30-day returns on unused products.", "mat"),
    ("TL-1012", "StudioArc Over-Ear Headphones", "Electronics", 2499, 66, "medium", "StudioArc Audio", 420,
     "Over-ear headphones with adjustable headband, wired connection, and replaceable ear cushions. 1-year warranty and 30-day returns. Suitable for desk listening and calls.", "headphones"),
]


def ordinary_review(noun, index):
    openings = ["After a few weeks of use", "I tested this over the weekend", "For my daily routine",
                "Compared with my previous purchase", "Having used it during travel", "On the first day",
                "After trying the main features", "For the price I paid", "After reading the instructions",
                "During regular use at home", "When I unpacked my order", "After using it for a month"]
    observations = ["the finish feels consistent", "the size fits my setup", "the controls are straightforward",
                    "the packaging protected everything", "the materials feel as described", "the weight is manageable",
                    "it performs adequately", "cleaning has been simple", "the fit takes some adjustment",
                    "the instructions could be clearer", "the color matches the pictures", "the basic function works"]
    endings = ["I will see how it holds up over time.", "Delivery took three days to my address.",
               "One small detail could be improved.", "I kept the receipt for the warranty.",
               "I bought it for my own use.", "The supplied accessory was useful.",
               "A family member found it easy to use.", "It suits the purpose I bought it for.",
               "I have no long-term durability observations yet.", "I would check the measurements before ordering."]
    choice = RNG.sample(range(len(openings) * len(observations) * len(endings)), 1)[0]
    a, rest = divmod(choice, len(observations) * len(endings))
    b, c = divmod(rest, len(endings))
    return f"{openings[a]}, {observations[b]} for this {noun}. {endings[c]} Observation {index + 1}."


def build():
    listings = []
    for pos, (lid, title, category, price, count, scenario, seller_name, age, description, illustration) in enumerate(SPECS):
        seller = {"id": f"SELLER-{pos + 1:03}", "name": seller_name,
                  "created_at": iso(NOW - timedelta(days=age)), "sales_count": count * (2 if scenario == "high" else 8),
                  "relisting_count": 7 if pos in (0, 8) else 5 if pos == 2 else 0,
                  "prior_takedowns": 2 if pos in (1, 2) else 1 if pos == 8 else 0}
        listing_age = 21 if pos == 0 else 18 if pos == 8 else min(age - 2, 170)
        reviews = []
        for n in range(count):
            review_date = NOW - timedelta(days=RNG.uniform(.2, listing_age), minutes=n % 59)
            review_text = ordinary_review(illustration, n)
            reviewer = f"READER-{pos + 1:02}-{n + 1:04}"
            verified = RNG.random() < (.22 if scenario == "high" else .9)
            rating = RNG.choices([2, 3, 4, 5], [2, 8, 34, 56])[0]
            review = {"id": f"{lid}-R{n + 1:04}", "reviewer_id": reviewer,
                      "date": iso(review_date), "rating": rating, "text": review_text,
                      "verified_purchase": verified,
                      "reviewer_created_at": iso(NOW - timedelta(days=RNG.randint(60, 1800)))}
            if pos in (0, 2, 8) and n < (210 if pos == 0 else count // 2):
                review["date"] = iso(NOW - timedelta(days=9) + timedelta(minutes=n * (10 if pos == 0 else 18)))
                templates = ["Changed my life, arrived fast. Amazing quality and the best purchase I have made.",
                             "Excellent product, arrived fast. Amazing quality and the best purchase I have made.",
                             "Perfect purchase, changed my life. Amazing quality and arrived fast at my door."]
                review["text"] = templates[n % 3]
                review["rating"] = 5
                review["verified_purchase"] = False
                review["reviewer_id"] = f"CLUSTER-{n + 1:04}"
                review["network_hash"] = hashlib.sha256(f"synthetic-network-{n % 3}".encode()).hexdigest()[:24]
                review["reviewer_created_at"] = iso(NOW - timedelta(days=12))
            if pos == 0 and n >= 210:
                # Keep ordinary reviews outside the known synthetic burst.
                days = RNG.uniform(12, 20) if n % 2 else RNG.uniform(.2, 5)
                review["date"] = iso(NOW - timedelta(days=days))
            if scenario == "high" and n % 19 == 0:
                review["text"] += " The seller offered a gift card in exchange for five stars."
            if pos == 11 and n < 12:
                review["text"] = "Comfortable fit and a clear sound profile for calls. Easy to recommend for desk use."
            reviews.append(review)
        fingerprint_key = "shared-audio-stock" if pos in (2, 11) else lid
        images = [{"id": f"{lid}-IMG1", "alt": title + " product illustration",
                   "fingerprint": hashlib.sha256(fingerprint_key.encode()).hexdigest(),
                   "source": "synthetic_metadata", "catalog_brand": "SoundPeak" if pos == 2 else seller_name,
                   "observed_brand": "SoundPeaq" if pos == 2 else seller_name}]
        old_price = round(price / .48) if pos == 8 else round(price * 1.6) if pos == 0 else price
        listing = {"id": lid, "title": title, "description": description, "category": category,
                   "brand": seller_name.split()[0], "price": price, "currency": "INR", "region": "IN",
                   "listed_at": iso(NOW - timedelta(days=listing_age)), "seller": seller,
                   "reviews": reviews, "images": images, "illustration": illustration,
                   "price_history": [{"date": iso(NOW - timedelta(days=listing_age)), "price": old_price},
                                     {"date": iso(NOW - timedelta(days=1)), "price": price}],
                   "stock_history": [{"date": iso(NOW - timedelta(days=2)), "quantity": 40 + pos * 7}],
                   "certifications": [],
                   "synthetic_scenario": {"intended_risk": scenario,
                                          "note": "Scenario label for classroom discussion; never consumed by the scoring engine."}}
        if pos == 8:
            listing["previous_version"] = {"title": title, "description": description.replace("heart-rate estimates", "activity estimates"),
                                           "seller_id": "SELLER-ARCHIVE", "price": old_price,
                                           "captured_at": iso(NOW - timedelta(days=15))}
        if pos == 4:
            listing["certifications"] = []  # Deliberately unsupported UL claim.
        listings.append(listing)
    return {"schema_version": "1.0", "metadata": {
        "name": "TrustLens synthetic marketplace dataset", "version": "1.0",
        "created_at": iso(NOW), "synthetic": True, "license": "CC0-1.0",
        "seed": 11013, "listing_count": len(listings),
        "review_count": sum(len(i["reviews"]) for i in listings),
        "source": "Original programmatically generated classroom scenarios; no scraped marketplace data or real people.",
        "limitations": "Not representative training data. Scenario labels are illustrative and are not ground truth about real products.",
        "reference_date": NOW.date().isoformat()}, "listings": listings}


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    dataset = build()
    (OUT / "trustlens_dataset.json").write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUT / "listings.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["id", "title", "category", "price", "currency", "region", "seller_id", "review_count", "intended_risk"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in dataset["listings"]:
            writer.writerow({**{k: item[k] for k in fields[:6]}, "seller_id": item["seller"]["id"],
                             "review_count": len(item["reviews"]), "intended_risk": item["synthetic_scenario"]["intended_risk"]})
    with (OUT / "reviews.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["listing_id", "id", "reviewer_id", "rating", "date", "verified_purchase", "text"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in dataset["listings"]:
            for review in item["reviews"]:
                writer.writerow({"listing_id": item["id"], **{k: review[k] for k in fields[1:]}})
    (OUT / "README.md").write_text(
        "# TrustLens classroom dataset\n\n"
        "12 fictional listings and 1,268 synthetic reviews, generated with seed 11013.\n"
        "Reference date: 13 November 2026. Prices are INR. License: CC0-1.0.\n\n"
        "The JSON contains listings, seller history, dated reviews, price/stock history,\n"
        "claim documentation fields, and synthetic image fingerprints. No real personal\n"
        "data, images, marketplace scraping, or actual fraud allegations are included.\n\n"
        "Scenarios include review bursts, repeated text, incentives, unsupported claims,\n"
        "seller changes, and ordinary listings. intended_risk is a scenario design label;\n"
        "it is ignored by the engine and is not a validated ML benchmark label.\n"
        "The data is suitable for a demonstration, not for training or validating a\n"
        "production fraud detector. Image metadata is simulated, not pixel evidence.\n\n"
        "Files: trustlens_dataset.json (application input), listings.csv (listing summary),\n"
        "reviews.csv (review records), schema.json (input schema), and this README.\n"
        "Recreate from the project root: python scripts/generate_dataset.py\n"
        "Import through the dashboard's Import listings action or use the default seed.\n",
        encoding="utf-8")
    review_schema = {
        "type": "object", "required": ["id", "reviewer_id", "date", "rating", "text"],
        "properties": {"rating": {"type": "number", "minimum": 1, "maximum": 5},
                       "verified_purchase": {"type": "boolean"}}
    }
    listing_schema = {
        "type": "object",
        "required": ["id", "title", "description", "category", "price", "seller", "reviews"],
        "properties": {
            "id": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$"},
            "title": {"type": "string", "maxLength": 250},
            "description": {"type": "string", "maxLength": 20000},
            "category": {"type": "string", "maxLength": 80},
            "price": {"type": "number", "minimum": 0},
            "currency": {"enum": ["INR", "USD", "EUR", "GBP"]},
            "region": {"enum": ["IN", "US", "EU", "Global"]},
            "seller": {"type": "object", "required": ["id", "name", "created_at"]},
            "reviews": {"type": "array", "maxItems": 5000, "items": review_schema}
        }
    }
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "TrustLens dataset", "type": "object", "required": ["listings"],
        "properties": {"metadata": {"type": "object"},
                       "listings": {"type": "array", "minItems": 1, "maxItems": 50, "items": listing_schema}}
    }
    (OUT / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    with zipfile.ZipFile(ROOT / "trustlens_dataset.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("trustlens_dataset.json", "listings.csv", "reviews.csv", "schema.json", "README.md"):
            archive.write(OUT / name, arcname="trustlens_dataset/" + name)
    print(f"Created {len(dataset['listings'])} listings and {dataset['metadata']['review_count']} reviews; JSON and ZIP ready.")
