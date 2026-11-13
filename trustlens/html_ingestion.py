"""Extract Product JSON-LD from supplied HTML without fetching URLs or running scripts."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json

from .models import ValidationError, identifier, validate_listing


class ProductParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_json = False
        self.buffer = []
        self.documents = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self.in_json = True
            self.buffer = []

    def handle_data(self, data):
        if self.in_json:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_json:
            self.in_json = False
            try:
                self.documents.append(json.loads("".join(self.buffer)))
            except (ValueError, TypeError):
                pass


def walk_products(value):
    if isinstance(value, list):
        for entry in value:
            yield from walk_products(entry)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if types == "Product" or isinstance(types, list) and "Product" in types:
            yield value
        if "@graph" in value:
            yield from walk_products(value["@graph"])


def extract_product(html, listing_id, seller, region="IN"):
    if not isinstance(html, str) or len(html) > 2_000_000:
        raise ValidationError("Supply product HTML text of at most 2,000,000 characters.")
    identifier(listing_id, "Listing ID")
    if not isinstance(seller, dict):
        raise ValidationError("A seller profile is required; account history cannot be inferred from HTML.")
    parser = ProductParser()
    parser.feed(html)
    products = [p for document in parser.documents for p in walk_products(document)]
    if not products:
        raise ValidationError("No valid Product JSON-LD was found. Supply a JSON dataset instead.")
    if len(products) > 1:
        raise ValidationError("The HTML contains multiple products. Provide a page with one Product record.")
    product = products[0]
    offers = product.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        raise ValidationError("The Product record needs an offers object with a price.")
    try:
        price = float(offers["price"])
    except (ValueError, TypeError, KeyError):
        raise ValidationError("The Product JSON-LD needs a numeric offers.price.")
    brand = product.get("brand", "")
    if isinstance(brand, dict):
        brand = brand.get("name", "")
    raw_images = product.get("image", [])
    if isinstance(raw_images, (str, dict)):
        raw_images = [raw_images]
    images = []
    for value in raw_images if isinstance(raw_images, list) else []:
        url = value.get("url") if isinstance(value, dict) else value
        if isinstance(url, str):
            # URLs are recorded as source references, never fetched or used as fingerprints.
            images.append({"alt": str(product.get("name", "Product")), "source_url": url, "source": "supplied_html"})
    raw_reviews = product.get("review", [])
    if isinstance(raw_reviews, dict):
        raw_reviews = [raw_reviews]
    reviews = []
    for index, review in enumerate(raw_reviews if isinstance(raw_reviews, list) else []):
        if not isinstance(review, dict):
            continue
        if not all(k in review for k in ("datePublished", "reviewBody", "reviewRating")):
            continue
        rating = review["reviewRating"]
        try:
            rating = float(rating.get("ratingValue") if isinstance(rating, dict) else rating)
        except (TypeError, ValueError):
            raise ValidationError("A Product review contains an invalid rating.")
        author = review.get("author", {"name": "unknown-" + str(index)})
        author_key = json.dumps(author, sort_keys=True)
        reviews.append({"id": f"{listing_id}-HTML-{index+1}",
                        "reviewer_id": "HTML-" + hashlib.sha256(author_key.encode()).hexdigest()[:20],
                        "rating": rating, "date": review["datePublished"], "text": review["reviewBody"]})
    item = {"id": listing_id, "title": product.get("name"), "description": product.get("description"),
            "category": product.get("category", "Uncategorized"), "price": price,
            "currency": offers.get("priceCurrency", "INR"), "region": region, "seller": seller,
            "brand": brand, "reviews": reviews, "images": images,
            "listed_at": product.get("datePublished", datetime.now(timezone.utc).isoformat()),
            "ingestion_source": "Supplied Product JSON-LD; no network fetch"}
    return validate_listing(item)
