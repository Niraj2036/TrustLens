"""TrustLens HTTP application. Start with: python app.py"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse, unquote
import uuid

from trustlens.agents import AGENTS, RULES, WEIGHTS
from trustlens.models import ValidationError, validate_dataset
from trustlens.store import Store, ConflictError
from trustlens.html_ingestion import extract_product

ROOT = Path(__file__).resolve().parent
MAX_BODY = 16 * 1024 * 1024


class Application:
    def __init__(self, db_path=None, seed=True):
        self.store = Store(db_path or ROOT / "data" / "trustlens.sqlite3")
        self.jobs = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="trustlens-job")
        if seed and self.store.count() == 0:
            source = json.loads((ROOT / "datasets" / "trustlens_dataset.json").read_text(encoding="utf-8-sig"))
            self.store.import_dataset(validate_dataset(source))
        if seed:
            pending = [r["id"] for r in self.store.records() if not r["report"]]
            for listing_id in pending:
                self.store.analyze(listing_id)

    def start_job(self, ids):
        if not isinstance(ids, list) or not ids or len(ids) > 500 or not all(isinstance(i, str) for i in ids):
            raise ValidationError("Provide a non-empty listing_ids array with at most 500 IDs.")
        ids = list(dict.fromkeys(ids))
        known = {row["id"] for row in self.store.records()}
        if set(ids) - known:
            raise ValidationError("One or more listing IDs were not found.")
        with self.lock:
            active = next((j for j in self.jobs.values() if j["status"] in ("queued", "running")), None)
            if active:
                raise ConflictError("An analysis is already running. Wait for it to finish, then retry.")
            job_id = uuid.uuid4().hex
            job = {"id": job_id, "status": "queued", "total": len(ids), "completed": 0,
                   "current": None, "errors": [], "created_at": datetime.now(timezone.utc).isoformat()}
            self.jobs[job_id] = job
            while len(self.jobs) > 30:
                self.jobs.pop(next(iter(self.jobs)))
        self.executor.submit(self.run_job, job_id, ids)
        return dict(job)

    def run_job(self, job_id, ids):
        with self.lock:
            self.jobs[job_id]["status"] = "running"
        for listing_id in ids:
            with self.lock:
                self.jobs[job_id]["current"] = listing_id
            try:
                self.store.analyze(listing_id)
            except Exception as error:
                with self.lock:
                    self.jobs[job_id]["errors"].append({"listing_id": listing_id,
                        "message": str(error) if isinstance(error, ConflictError) else "Analysis failed. Retry this listing."})
            finally:
                with self.lock:
                    self.jobs[job_id]["completed"] += 1
        with self.lock:
            job = self.jobs[job_id]
            job["status"] = "partial" if job["errors"] else "completed"
            job["current"] = None

    def job(self, job_id):
        with self.lock:
            value = self.jobs.get(job_id)
            return json.loads(json.dumps(value)) if value else None

    def close(self):
        self.executor.shutdown(wait=True)


def make_handler(application):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TrustLens/1.0"

        def log_message(self, format, *args):
            # Do not log imported text, notes, or request bodies.
            pass

        def response(self, status, value, mime="application/json; charset=utf-8", filename=None):
            data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode() if mime.startswith("application/json") and not isinstance(value, bytes) else value
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def body(self):
            if self.headers.get("Transfer-Encoding"):
                raise ValidationError("Chunked requests are not supported.")
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > MAX_BODY:
                raise ValidationError("Request body must be between 1 byte and 16 MB.")
            raw = self.rfile.read(length)
            try:
                value = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, UnicodeDecodeError):
                raise ValidationError("The request is not valid UTF-8 JSON.")
            if not isinstance(value, dict):
                raise ValidationError("The request must be a JSON object.")
            return value

        def allowed_request(self, mutation=False):
            host = self.headers.get("Host", "")
            expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if host not in expected:
                self.response(403, {"error": "This application accepts localhost requests only."})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{h}" for h in expected}:
                self.response(403, {"error": "Cross-origin requests are not allowed."})
                return False
            if mutation and "application/json" not in self.headers.get("Content-Type", ""):
                self.response(415, {"error": "Use Content-Type: application/json."})
                return False
            return True

        def do_GET(self):
            if not self.allowed_request():
                return
            try:
                path = unquote(urlparse(self.path).path)
                query = {k: v[-1] for k, v in parse_qs(urlparse(self.path).query).items()}
                if path == "/api/health":
                    return self.response(200, {"status": "ok", "engine": "explainable-rules", "version": "1.0.0"})
                if path == "/api/overview":
                    return self.response(200, application.store.overview())
                if path == "/api/config":
                    return self.response(200, {"agents": AGENTS, "weights": WEIGHTS, "rules": RULES})
                if path == "/api/listings":
                    return self.response(200, application.store.listing_page(query))
                if path.startswith("/api/listings/"):
                    parts = path.split("/")
                    detail = application.store.detail(parts[3])
                    if not detail:
                        return self.response(404, {"error": "Listing not found."})
                    if len(parts) == 5 and parts[4] == "report":
                        if not detail["report"]:
                            return self.response(409, {"error": "Analyze this listing before exporting a report."})
                        return self.response(200, detail["report"], filename=parts[3] + "-trust-report.json")
                    if len(parts) == 4:
                        return self.response(200, detail)
                if path.startswith("/api/jobs/"):
                    job = application.job(path.rsplit("/", 1)[-1])
                    return self.response(200 if job else 404, job or {"error": "Analysis job not found."})
                downloads = {"/api/dataset": (ROOT / "datasets" / "trustlens_dataset.json", "application/json; charset=utf-8"),
                             "/api/dataset/zip": (ROOT / "trustlens_dataset.zip", "application/zip"),
                             "/api/dataset/schema": (ROOT / "datasets" / "schema.json", "application/json; charset=utf-8")}
                if path in downloads:
                    file, mime = downloads[path]
                    return self.response(200, file.read_bytes(), mime, file.name)
                static = {"/": ("index.html", "text/html; charset=utf-8"),
                          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                          "/tokens.css": ("tokens.css", "text/css; charset=utf-8"),
                          "/favicon.svg": ("favicon.svg", "image/svg+xml")}
                if path in static:
                    name, mime = static[path]
                    return self.response(200, (ROOT / "web" / name).read_bytes(), mime)
                return self.response(404, {"error": "Page not found."})
            except (ValidationError, ValueError) as error:
                self.response(400, {"error": str(error)})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.response(500, {"error": "The server could not complete this request. Check the local terminal and retry."})

        def do_POST(self):
            if not self.allowed_request(mutation=True):
                return
            try:
                path = urlparse(self.path).path
                body = self.body()
                if path == "/api/import/html":
                    item = extract_product(body.get("html"), body.get("listing_id"), body.get("seller"), body.get("region", "IN"))
                    application.store.import_dataset({"metadata": {"source": "Supplied Product JSON-LD"}, "listings": [item]})
                    return self.response(201, {"imported": 1, "listing_ids": [item["id"]]})
                if path == "/api/import":
                    dataset = validate_dataset(body)
                    imported = application.store.import_dataset(dataset)
                    return self.response(201, {"imported": imported, "listing_ids": [i["id"] for i in dataset["listings"]]})
                if path == "/api/analyze":
                    ids = body.get("listing_ids")
                    if ids is None:
                        ids = [row["id"] for row in application.store.records()]
                    return self.response(202, application.start_job(ids))
                if path.startswith("/api/listings/") and path.endswith("/decision"):
                    parts = path.split("/")
                    if len(parts) == 5:
                        detail = application.store.decide(parts[3], body.get("status"), body.get("notes", ""), body.get("version"))
                        return self.response(200, detail)
                self.response(404, {"error": "Action not found."})
            except ConflictError as error:
                self.response(409, {"error": str(error)})
            except (ValidationError, ValueError) as error:
                self.response(400, {"error": str(error)})
            except KeyError:
                self.response(404, {"error": "Listing not found."})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.response(500, {"error": "The operation failed. Your saved data is unchanged; retry from the current view."})
    return Handler


def main():
    parser = argparse.ArgumentParser(description="Start the local TrustLens workbench.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "trustlens.sqlite3")
    parser.add_argument("--no-seed", action="store_true", help="Start with an empty workspace.")
    args = parser.parse_args()
    print("Preparing TrustLens local workspace...", flush=True)
    application = Application(args.db, seed=not args.no_seed)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(application))
    except OSError as error:
        application.close()
        raise SystemExit(f"Could not open port {args.port}: {error}. Try --port 8001.")
    print(f"TrustLens is ready at http://127.0.0.1:{args.port}", flush=True)
    print("Press Ctrl+C to stop. Dataset: datasets/trustlens_dataset.json and trustlens_dataset.zip", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TrustLens.", flush=True)
    finally:
        server.server_close()
        application.close()


if __name__ == "__main__":
    main()
