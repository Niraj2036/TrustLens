"""Analyze a dataset without starting the web server."""
import argparse
import json
from pathlib import Path
import tempfile
from app import Application
from trustlens.models import validate_dataset

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Run the TrustLens pipeline from the command line.")
    parser.add_argument("input", nargs="?", type=Path, default=ROOT/"datasets/trustlens_dataset.json")
    parser.add_argument("--output", type=Path, default=ROOT/"reports/trust_reports.json")
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8-sig"))
    dataset = validate_dataset(source)
    with tempfile.TemporaryDirectory() as directory:
        application = Application(Path(directory)/"analysis.db",seed=False)
        application.store.import_dataset(dataset)
        reports = []
        for item in dataset["listings"]:
            report = application.store.analyze(item["id"])
            reports.append(report)
            print(f"{item['id']}: trust {report['scoring']['trust_score']}/100, {report['scoring']['risk']} risk")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({"dataset":dataset["metadata"],"reports":reports},indent=2,ensure_ascii=False),encoding="utf-8")
        application.close()
    print(f"Saved {len(reports)} reports to {args.output.resolve()}")


if __name__ == "__main__":
    main()
