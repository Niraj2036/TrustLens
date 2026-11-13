import json
import unittest
from trustlens.html_ingestion import extract_product
from trustlens.models import ValidationError
from trustlens.agents import image_signals

SELLER = {"id":"HTML-SELLER","name":"HTML store","created_at":"2025-01-01T00:00:00Z"}


def page(product):
    return '<html><script type="application/ld+json">'+json.dumps(product)+'</script></html>'


PRODUCT = {"@type":"Product","name":"Test lamp",
           "description":"An adjustable desk lamp with a flexible neck, USB cable, and 1-year warranty.",
           "category":"Home & kitchen", "offers":{"price":"999","priceCurrency":"INR"},
           "image":"https://example.com/image.png"}


class HtmlTests(unittest.TestCase):
    def test_extracts_product_json_ld(self):
        listing = extract_product(page(PRODUCT),"HTML-01",SELLER)
        self.assertEqual(listing["price"],999)
        self.assertEqual(listing["seller"],SELLER)
        self.assertEqual(listing["images"][0]["source_url"],PRODUCT["image"])
        self.assertNotIn("fingerprint",listing["images"][0])

    def test_graph_records_are_supported(self):
        listing = extract_product(page({"@graph":[{"@type":"WebPage"},PRODUCT]}),"HTML-01",SELLER)
        self.assertEqual(listing["title"],PRODUCT["name"])

    def test_missing_product_fails_clearly(self):
        with self.assertRaises(ValidationError):
            extract_product("<p>No structured product here.</p>","HTML-01",SELLER)

    def test_seller_is_never_invented(self):
        with self.assertRaises(ValidationError):
            extract_product(page(PRODUCT),"HTML-01",None)

    def test_multiple_products_are_not_silently_combined(self):
        with self.assertRaises(ValidationError):
            extract_product(page([PRODUCT,PRODUCT]),"HTML-01",SELLER)

    def test_image_url_is_not_an_image_match(self):
        listing = extract_product(page(PRODUCT),"HTML-01",SELLER)
        output = image_signals(listing,{})
        self.assertFalse(output["available"])
        self.assertEqual(output["findings"],[])
