"""SQLite persistence. Each operation owns a connection and transaction."""
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .agents import Orchestrator


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class ConflictError(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS listings (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, previous_payload TEXT,
                    report TEXT, status TEXT NOT NULL DEFAULT 'open', notes TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY, listing_id TEXT NOT NULL, report TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, listing_id TEXT, kind TEXT NOT NULL,
                    message TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def count(self):
        with self.db() as db:
            return db.execute("SELECT COUNT(*) FROM listings").fetchone()[0]

    def import_dataset(self, dataset):
        moment = now_iso()
        with self.db() as db:
            current_ids = {r[0] for r in db.execute("SELECT id FROM listings")}
            incoming_ids = {i["id"] for i in dataset["listings"]}
            if len(current_ids | incoming_ids) > 500:
                raise ValueError("This local workspace supports at most 500 listings.")
            for item in dataset["listings"]:
                payload = json.dumps(item, ensure_ascii=False)
                old = db.execute("SELECT payload FROM listings WHERE id=?", (item["id"],)).fetchone()
                if old:
                    db.execute("UPDATE listings SET previous_payload=payload, payload=?, report=NULL, "
                               "status='open', version=version+1, updated_at=? WHERE id=?",
                               (payload, moment, item["id"]))
                else:
                    db.execute("INSERT INTO listings(id,payload,updated_at) VALUES(?,?,?)", (item["id"], payload, moment))
                db.execute("INSERT INTO events(listing_id,kind,message,created_at) VALUES(?,?,?,?)",
                           (item["id"], "import", "Listing updated; analysis required." if old else "Listing imported.", moment))
            db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('dataset',?)",
                       (json.dumps(dataset["metadata"], ensure_ascii=False),))
        return len(dataset["listings"])

    def records(self):
        with self.db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM listings ORDER BY id")]

    @staticmethod
    def summary(row):
        item = json.loads(row["payload"])
        report = json.loads(row["report"]) if row["report"] else None
        scoring = report["scoring"] if report else {}
        reviews = item["reviews"]
        return {"id": item["id"], "title": item["title"], "category": item["category"],
                "price": item["price"], "currency": item["currency"], "region": item["region"],
                "seller": item["seller"]["name"], "review_count": len(reviews),
                "average_rating": round(sum(r["rating"] for r in reviews) / len(reviews), 1) if reviews else None,
                "trust_score": scoring.get("trust_score"), "risk": scoring.get("risk", "pending"),
                "finding_count": len(scoring.get("findings", [])), "status": row["status"],
                "illustration": item.get("illustration", "box"), "version": row["version"],
                "updated_at": row["updated_at"], "analyzed_at": report["generated_at"] if report else None,
                "partial": report["partial"] if report else False,
                "synthetic": "synthetic_scenario" in item}

    def detail(self, listing_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
            if not row:
                return None
            events = [dict(e) for e in db.execute("SELECT * FROM events WHERE listing_id=? ORDER BY id DESC LIMIT 30", (listing_id,))]
            runs = [json.loads(r[0]) for r in db.execute("SELECT report FROM runs WHERE listing_id=? ORDER BY id DESC LIMIT 2", (listing_id,))]
        return {"listing": json.loads(row["payload"]), "report": json.loads(row["report"]) if row["report"] else None,
                "summary": self.summary(row), "notes": row["notes"], "events": events,
                "previous_report": runs[1] if len(runs) > 1 else None}

    def context(self, row):
        memory, images = defaultdict(list), defaultdict(list)
        for other in self.records():
            item = json.loads(other["payload"])
            for image in item["images"]:
                if image.get("fingerprint"):
                    images[image["fingerprint"]].append(item["id"])
            if other["report"]:
                report = json.loads(other["report"])
                for reviewer in report["agents"].get("authenticity", {}).get("flagged_reviewer_ids", []):
                    memory[reviewer].append(item["id"])
        return {"reviewer_memory": dict(memory), "image_index": dict(images),
                "previous_listing": json.loads(row["previous_payload"]) if row.get("previous_payload") else None}

    def analyze(self, listing_id, engine=None):
        with self.db() as db:
            raw = db.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
            if not raw:
                raise KeyError(listing_id)
            row = dict(raw)
        report = (engine or Orchestrator()).run(json.loads(row["payload"]), self.context(row))
        moment = now_iso()
        with self.db() as db:
            cursor = db.execute("UPDATE listings SET report=?, updated_at=? WHERE id=? AND version=?",
                                (json.dumps(report), moment, listing_id, row["version"]))
            if not cursor.rowcount:
                raise ConflictError("Listing changed during analysis. Run the analysis again.")
            db.execute("INSERT INTO runs(listing_id,report,created_at) VALUES(?,?,?)", (listing_id, json.dumps(report), moment))
            # Keep the latest 30 reports per listing to bound local storage.
            db.execute("DELETE FROM runs WHERE listing_id=? AND id NOT IN "
                       "(SELECT id FROM runs WHERE listing_id=? ORDER BY id DESC LIMIT 30)", (listing_id, listing_id))
            db.execute("INSERT INTO events(listing_id,kind,message,created_at) VALUES(?,?,?,?)",
                       (listing_id, "analysis", f"Analysis completed: trust {report['scoring']['trust_score']}/100, "
                        f"{report['scoring']['risk']} risk.", moment))
        return report

    def decide(self, listing_id, status, notes, version):
        if status not in ("open", "needs_review", "reviewed"):
            raise ValueError("Review status must be open, needs_review, or reviewed.")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise ValueError("Review notes must be text of at most 4,000 characters.")
        if isinstance(version, bool) or not isinstance(version, int):
            raise ValueError("A numeric listing version is required.")
        with self.db() as db:
            existing = db.execute("SELECT id FROM listings WHERE id=?", (listing_id,)).fetchone()
            if not existing:
                raise KeyError(listing_id)
            cursor = db.execute("UPDATE listings SET status=?, notes=?, version=version+1, updated_at=? "
                                "WHERE id=? AND version=?", (status, notes, now_iso(), listing_id, version))
            if not cursor.rowcount:
                raise ConflictError("This listing changed in another view. Refresh before saving your review.")
            db.execute("INSERT INTO events(listing_id,kind,message,created_at) VALUES(?,?,?,?)",
                       (listing_id, "review", f"Human review status changed to {status.replace('_', ' ')}.", now_iso()))
        return self.detail(listing_id)

    def overview(self):
        items = [self.summary(row) for row in self.records()]
        scored = [i for i in items if i["trust_score"] is not None]
        distribution = Counter(i["risk"] for i in items)
        categories = defaultdict(list)
        for item in items:
            categories[item["category"]].append(item)
        with self.db() as db:
            activity = [dict(e) for e in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 8")]
            metadata = db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()
            total_runs = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        return {"totals": {"listings": len(items), "reviews": sum(i["review_count"] for i in items),
                           "high_risk": distribution["high"], "needs_review": sum(i["status"] != "reviewed" for i in items),
                           "average_trust": round(sum(i["trust_score"] for i in scored) / len(scored)) if scored else None,
                           "findings": sum(i["finding_count"] for i in items), "stored_runs": total_runs},
                "distribution": dict(distribution),
                "categories": [{"name": name, "total": len(values),
                                "high": sum(i["risk"] == "high" for i in values),
                                "medium": sum(i["risk"] == "medium" for i in values),
                                "low": sum(i["risk"] == "low" for i in values)}
                               for name, values in sorted(categories.items())],
                "priority": sorted(items, key=lambda i: (i["trust_score"] is None, i["trust_score"] or 0))[:5],
                "activity": activity, "dataset": json.loads(metadata[0]) if metadata else {},
                "last_analysis": max((i["analyzed_at"] for i in items if i["analyzed_at"]), default=None)}

    def listing_page(self, query):
        items = [self.summary(row) for row in self.records()]
        categories = sorted({i["category"] for i in items})
        search = query.get("q", "").strip().casefold()
        if search:
            items = [i for i in items if search in " ".join(str(i[k]) for k in ("title", "id", "seller", "category")).casefold()]
        for key in ("risk", "category", "status"):
            if query.get(key):
                items = [i for i in items if i[key] == query[key]]
        sort = query.get("sort", "trust")
        if sort == "title":
            items.sort(key=lambda i: i["title"].casefold())
        elif sort == "reviews":
            items.sort(key=lambda i: -i["review_count"])
        elif sort == "recent":
            items.sort(key=lambda i: i["updated_at"], reverse=True)
        else:
            items.sort(key=lambda i: (i["trust_score"] is None, i["trust_score"] or 0))
        try:
            size = max(1, min(100, int(query.get("size", 10))))
            page = max(1, int(query.get("page", 1)))
        except (ValueError, TypeError):
            raise ValueError("Page and size must be whole numbers.")
        total = len(items)
        pages = max(1, math_ceil(total / size))
        page = min(page, pages)
        return {"items": items[(page - 1) * size:page * size], "total": total, "page": page,
                "pages": pages, "size": size, "categories": categories}


def math_ceil(value):
    return int(-(-value // 1))
