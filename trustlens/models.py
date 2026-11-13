"""Input contracts shared by the server and every analysis agent."""
from copy import deepcopy
from datetime import datetime, timezone
import math
import re

MAX_LISTINGS = 50
MAX_REVIEWS = 5000
REGIONS = ("IN", "US", "EU", "Global")


class ValidationError(ValueError):
    pass


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        raise ValidationError("Dates must use ISO 8601, for example 2026-11-13T12:00:00Z.")


def text(value, name, limit=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f"{name} must be non-empty text, at most {limit} characters.")
    return value.strip()


def number(value, name, minimum=0, maximum=1_000_000_000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError(f"{name} must be a finite number.")
    if not minimum <= value <= maximum:
        raise ValidationError(f"{name} must be between {minimum} and {maximum}.")
    return value


def identifier(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value):
        raise ValidationError(f"{name} must contain 1–80 letters, digits, underscores, or hyphens.")
    return value


def validate_listing(raw):
    if not isinstance(raw, dict):
        raise ValidationError("Each listing must be a JSON object.")
    item = deepcopy(raw)
    for key in ("id", "title", "category", "description", "price", "seller", "reviews"):
        if key not in item:
            raise ValidationError(f"Listing is missing required field: {key}.")
    identifier(item["id"], "Listing ID")
    for key, limit in (("title", 250), ("category", 80), ("description", 20000)):
        item[key] = text(item[key], key, limit)
    number(item["price"], "Price")
    item.setdefault("currency", "INR")
    if item["currency"] not in ("INR", "USD", "EUR", "GBP"):
        raise ValidationError("Currency must be INR, USD, EUR, or GBP.")
    item.setdefault("region", "IN")
    if item["region"] not in REGIONS:
        raise ValidationError("Region must be IN, US, EU, or Global.")
    item.setdefault("listed_at", datetime.now(timezone.utc).isoformat())
    timestamp(item["listed_at"])
    seller = item["seller"]
    if not isinstance(seller, dict):
        raise ValidationError("Seller must be an object with id, name, and created_at.")
    for key in ("id", "name", "created_at"):
        if key not in seller:
            raise ValidationError(f"Seller is missing {key}.")
    identifier(seller["id"], "Seller ID")
    text(seller["name"], "Seller name", 200)
    timestamp(seller["created_at"])
    for key in ("sales_count", "relisting_count", "prior_takedowns"):
        if key in seller:
            number(seller[key], f"Seller {key}", 0, 1_000_000_000)
    reviews = item["reviews"]
    if not isinstance(reviews, list) or len(reviews) > MAX_REVIEWS:
        raise ValidationError(f"Reviews must be an array of at most {MAX_REVIEWS} records.")
    seen = set()
    for review in reviews:
        if not isinstance(review, dict):
            raise ValidationError("Each review must be an object.")
        for key in ("id", "reviewer_id", "rating", "text", "date"):
            if key not in review:
                raise ValidationError(f"Review is missing {key}.")
        identifier(review["id"], "Review ID")
        identifier(review["reviewer_id"], "Reviewer ID")
        if review["id"] in seen:
            raise ValidationError(f"Duplicate review ID: {review['id']}.")
        seen.add(review["id"])
        number(review["rating"], "Review rating", 1, 5)
        text(review["text"], "Review text", 5000)
        timestamp(review["date"])
        if "verified_purchase" in review and not isinstance(review["verified_purchase"], bool):
            raise ValidationError("verified_purchase must be true or false.")
        if "reviewer_created_at" in review:
            timestamp(review["reviewer_created_at"])
        if "network_hash" in review:
            text(review["network_hash"], "network_hash", 150)
    for key in ("price_history", "images", "certifications", "stock_history"):
        item.setdefault(key, [])
        if not isinstance(item[key], list) or len(item[key]) > 1000:
            raise ValidationError(f"{key} must be an array with at most 1,000 records.")
    for point in item["price_history"]:
        if not isinstance(point, dict) or not all(k in point for k in ("date", "price")):
            raise ValidationError("Each price history point needs date and price.")
        timestamp(point["date"])
        number(point["price"], "Historical price")
    for image in item["images"]:
        if not isinstance(image, dict):
            raise ValidationError("Each image must be a metadata object.")
        for key in ("fingerprint", "alt", "catalog_brand", "observed_brand"):
            if key in image:
                text(image[key], f"Image {key}", 500)
    for certificate in item["certifications"]:
        if not isinstance(certificate, dict) or not isinstance(certificate.get("name"), str):
            raise ValidationError("Each certification needs a name.")
        if "document_reference" in certificate:
            text(certificate["document_reference"], "Document reference", 500)
    if "previous_version" in item:
        previous = item["previous_version"]
        if not isinstance(previous, dict):
            raise ValidationError("previous_version must be an object.")
        for key in ("title", "description", "seller_id"):
            if key in previous:
                text(previous[key], f"Previous {key}", 20000)
        if "price" in previous:
            number(previous["price"], "Previous price")
    return item


def validate_dataset(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("listings"), list):
        raise ValidationError('Upload a JSON object with a "listings" array.')
    if not 1 <= len(raw["listings"]) <= MAX_LISTINGS:
        raise ValidationError(f"Provide 1–{MAX_LISTINGS} listings per import.")
    if not isinstance(raw.get("metadata", {}), dict):
        raise ValidationError("Dataset metadata must be an object.")
    items = [validate_listing(item) for item in raw["listings"]]
    if len({item["id"] for item in items}) != len(items):
        raise ValidationError("Listing IDs must be unique within the import.")
    if sum(len(i["reviews"]) for i in items) > 25000:
        raise ValidationError("An import may contain at most 25,000 reviews in total.")
    return {"metadata": deepcopy(raw.get("metadata", {})), "listings": items}
