# TrustLens

TrustLens is a local Product Listing and Review Trust Agent for e-commerce. It ingests
product listings, reviews, and supplied seller information, runs ten cooperating analysis
agents, and gives a human reviewer an evidence-backed trust report. It never approves or
removes a marketplace listing.

The problem is that ratings alone cannot establish trust. Review bursts, repeated phrases,
incentives, unsupported product claims, seller changes, and reused image metadata need to be
examined together. TrustLens organizes these observations into a case that a person can inspect.

## What belongs on GitHub

The root .gitignore uses an allowlist: Git includes the application source, its tests, the
dataset generator, runtime configuration, and this README. All other files stay local.

| Included path | Purpose |
|---|---|
| app.py | Local HTTP server, API routes, and background analysis jobs |
| analyze.py | Command-line dataset analysis and report export |
| trustlens/*.py | Input validation, ten-agent pipeline, HTML ingestion, and SQLite persistence |
| web/*.html, *.css, *.js, *.svg | Browser interface, runtime styles, and required assets |
| tests/*.py and tests/*.cjs | Agent, validation, API, persistence, HTML, and renderer tests |
| scripts/generate_dataset.py | Recreate the JSON, ZIP, CSV tables, schema, and dataset notes |
| run.bat | Windows application start shortcut |
| requirements.txt | Python runtime requirement; the app uses the standard library |
| package.json | Optional npm shortcuts for starting and checking the application |
| README.md and .gitignore | Project documentation and repository inclusion rules |

The policy is intentionally strict. When adding another application file, extension, or
subdirectory, add its corresponding allow rule to .gitignore. Caches, dependency folders,
environment files, private keys, and database files remain excluded inside source folders too.

The local Word reports, presentation, dataset, and analysis results remain available in the
project folder. Ignoring them does not delete them.

## Run the project

Python 3.10 or newer is the only application requirement. No pip installation, Node installation,
database setup, API key, or internet connection is needed to run it.

After cloning or downloading the source, run these commands from the project folder:

    python scripts/generate_dataset.py
    python app.py

The first command recreates the dataset files excluded from Git. The application and tests
need these files, so run it before the first start or test run in a fresh checkout.

Open http://127.0.0.1:8000 in your browser. On Windows, you can also double-click run.bat
after generating the dataset. The first application run imports and analyzes that dataset
automatically. Run the generator again whenever you need to recreate the submission ZIP.

If port 8000 is busy:

    python app.py --port 8001

To stop the server, press Ctrl+C in its terminal. To start an empty, separate workspace:

    python app.py --no-seed --db data/empty-workspace.sqlite3

Existing saved workspaces are preserved. Reports created with an earlier engine are retained
until you use Analyze listings. There is no automatic database deletion or reset.

## Dataset for submission

These generated files stay local and are excluded from GitHub. Recreate them with
python scripts/generate_dataset.py and submit them separately when required.

- JSON: datasets/trustlens_dataset.json
- ZIP: trustlens_dataset.zip
- Listing table: datasets/listings.csv
- Review table: datasets/reviews.csv
- Schema: datasets/schema.json
- Provenance: datasets/README.md

The ZIP contains the JSON, both CSV files, schema, and dataset README. It contains **12 fictional
listings and 1,268 synthetic reviews across 6 categories**. All prices use INR.
The fixed reference date is 13 November 2026; seed 11013 makes generation reproducible.

This is original synthetic classroom data under CC0-1.0. It includes no real personal information,
scraped marketplace records, or real fraud allegations. Scenario labels explain how examples
were designed; the scoring engine does not read those labels. This dataset is not a validated
training set or an accuracy benchmark.

Regenerate the dataset and its ZIP:

    python scripts/generate_dataset.py

Downloading the included sample dataset does not export a user's private imported workspace.

## What works

- Overview with real category counts, trust distribution, review totals, and review priorities.
- Searchable, filterable, sortable listing queue with pagination and URL state.
- JSON imports with nested input validation and atomic persistence.
- An API for extracting a Product record from supplied JSON-LD HTML.
- Weekly UTC review segmentation and verified/unverified/unknown purchase cohorts.
- Exact and near-duplicate review clustering, a sliding 48-hour burst detector, incentive-language
  detection, supplied network-hash clustering, and cross-listing reviewer memory.
- Claim extraction for capacities, materials, certifications, warranty, and returns.
- Illustrative regional claim-screening presets for IN, US, EU, and Global.
- Seller account-age signals, relisting history, supplied takedowns, price drops, and seller swaps.
- Supplied image-fingerprint reuse and brand-metadata comparisons.
- Weighted trust scoring with coverage, risk tiers, and consequential-finding score caps.
- Evidence, claim, review, listing-change, and agent-execution views.
- Reviewer notes/status, audit events, optimistic version conflicts, and retained report history.
- Targeted seller-evidence request drafts, with copy and manual-copy recovery.
- Focused navigation for overview, listing review, and the agent pipeline.
- JSON and readable Markdown report downloads.
- A command-line demonstration that exports reports without running a web server.

## Ten-agent architecture

1. Listing ingestion agent normalizes listing and price metadata.
2. Review segmentation agent organizes UTC weeks and purchase cohorts.
3. Listing compliance agent screens unsupported or consequential claims.
4. Claim extraction agent extracts structured seller statements.
5. Review authenticity agent examines text, timing, and reviewer patterns.
6. Seller behavior agent checks supplied seller history and listing drift.
7. Image signal agent compares supplied fingerprints and brand metadata.
8. Risk aggregation agent combines available evidence and applies score caps.
9. Report agent writes a deterministic, plain-language evidence summary and next actions.
10. Orchestrator agent manages handoffs, concurrent detection, one retry, and partial reports.

Agents 3–7 run concurrently after ingestion. These are focused software agents with explicit
inputs, outputs, and an execution trace. The default intelligence engine is a **rule-based expert
system with statistical NLP**. It does not use a trained fraud model, an LLM, or autonomous
language-model planning.

The application uses three layers: the browser interface, the local Python service, and
SQLite persistence. The service validates imported records before passing them to the pipeline.

    JSON dataset or supplied Product JSON-LD HTML
                       |
                 Input validation
                       |
         Listing ingestion and review segmentation
                       |
       Compliance / Claims / Reviews / Seller / Images
                       |
         Weighted scoring and evidence coverage
                       |
              Plain-language report
                       |
             Human review and local audit

All five detection agents receive the same listing and context. The orchestrator records each
agent's status, attempts, duration, and finding count. A failed analytical agent receives one
retry. If it fails again, the report remains available, identifies the partial analysis, and
excludes that component from the weighted score.

Review segmentation uses Monday-start UTC weeks. The burst detector requires a peak 48-hour
window with at least 12 reviews, at least 25% of the listing's reviews, and at least three times
the remaining-period rate. Text analysis groups normalized exact matches, then uses four-word
shingles to select candidate pairs and token-set Jaccard similarity of at least 0.82 to identify
near matches. Clusters require multiple distinct reviewer IDs. Unknown purchase verification
remains unknown.

Reviewer IDs implicated in duplicate, incentive, or supplied network clusters form local
cross-listing memory. Fingerprint matches and catalog/observed-brand comparisons use supplied
image metadata only. A URL alone does not enable image analysis.

SQLite stores current listing input, earlier input, current reports, bounded report history,
review notes, case status, and audit events. Imports are atomic. Updating a listing preserves
the earlier input, notes, and audit trail, reopens the case, and requires fresh analysis.
Review and analysis saves check the current version to prevent stale overwrites.

## How scoring works

Each component starts at 100. Each finding deducts impact multiplied by heuristic confidence.
Scores are clamped to 0–100.

| Component | Weight |
|---|---:|
| Listing compliance | 25% |
| Review authenticity | 40% |
| Seller behavior | 25% |
| Image metadata | 10% |

The initial weighted score uses only available components and renormalizes their weights.
Unavailable agents do not silently receive a clean score.

Evidence coverage counts available component weights; image metadata receives only 40% of its
weight in coverage because actual pixels are not inspected. Below 50% coverage the risk label
is Insufficient evidence, regardless of the provisional numeric score.

Two transparent caps prevent consequential findings from being averaged away:

- A high-severity finding with confidence at least 0.85 and impact at least 20 caps trust at 74.
- A detected medical claim promising a cure or guaranteed outcome caps trust at 49.

Reports contain the initial weighted score and any cap reason. Otherwise, high risk is below 50,
medium is 50–74, and low is 75–100. The weights, confidence values, caps, and thresholds are
illustrative settings, not calibrated probabilities or validated production policy.

## Demonstrate it to your teacher

1. Open Overview and explain the synthetic dataset and category distribution.
2. Open UltraCharge Pro (TL-1001). Inspect the review burst, repeated text, unsupported claims,
   and specific next actions.
3. Open Reviews to show weekly cohorts and individual review evidence.
4. Open PulseFit (TL-1009), then Listing changes, to show a seller swap and price drop.
5. Open Agent trace to show all ten agents, duration, attempts, and available metrics.
6. Add a reviewer note, choose Needs review, and save. Risk and case status remain separate.
7. Download a JSON or readable report.
8. Use the local datasets/trustlens_dataset.json or trustlens_dataset.zip when a submission requires the sample data.

For a command-line demonstration:

    python analyze.py

This creates reports/trust_reports.json. To analyze another dataset:

    python analyze.py path/to/input.json --output reports/custom-report.json

## API

All API operations are local. JSON request bodies use Content-Type: application/json.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/health | Read readiness and engine version |
| GET | /api/overview | Read dashboard metrics |
| GET | /api/config | Read agents, weights, and screening presets |
| GET | /api/listings | Search/filter/sort/page; q, risk, category, status, sort, page, size |
| GET | /api/listings/ID | Read listing, evidence report, notes, and audit events |
| GET | /api/listings/ID/report | Download a JSON evidence report |
| POST | /api/import | Validate/import a dataset containing a listings array |
| POST | /api/import/html | Import one supplied Product JSON-LD HTML record |
| POST | /api/analyze | Start analysis; optional listing_ids array |
| GET | /api/jobs/ID | Read actual background job progress |
| POST | /api/listings/ID/decision | Save status, notes, and expected numeric version |
| GET | /api/dataset | Download the bundled JSON |
| GET | /api/dataset/zip | Download the bundled ZIP |
| GET | /api/dataset/schema | Download the input schema |

For HTML ingestion, provide html (the complete HTML string), listing_id, region, and a seller
object with id, name, and created_at. The parser accepts exactly one Product JSON-LD record,
including a record within @graph. Price must be available in offers. Missing seller history and
purchase verification are not invented. Recorded image URLs are not fetched or treated as matches.
This endpoint is API-only; the dashboard import form accepts JSON datasets.

Review status is open, needs_review, or reviewed. A stale version returns HTTP 409.
Imports are limited to 16 MB, 50 listings, 5,000 reviews per listing, and 25,000 reviews per import.
The local workspace is capped at 500 listings. Reports retain the latest 30 runs per listing.

## Local folders and excluded files

The following folders are deliberately absent from a source-only GitHub checkout.

| Local path | Contents | How it becomes available |
|---|---|---|
| data/ | SQLite database and its journal files | Created automatically when the app starts |
| datasets/ | Dataset JSON, listing/review CSVs, JSON schema, and provenance README | Run python scripts/generate_dataset.py |
| reports/ | Exported evidence reports, including trust_reports.json | Run python analyze.py or download reports through the app |
| project_documents/ | Four academic Word sections | Retained separately as submission documents |
| presentations/ | Final TrustLens PowerPoint | Retained separately as a presentation deliverable |
| presentation_build/ | Deck authoring source, drafts, previews, and validation records | Local presentation-authoring work only |
| docs/ | Expanded architecture, requirements mapping, verification notes, report content, and document QA | Local development and submission material |
| __pycache__/ and nested caches | Compiled Python bytecode | Recreated by Python and ignored everywhere |

Additional root files excluded from GitHub:

| File | Purpose |
|---|---|
| trustlens_dataset.zip | Generated dataset submission archive, recreated by the dataset generator |
| PS-11-Ecommerce-Product-Trust-Agent.docx | Original supplied problem statement; its internal heading says PS-10 |
| DESIGN.md | Local visual design decisions and design-token source |
| UX-CONTRACT.md | Local interface and interaction contract |
| premium-ui.json | Local UI-audit configuration |
| premium-audit.json | Local static UI-audit findings |

The Word documents are:

1. project_documents/01_Problem_Definition_and_Scope_of_Project.docx
2. project_documents/02_Literature_Review.docx
3. project_documents/03_Conceptual_System_Design.docx
4. project_documents/04_Results_and_Conclusions.docx

The enhanced presentation is presentations/TrustLens_Project_Presentation_Enhanced_Final.pptx.
Its 16 slides cover the problem, scope, literature, architecture, agents, running interface,
scoring, synthetic results, seller-evidence requests, limitations, and conclusions. The original
15-slide presentation remains available separately.

Optional local helpers are also excluded: scripts/create_report_documents.py,
scripts/check_report_documents.py, scripts/render_report_documents.ps1, and
scripts/design_tokens.py. They support artifact or design work and are not dependencies of
the application. Their inputs remain in the corresponding local documentation/build folders.
The committed web/tokens.css already contains the runtime tokens, so a fresh checkout does
not need DESIGN.md or the design helper.

This README contains the application setup, architecture, API, scoring rules, demonstration
steps, verification details, and limitations needed to understand the source independently
of those excluded documents.

Node.js is optional and is used only for JavaScript verification. The application serves
JavaScript directly and has no frontend compilation step.

## Verification

Generate the ignored dataset before running tests in a fresh checkout:

    python scripts/generate_dataset.py
    python -m unittest discover -s tests -v
    python -m compileall -q app.py analyze.py trustlens scripts tests

If Node.js is installed, also run:

    node --check web/app.js

The recorded project verification has 49 passing tests. Without Node.js, the Python suite skips
the interface-renderer test. The checks cover signals, retries, missing evidence, score caps,
input validation, real localhost API requests, background analysis jobs, saved reviews, restart
persistence, version conflicts, report downloads, ZIP integrity, and Product JSON-LD parsing.

The frontend test checks six renderer outputs, untrusted-text escaping, and static command
bindings in Node. Browser checks also confirmed the three-link navigation, overview and
evidence views, and layouts at desktop and 390px widths without page overflow. The seller
request displayed with paragraph breaks and its copy action showed success feedback. The
browser bridge did not expose the copied clipboard payload, so that payload was not verified.
Full keyboard, recovery-state, and runtime accessibility checks remain outstanding.

The local static UI audit reported five action-binding findings because its detector does not
recognize the application's delegated data-action handlers. The handlers exist and the Node
test checks their bindings. This is not a claim that a browser accessibility audit has passed.

### Recorded synthetic results

The saved first-pass demonstration run on 13 November 2026 produced:

| Measure | Recorded value |
|---|---:|
| Listings | 12 |
| Reviews | 1,268 |
| High-risk listings | 4 |
| Medium-risk listings | 3 |
| Low-risk listings | 5 |
| Findings | 45 |
| Mean trust score | 71.92 / 100 |

UltraCharge (TL-1001) received 27 / 100 with 210 reviews in its busiest 48-hour window,
210 reviews in repeated-text clusters, and 18 reviews containing incentive language.
These results demonstrate configured behavior on synthetic examples. They do not measure
real-world detection accuracy. Later analyses can add reviewer-memory findings as local history
accumulates. Regenerate a first-pass local report with python analyze.py.

## Research background

The literature informed the choice to combine text, timing, reviewer relationships, and
explicit agent responsibilities. TrustLens does not reproduce the studies' trained or
probabilistic models and does not inherit their measured performance.

- [Jindal and Liu (2008), Opinion Spam and Analysis](https://www.cs.uic.edu/~liub/FBS/opinion-spam-WSDM-08.pdf)
- [Ott, Choi, Cardie, and Hancock (2011), Finding Deceptive Opinion Spam by Any Stretch of the Imagination](https://aclanthology.org/P11-1032/)
- [Mukherjee, Liu, and Glance (2012), Spotting Fake Reviewer Groups in Consumer Reviews](https://wwwconference.org/wp-content/uploads/2025/01/p191.pdf)
- [Rayana and Akoglu (2015), Collective Opinion Spam Detection Bridging Review Networks and Metadata](https://www.andrew.cmu.edu/user/lakoglu/pubs/15-kdd-collectiveopinionspam.pdf)
- [Li and colleagues (2016), Modeling Review Spam Using Temporal Patterns and Co-bursting Behaviors](https://arxiv.org/abs/1611.06625)
- [Wooldridge and Jennings (1995), Intelligent Agents Theory and Practice](https://www.cs.ox.ac.uk/people/michael.wooldridge/pubs/ker95.pdf)

## GitHub publishing notes

This folder does not yet contain a Git repository. The .gitignore policy takes effect when you
initialize one and add files. It controls tracking, not file storage or deletion.

After initializing your repository, inspect the files before committing:

    git add --dry-run .
    git status --short

Only the included paths listed above should appear. If any file was already committed before
these ignore rules were added, .gitignore does not automatically remove it from Git history or
the index. Review that situation separately before publishing.

## Scope and limitations

This is a local academic demonstration. The server binds to 127.0.0.1, rejects untrusted Host and
Origin headers, escapes untrusted listing content, and uses SQLite parameterized statements.
It has no authentication, team permissions, public hosting configuration, or production hardening.

No live marketplace scraper, order database, reverse-image service, certificate verifier, or
enforcement-history database is connected. Seller history, document references, image fingerprints,
and network hashes are supplied evidence. Image analysis is metadata comparison, not pixel forensics.
External URLs are never fetched by the analysis engine.

Regional rules are illustrative review presets and must not be presented as statements of law or
actual marketplace policy. A supplied certificate reference remains unverified. A high trust score
means configured red flags were absent or limited in available input, not that a product is genuine.
Human review is required. Near-duplicate comparisons are bounded at 40,000 pairs; reaching the cap
is reported, while exact text grouping still covers all reviews.

Seller account age is measured at analysis time, so age-related results can change as time passes.
Synthetic scenario labels and data must not be used to claim a real-world detection accuracy.
