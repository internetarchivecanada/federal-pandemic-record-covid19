#!/usr/bin/env python3
"""Build the explorer's data, corpus.js, from the pipeline's outputs.

Reads data/documents.jsonl (languages.py), data/dates.jsonl (dates.py) and
data/pages-monthly.txt, and writes corpus.js beside index.html at the
repository root, where GitHub Pages serves it.

What goes in follows the corpus rule: every document opens as a document.
  - Agency file folders: PDFs and Office files only. Images, stylesheets,
    scripts and XML in the same folders are left out.
  - White House: the issuance pages themselves. Trump items take the first
    capture of their www.whitehouse.gov address from dates.py, and only those
    inside the period; Biden items carry their day in the URL.
  - PHE: only the COVID declarations. The same folder holds every emergency
    since 2010 (hurricanes, opioids, Zika).

Each Wayback link points at the capture the date came from, so the link
replays the document as it stood when it was first seen.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import harvest  # noqa: E402

FILE_TYPES = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
    "application/msword": "Word",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
    "application/vnd.ms-excel": "Excel",
}
ISSUANCE_SOURCES = {"wht-actions", "wht-briefings", "whb-actions"}
PHE_COVID = re.compile(r"/pages/[^/]*(covid|covdi|ncov)[^/]*\.aspx$")

ACTION_TYPES = [("executive-order", "Executive order"), ("proclamation", "Proclamation"),
                ("memorandum", "Memorandum"), ("determination", "Determination"),
                ("notice", "Notice"), ("letter", "Letter"), ("message", "Message")]
BRIEFING_TYPES = [("remarks", "Remarks"), ("statement", "Statement"), ("press-briefing", "Press briefing"),
                  ("briefing", "Press briefing"), ("readout", "Readout"), ("fact-sheet", "Fact sheet"),
                  ("letter", "Letter"), ("message", "Message"), ("proclamation", "Proclamation"),
                  ("executive-order", "Executive order"), ("memorandum", "Memorandum")]


def title_from(key: str) -> str:
    slug = urllib.parse.unquote(key.rstrip("/").rsplit("/", 1)[-1])
    slug = re.sub(r"\.(pdf|docx?|xlsx?|html?|aspx)$", "", slug, flags=re.I)
    words = re.sub(r"[-_]+", " ", slug).strip()
    return words[:1].upper() + words[1:] if words else key


MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
SLUG_DATE = re.compile(r"(\d{1,2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(\d{2,4})")


def phe_title(slug: str) -> str:
    """phe.gov names each renewal by its date: covid19-21apr2020, covdi-15oct21."""
    m = SLUG_DATE.search(slug.lower())
    if not m:
        return "Determination that a public health emergency exists: 2019 novel coronavirus"
    day, mon, year = int(m.group(1)), m.group(2), m.group(3)
    year = int(year) + (2000 if len(year) == 2 else 0)
    return f"Renewal of the COVID-19 public health emergency, {day} {mon.title()} {year}"


def kind(slug: str, table: list[tuple[str, str]], default: str) -> str:
    return next((label for word, label in table if word in slug), default)


def wayback(ts: str, url: str) -> str:
    return f"https://web.archive.org/web/{ts}/{url}"


def month(ts: str) -> str:
    return f"{ts[:4]}-{ts[4:6]}"


def in_period(ts: str) -> bool:
    return harvest.FIRST_DAY <= ts[:8] <= harvest.LAST_DAY


def entry(d: dict, dates: dict[str, dict]) -> dict | None:
    """One document as the page shows it, or None if it is not in the corpus."""
    source, slug = d["source"], d["key"].rstrip("/").rsplit("/", 1)[-1]
    base = {"agency": d["agency"], "title": title_from(d["key"]), "langs": d["languages"]}
    if source == "wht-actions" or source == "wht-briefings":
        found = dates.get(d["key"], {})
        if found.get("status") != "found" or not found.get("in_period"):
            return None
        table = ACTION_TYPES if source == "wht-actions" else BRIEFING_TYPES
        default = "Presidential action" if source == "wht-actions" else "Briefing room"
        return base | {"type": kind(slug, table, default), "month": month(found["first_ts"]),
                       "url": wayback(found["first_ts"], found["live_url"])}
    if source == "whb-actions":
        day = d["url_day"]
        if not day or not in_period(day):
            return None
        return base | {"type": kind(slug, ACTION_TYPES, "Presidential action"), "month": month(day),
                       "day": f"{day[:4]}-{day[4:6]}-{day[6:]}", "url": wayback(d["timestamp"], d["original"])}
    if source == "phe":
        if not PHE_COVID.search(d["key"]) or not in_period(d["timestamp"]):
            return None
        return base | {"title": phe_title(slug), "type": "PHE declaration", "month": month(d["timestamp"]),
                       "url": wayback(d["timestamp"], d["original"])}
    if d["mimetype"] not in FILE_TYPES or not in_period(d["first_ts"]):
        return None
    return base | {"type": FILE_TYPES[d["mimetype"]], "month": month(d["first_ts"]),
                   "url": wayback(d["timestamp"], d["original"])}


def pages(path: Path) -> list[dict]:
    out, lines = [], path.read_text().splitlines()
    for head, body in zip(lines[0::2], lines[1::2]):
        key, url, versions, first, last = head.lstrip("#").split("|")
        months = []
        for cell in body.split():
            ym, ts, v, kb = (cell.split(":") + [""])[:4]
            months.append({"m": f"{ym[:4]}-{ym[4:]}", "ts": ym + ts, "v": int(v),
                           "kb": float(kb) if kb else None})
        peak = max((x["kb"] for x in months if x["kb"]), default=0)
        for x in months:
            x["ph"] = bool(x["kb"] is not None and peak and x["kb"] < 0.15 * peak)
        out.append({"key": key, "url": url, "versions": int(versions),
                    "first": first, "last": last, "peak": peak, "months": months})
    return out


def main() -> None:
    documents = [json.loads(line) for line in (ROOT / "data" / "documents.jsonl").read_text().splitlines()]
    dates = {json.loads(line)["key"]: json.loads(line)
             for line in (ROOT / "data" / "dates.jsonl").read_text().splitlines()}

    docs, left_out = [], Counter()
    for d in documents:
        e = entry(d, dates)
        if e:
            docs.append(e)
        else:
            left_out[d["source"]] += 1
    docs.sort(key=lambda d: (d["month"], d["agency"], d["title"]))

    fetched = max(json.loads(p.read_text())["fetched"] for p in (ROOT / "data" / "cdx-cache").glob("*.json"))
    harvested = time.strptime(fetched[:10], "%Y-%m-%d")
    cdc = [d for d in documents if d["source"] == "cdc-dl"]
    stats = {"built": time.strftime("%-d %B %Y"), "harvested": time.strftime("%-d %B %Y", harvested),
             "cdc_files": sum(len(d["members"]) for d in cdc), "cdc_docs": len(cdc),
             "by_agency": Counter(d["agency"] for d in docs)}
    data = {"docs": docs, "pages": pages(ROOT / "data" / "pages-monthly.txt"), "stats": stats}
    out = ROOT / "corpus.js"
    out.write_text("window.CORPUS=" + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n",
                   encoding="utf-8")

    for agency, n in stats["by_agency"].most_common():
        print(f"  {agency:<22} {n:>6,}", file=sys.stderr)
    print(f"  {'left out':<22} " + ", ".join(f"{s} {n}" for s, n in left_out.most_common()), file=sys.stderr)
    print(f"wrote {len(docs):,} documents to {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KB)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
