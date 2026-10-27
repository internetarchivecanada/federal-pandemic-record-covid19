#!/usr/bin/env python3
"""Date the Trump White House items by their first capture on www.whitehouse.gov.

The harvest finds these on trumpwhitehouse.archives.gov, whose captures begin
on 20 January 2021, when the site was moved there. That date says nothing about
when an item was issued. The same path on www.whitehouse.gov was captured while
it was live, and an exact-URL query is cheap there even though any prefix query
on that host answers 503 (measured in the Cowork survey, 22-25 Oct 2026).

The first capture with status 200 is an upper bound on the issue date: the item
existed by then. Shown as "by March 2020", or as a day only where the URL or
the document states one. Checked on two known items, 26 Oct 2026: the national
emergency proclamation first appears on 13 Mar 2020 and "15 Days to Slow the
Spread" on 16 Mar 2020, the days they were issued.

Three outcomes per item, kept apart because they mean different things:
  found     a first capture; it may fall before the period, which is how the
            2019 influenza-vaccine order drops out
  none      CDX answered empty twice, a pause apart. One empty answer is not
            enough: on 26 Oct 2026 CDX answered empty for the Paycheck
            Protection Program remarks, then gave a 29 Apr 2020 capture to
            the same query three times out of three
  error     the request failed; recorded and retried on the next run

Lookups are cached in data/dates-cache.jsonl, one line per attempt, last line
wins, so a run can stop at any point and resume.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import threading
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import harvest

LIVE_HOST = "www.whitehouse.gov"
MIRROR_HOST = "trumpwhitehouse.archives.gov"
SOURCES = {"wht-actions", "wht-briefings"}


def live_url(mirror_url: str) -> str:
    """The same path on the live host, scheme https, query dropped."""
    parts = urllib.parse.urlsplit(mirror_url)
    if parts.netloc.lower() not in (MIRROR_HOST, "www." + MIRROR_HOST):
        raise ValueError(f"not a {MIRROR_HOST} URL: {mirror_url}")
    path = parts.path if parts.path.endswith("/") else parts.path + "/"
    return f"https://{LIVE_HOST}{path}"


def first_capture(url: str, pause: float = 5.0) -> dict:
    """Ask twice before believing an empty answer."""
    result = ask_first(url)
    if result["status"] == "none":
        time.sleep(pause)
        result = ask_first(url)
    return result | {"asked": 2} if result["status"] == "none" else result


def ask_first(url: str) -> dict:
    params = [("url", url), ("limit", "1"), ("filter", "statuscode:200"),
              ("fl", "timestamp,original,digest")]
    body = harvest.fetch(f"{harvest.CDX}?{urllib.parse.urlencode(params)}", timeout=120)
    return parse_first(body)


def parse_first(body: str) -> dict:
    for line in body.splitlines():
        parts = line.split(" ")
        if len(parts) == 3:
            ts, original, digest = parts
            return {"status": "found", "first_ts": ts, "first_url": original, "digest": digest}
    return {"status": "none"}


def in_period(ts: str) -> bool:
    return harvest.FIRST_DAY <= ts[:8] <= harvest.LAST_DAY


def settled(entry: dict) -> bool:
    """Found, or empty twice. A single empty answer from before the second ask is re-asked."""
    return entry.get("status") == "found" or (entry.get("status") == "none" and entry.get("asked") == 2)


def read_cache(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # a line cut off by a kill is simply not an entry
            out[rec["key"]] = rec
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--harvest", type=Path, default=root / "data" / "harvest.jsonl")
    ap.add_argument("--cache", type=Path, default=root / "data" / "dates-cache.jsonl")
    ap.add_argument("--out", type=Path, default=root / "data" / "dates.jsonl")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--export-only", action="store_true")
    args = ap.parse_args()

    items = [json.loads(line) for line in args.harvest.read_text(encoding="utf-8").splitlines()]
    items = [r for r in items if r["source"] in SOURCES]
    cache = read_cache(args.cache)
    todo = [] if args.export_only else [
        r for r in items if not settled(cache.get(r["key"], {}))]
    print(f"{len(items)} items, {len(todo)} to look up", file=sys.stderr)

    lock = threading.Lock()

    def look(rec: dict) -> dict:
        url = live_url(rec["original"])
        try:
            result = first_capture(url)
        except Exception as exc:  # noqa: BLE001
            result = {"status": "error", "error": str(exc)[:120]}
        entry = {"key": rec["key"], "live_url": url, **result,
                 "checked": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with lock, args.cache.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(entry) + "\n")
        time.sleep(args.pause)
        return entry

    started = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, entry in enumerate(pool.map(look, todo), 1):
            cache[entry["key"]] = entry
            if n % 25 == 0 or entry["status"] == "error":
                print(f"  [{n}/{len(todo)}] {entry['status']:<6} {entry['key'][-60:]}  "
                      f"{(time.time() - started) / 60:.1f}m", file=sys.stderr, flush=True)

    counts, by_month = Counter(), Counter()
    with args.out.open("w", encoding="utf-8") as sink:
        for rec in items:
            entry = cache.get(rec["key"], {"status": "error", "error": "never looked up"})
            row = {"key": rec["key"], "source": rec["source"], "status": entry["status"],
                   "live_url": entry.get("live_url") or live_url(rec["original"])}
            if entry["status"] == "found":
                row |= {"first_ts": entry["first_ts"], "in_period": in_period(entry["first_ts"])}
                counts["found, in period" if row["in_period"] else "found, outside period"] += 1
                if row["in_period"]:
                    by_month[entry["first_ts"][:6]] += 1
            else:
                counts[entry["status"]] += 1
            sink.write(json.dumps(row) + "\n")

    print("\n" + "\n".join(f"  {k:<24} {v:>4}" for k, v in sorted(counts.items())), file=sys.stderr)
    print("  in period, by month: " + " ".join(f"{m[:4]}-{m[4:]}:{n}" for m, n in sorted(by_month.items())),
          file=sys.stderr)
    print(f"wrote {len(items)} rows to {args.out.relative_to(root)}", file=sys.stderr)
    if counts["error"]:
        print(f"{counts['error']} lookups failed; re-run to retry only those", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
