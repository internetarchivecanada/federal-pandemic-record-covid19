#!/usr/bin/env python3
"""Ask Wayback's CDX index what each federal source published, per build/sources.tsv.

Modelled on Letters from Congress's harvest.py, and for the same reasons:

**The cache holds raw rows.** Everything CDX returns for a source is cached
verbatim in data/cdx-cache/, and cleaning runs on the way out. Querying is
minutes to hours; re-filtering is seconds, so a newly found kind of junk costs
an --export-only run instead of another pass at the server.

**A failure is recorded as a failure, never as a number.** A failed request and
an empty folder look the same in a spreadsheet. A source that errors is cached
with its error and retried on the next run; a source silently short stays wrong.
Hitting the row cap is a failure too: the resume key's presence says so.

**Narrow prefixes, no regex on big folders.** Measured in the Cowork survey,
22-25 Oct 2026: a domain-wide or regex-filtered query on cdc.gov or a large
/sites/default/files/ folder answers 503 or 504 after about a minute, and any
prefix query on www.whitehouse.gov answers 503 in five seconds, every time.
Keyword selection therefore runs here, locally, on the last path segment.
Large folders use mode `paged`, one cached file per CDX index page, so a run
of many hours can stop and resume. Expensive pages fail first, so a partial
paged run understates.

**https only.** Letters from Congress found the http endpoint answering
"Temporarily Offline" 503s that https did not.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CDX = "https://web.archive.org/cdx/search/cdx"
UA = {"User-Agent": "ia-federal-pandemic-record/0.1 "
                    "(Internet Archive; collections research)"}
FIELDS = ["original", "timestamp", "mimetype", "statuscode", "digest", "length"]

# The period: the first federal notices in December 2019 to the end of the
# Public Health Emergency. CDX takes months; URL dates are checked to the day.
FROM, TO = "201912", "202305"
FIRST_DAY, LAST_DAY = "20191201", "20230511"

TIMEOUT = 240
RETRIES = 3
ROW_CAP = 150_000
CACHE_METHOD = "v1"
DEFAULT_STATUSES = {"harvested", "partial", "retry"}

# Tested in the Cowork survey. Word boundaries matter: without them "ppe"
# matched inside "copper". Slugs both over- and under-match, so the White House
# lists still need a read by hand.
KEYWORDS = re.compile(
    r"(covid|coronavirus|pandemic|vaccin|sars-cov|public-health-emergency|novel-corona|"
    r"(^|-)masks?(-|$)|mask-wearing|(^|-)testing(-|$)|reopen|cares-act|american-rescue|"
    r"paycheck|stimulus|quarantine|social-distanc|ventilator|(^|-)dpa(-|$)|"
    r"defense-production-act|(^|-)ppe(-|$)|personal-protective|long-covid|omicron|"
    r"delta-variant|suspension-of-entry|suspending-entry|immigrants-who-present-risk|"
    r"economic-relief|eviction|student-loan|task-force|opening-up-america|warp-speed|"
    r"hydroxychloroquine)")

URL_DATE = re.compile(r"/(20\d\d)/(\d\d)/(\d\d)/")


# ---------------------------------------------------------------- sources

def load_sources(path: Path) -> list[dict]:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    sources = list(csv.DictReader(lines, delimiter="\t"))
    seen = set()
    for s in sources:
        if s["code"] in seen:
            raise ValueError(f"duplicate source code {s['code']!r} in {path.name}")
        seen.add(s["code"])
        if s["mode"] not in ("prefix", "paged"):
            raise ValueError(f"{s['code']}: unknown mode {s['mode']!r}")
        if s["select"] not in ("all", "keywords"):
            raise ValueError(f"{s['code']}: unknown select {s['select']!r}")
    return sources


# ---------------------------------------------------------------- network

def fetch(url: str, *, timeout: int = TIMEOUT) -> str:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            last = exc
            # 429 and 5xx are worth waiting out; other 4xx are not.
            if exc.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(8 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(6 * (attempt + 1))
    raise RuntimeError(f"{type(last).__name__}: {str(last)[:100]}")


def query(source: dict, **extra) -> str:
    params = [("url", source["prefix"]), ("matchType", "prefix"),
              ("collapse", "urlkey"), ("fl", ",".join(FIELDS))]
    if source["dated"] == "yes":
        params += [("from", FROM), ("to", TO)]
    params += [("filter", f) for f in source["filters"].split(";") if f]
    params += list(extra.items())
    return f"{CDX}?{urllib.parse.urlencode(params)}"


def parse_rows(body: str) -> list[dict]:
    """CDX text to rows. Raises if the body ends in a resume key.

    With showResumeKey, a response cut short by the limit ends with a blank
    line and a lone token. Anything else that is not a full row is ignored.
    """
    rows, lines = [], body.splitlines()
    for i, line in enumerate(lines):
        parts = line.split(" ")
        if len(parts) == len(FIELDS):
            rows.append(dict(zip(FIELDS, parts)))
        elif line.strip() and i >= len(lines) - 2:
            raise RuntimeError(f"hit the {ROW_CAP:,}-row cap; this source needs mode paged")
    return rows


# ---------------------------------------------------------------- cache

def write_cache(path: Path, payload: dict) -> None:
    """Atomic: a run killed mid-write leaves the old entry or none, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(f".tmp{os.getpid()}")
    staged.write_text(json.dumps(payload), encoding="utf-8")
    staged.replace(path)


def read_cache(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - missing or corrupt is simply not an entry
        return None


def is_done(entry: dict | None) -> bool:
    return bool(entry) and "error" not in entry and entry.get("method") == CACHE_METHOD


# ---------------------------------------------------------------- harvest

def harvest_prefix(source: dict, cache: Path) -> dict:
    path = cache / f"{source['code']}.json"
    entry = read_cache(path)
    if is_done(entry):
        return entry
    started = time.time()
    try:
        rows = parse_rows(fetch(query(source, limit=ROW_CAP, showResumeKey="true")))
        entry = {"code": source["code"], "method": CACHE_METHOD, "rows": rows,
                 "seconds": round(time.time() - started, 1),
                 "fetched": time.strftime("%Y-%m-%dT%H:%M:%S")}
    except Exception as exc:  # noqa: BLE001
        entry = {"code": source["code"], "error": str(exc)[:160],
                 "fetched": time.strftime("%Y-%m-%dT%H:%M:%S")}
    write_cache(path, entry)
    return entry


def harvest_paged(source: dict, cache: Path, pause: float) -> dict:
    """Walk CDX index pages, one cached file per page.

    showNumPages is asked without fl (with one it answers "- - - - -") and
    ignores filters, so it counts pages of the whole prefix; the filters still
    apply to each page. A page that fails is recorded and retried next run,
    and the source reports failed until every page is in.
    """
    folder = cache / source["code"]
    meta_path = folder / "_pages.json"
    meta = read_cache(meta_path)
    if not meta:
        count_params = [("url", source["prefix"]), ("matchType", "prefix"),
                        ("showNumPages", "true")]
        try:
            text = fetch(f"{CDX}?{urllib.parse.urlencode(count_params)}", timeout=120).strip()
            meta = {"pages": int(text)}
        except Exception as exc:  # noqa: BLE001
            return {"code": source["code"], "error": f"showNumPages: {str(exc)[:120]}"}
        write_cache(meta_path, meta)
    failed = 0
    for page in range(meta["pages"]):
        path = folder / f"page-{page:05d}.json"
        if is_done(read_cache(path)):
            continue
        try:
            rows = parse_rows(fetch(query(source, page=page)))
            write_cache(path, {"method": CACHE_METHOD, "rows": rows})
        except Exception as exc:  # noqa: BLE001
            failed += 1
            write_cache(path, {"error": str(exc)[:160]})
        if pause:
            time.sleep(pause)
    return load_paged(source, cache) | ({"error": f"{failed} of {meta['pages']} pages failed"}
                                        if failed else {})


def load_paged(source: dict, cache: Path) -> dict:
    folder = cache / source["code"]
    meta = read_cache(folder / "_pages.json")
    if not meta:
        return {"code": source["code"], "error": "never started"}
    rows, missing = [], 0
    for page in range(meta["pages"]):
        entry = read_cache(folder / f"page-{page:05d}.json")
        if is_done(entry):
            rows += entry["rows"]
        else:
            missing += 1
    out = {"code": source["code"], "method": CACHE_METHOD, "rows": rows,
           "pages": meta["pages"]}
    if missing:
        out["error"] = f"{missing} of {meta['pages']} pages not in"
    return out


def load(source: dict, cache: Path) -> dict | None:
    if source["mode"] == "paged":
        return load_paged(source, cache) if (cache / source["code"]).exists() else None
    return read_cache(cache / f"{source['code']}.json")


# ---------------------------------------------------------------- cleaning

def slug(url: str) -> str:
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return urllib.parse.unquote(path.rsplit("/", 1)[-1]).lower()


def url_day(url: str) -> str | None:
    m = URL_DATE.search(url)
    return "".join(m.groups()) if m else None


def canonical(url: str) -> str:
    """One key per file: scheme, www, port, query string and case do not count."""
    key = url.split("#", 1)[0].split("?", 1)[0]
    key = re.sub(r"^https?://", "", key)
    key = re.sub(r"^www\.", "", key)
    key = re.sub(r":80(/|$)", r"\1", key)
    return urllib.parse.unquote(key).rstrip("/").lower()


def clean(source: dict, rows: list[dict]) -> list[dict]:
    """Raw rows to one record per file, earliest capture kept.

    A URL that carries a date outside the period is dropped; that is how a 2019
    influenza-vaccine order falls out of the keyword match. The prefix's own
    index page is dropped too: it is a listing, not a document.
    """
    base = canonical("https://" + source["prefix"])
    seen: dict[str, dict] = {}
    for row in rows:
        key = canonical(row["original"])
        if key == base or not key.startswith(base.rstrip("/")):
            continue
        if source["select"] == "keywords" and not KEYWORDS.search(slug(row["original"])):
            continue
        day = url_day(row["original"])
        if day and not FIRST_DAY <= day <= LAST_DAY:
            continue
        if key not in seen or row["timestamp"] < seen[key]["timestamp"]:
            seen[key] = row
    return [{"source": source["code"], "agency": source["agency"], "key": k,
             "url_day": url_day(r["original"]), **r} for k, r in sorted(seen.items())]


# ---------------------------------------------------------------- main

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sources", type=Path, default=root / "build" / "sources.tsv")
    ap.add_argument("--cache", type=Path, default=root / "data" / "cdx-cache")
    ap.add_argument("--out", type=Path, default=root / "data" / "harvest.jsonl")
    ap.add_argument("--source", action="append", default=[],
                    help="run only this code (repeatable); needed for queued, blocked and paged sources")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--pause", type=float, default=1.5, help="seconds between paged requests")
    ap.add_argument("--export-only", action="store_true",
                    help="re-clean the cache without touching the network")
    args = ap.parse_args()

    sources = load_sources(args.sources)
    known = {s["code"] for s in sources}
    unknown = set(args.source) - known
    if unknown:
        sys.exit(f"unknown source code(s): {', '.join(sorted(unknown))}")
    chosen = ([s for s in sources if s["code"] in args.source] if args.source else
              [s for s in sources if s["status"] in DEFAULT_STATUSES and s["mode"] == "prefix"])

    todo = [] if args.export_only else [
        s for s in chosen if s["mode"] == "paged" or not is_done(load(s, args.cache))]
    print(f"{len(chosen)} sources chosen, {len(todo)} to query "
          f"({len(chosen) - len(todo)} cached)", file=sys.stderr)

    def run(s):
        return harvest_paged(s, args.cache, args.pause) if s["mode"] == "paged" \
            else harvest_prefix(s, args.cache)

    failed = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run, s): s for s in todo}
        for fut in cf.as_completed(futures):
            s, entry = futures[fut], fut.result()
            if "error" in entry:
                failed += 1
                print(f"  {s['code']:<18} FAILED  {entry['error']}", file=sys.stderr, flush=True)
            else:
                print(f"  {s['code']:<18} {len(entry['rows']):>7,} rows  "
                      f"{entry.get('seconds', '')}s", file=sys.stderr, flush=True)

    # Export everything cached, not only what was chosen, so a one-source run
    # never rewrites the dataset as that one source.
    total = 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    print(f"\n{'source':<18} {'raw':>8} {'kept':>7}  handoff", file=sys.stderr)
    with args.out.open("w", encoding="utf-8") as sink:
        for s in sources:
            entry = load(s, args.cache)
            if not entry:
                continue
            if "error" in entry and not entry.get("rows"):
                print(f"{s['code']:<18} {'FAILED':>8}          {entry['error'][:60]}", file=sys.stderr)
                continue
            kept = clean(s, entry["rows"])
            flag = "  PARTIAL: " + entry["error"] if "error" in entry else ""
            print(f"{s['code']:<18} {len(entry['rows']):>8,} {len(kept):>7,}  {s['handoff']}{flag}",
                  file=sys.stderr)
            for rec in kept:
                sink.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += len(kept)
    print(f"\nwrote {total:,} records to {args.out.relative_to(root)}", file=sys.stderr)
    if failed:
        print(f"{failed} source(s) failed; re-run to retry only those", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
