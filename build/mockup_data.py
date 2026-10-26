"""Build the mockup's data from the CDX samples in data/sample/ and
data/pages-monthly.txt. A stand-in for the real pipeline in HANDOFF.md:
translation folding here is a rough first cut, not build/languages.py."""
import json, re, sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "sample"
START, END = "201912", "20230511"

KEYWORDS = re.compile(
    r"(covid|coronavirus|pandemic|vaccin|sars-cov|public-health-emergency|novel-corona|"
    r"(^|-)masks?(-|$)|mask-wearing|(^|-)testing(-|$)|reopen|cares-act|american-rescue|"
    r"paycheck|stimulus|quarantine|social-distanc|ventilator|(^|-)dpa(-|$)|"
    r"defense-production-act|(^|-)ppe(-|$)|personal-protective|long-covid|omicron|"
    r"delta-variant|suspension-of-entry|suspending-entry|immigrants-who-present-risk|"
    r"economic-relief|eviction|student-loan|task-force|opening-up-america|warp-speed|"
    r"hydroxychloroquine)")

LANGS = {
    "sp": "Spanish", "es": "Spanish", "esp": "Spanish", "spanish": "Spanish",
    "zhcn": "Chinese", "chinese": "Chinese", "zh": "Chinese", "zhtw": "Chinese",
    "ko": "Korean", "korean": "Korean", "vi": "Vietnamese", "vietnamese": "Vietnamese",
    "ar": "Arabic", "arabic": "Arabic", "fr": "French", "french": "French",
    "ht": "Haitian Creole", "haitian": "Haitian Creole", "creole": "Haitian Creole",
    "ru": "Russian", "russian": "Russian", "tl": "Tagalog", "tagalog": "Tagalog",
    "pt": "Portuguese", "portuguese": "Portuguese", "so": "Somali", "somali": "Somali",
    "am": "Amharic", "amharic": "Amharic", "burmese": "Burmese", "dari": "Dari",
    "faaf": "Dari", "pashto": "Pashto", "farsi": "Farsi", "fa": "Farsi",
    "nepali": "Nepali", "ne": "Nepali", "swahili": "Swahili", "sw": "Swahili",
    "tigrinya": "Tigrinya", "tigryna": "Tigrinya", "tigrynia": "Tigrinya",
    "kinyarwanda": "Kinyarwanda", "kinyardwanda": "Kinyarwanda", "hmong": "Hmong",
    "japanese": "Japanese", "ja": "Japanese", "karen": "Karen", "khmer": "Khmer",
    "lao": "Lao", "marshallese": "Marshallese", "chuukese": "Chuukese",
    "hindi": "Hindi", "hi": "Hindi", "urdu": "Urdu", "punjabi": "Punjabi",
    "bengali": "Bengali", "polish": "Polish", "pl": "Polish", "italian": "Italian",
    "german": "German", "ukrainian": "Ukrainian", "uk": "Ukrainian",
    "gujarati": "Gujarati", "thai": "Thai", "tongan": "Tongan", "samoan": "Samoan",
    "navajo": "Navajo", "yupik": "Yupik", "kirundi": "Kirundi", "oromo": "Oromo",
    "uzbek": "Uzbek", "dzongkha": "Dzongkha", "rohingya": "Rohingya",
    "malay": "Malay", "mam": "Mam", "greek": "Greek", "hebrew": "Hebrew",
    "turkish": "Turkish", "chamorro": "Chamorro", "ilocano": "Ilocano",
}
NOISE = {"hr", "p", "508", "print", "plain", "final", "c", "fs", "pdf"}
# Two-to-four letter codes count only near the end; a long name counts anywhere
# but first. "to" and "my" are ISO codes too, so they are not in LANGS.
SHORT = {k for k in LANGS if len(k) <= 4 and k not in {"faaf", "zhcn", "zhtw"}}


def rows(name):
    for line in (SAMPLE / name).read_text().splitlines():
        if line.strip():
            yield line.split(" ")


def month(ts):
    return f"{ts[:4]}-{ts[4:6]}"


def title_from(slug):
    s = unquote(slug)
    s = re.sub(r"\.(pdf|html?|aspx)$", "", s, flags=re.I)
    s = re.sub(r"[-_]+", " ", s).strip()
    return s[:1].upper() + s[1:] if s else slug


def wb(ts, url):
    return f"https://web.archive.org/web/{ts}/{url}"


def cdc():
    by_file = {}
    for url, ts, digest, length in rows("cdc-downloads.txt"):
        if ts > END + "999999":
            continue
        clean = url.split("?")[0]
        if clean not in by_file or ts < by_file[clean][0]:
            by_file[clean] = (ts, url)
    groups = defaultdict(list)
    for clean, (ts, url) in by_file.items():
        d, f = clean.rsplit("/", 1)
        stem = re.sub(r"\.pdf$", "", unquote(f), flags=re.I)
        toks = [t for t in re.split(r"[-_ .]+", stem) if t]
        lang, keep = None, []
        for i, t in enumerate(toks):
            tl = t.lower()
            near_end = i >= len(toks) - 3
            if i > 0 and tl in LANGS and (tl not in SHORT or near_end):
                lang = LANGS[tl]
            elif i > 0 and tl.endswith("korean"):
                lang = "Korean"
            elif tl in NOISE:
                continue
            else:
                keep.append(tl)
        groups[(d, " ".join(keep))].append((lang, ts, url, stem))
    docs = []
    for (d, key), members in groups.items():
        members.sort(key=lambda m: (m[0] is not None, m[1]))
        lang0, ts, url, stem = members[0]
        langs = sorted({m[0] for m in members if m[0]})
        first = min(m[1] for m in members)
        docs.append({
            "agency": "CDC", "type": "PDF", "title": title_from(stem),
            "month": month(first), "url": wb(ts, url),
            "langs": langs if lang0 is None else langs,
            "src": url,
        })
    return docs, len(by_file)


def plain_pdfs(name, agency):
    out, seen = [], set()
    for url, ts, mime, status in rows(name):
        if status != "200" or "pdf" not in mime or ts > END + "999999":
            continue
        clean = url.split("?")[0]
        if clean in seen:
            continue
        seen.add(clean)
        out.append({"agency": agency, "type": "PDF",
                    "title": title_from(clean.rsplit("/", 1)[1]),
                    "month": month(ts), "url": wb(ts, url), "langs": [], "src": url})
    return out


ACTION_TYPES = [("executive-order", "Executive order"), ("proclamation", "Proclamation"),
                ("memorandum", "Memorandum"), ("notice", "Notice"), ("letter", "Letter")]


def biden():
    out = []
    for url, ts in rows("biden-actions.txt"):
        m = re.search(r"/presidential-actions/(\d{4})/(\d{2})/(\d{2})/([^/?]+)", url)
        if not m:
            continue
        y, mo, d, slug = m.groups()
        if f"{y}{mo}{d}" > END or not KEYWORDS.search(slug):
            continue
        kind = next((v for k, v in ACTION_TYPES if k in slug), "Presidential action")
        live = f"https://www.whitehouse.gov/briefing-room/presidential-actions/{y}/{mo}/{d}/{slug}/"
        out.append({"agency": "White House", "type": kind, "title": title_from(slug),
                    "month": f"{y}-{mo}", "day": f"{y}-{mo}-{d}",
                    "url": f"https://web.archive.org/web/{y}{mo}{d}235959/{live}",
                    "langs": [], "src": live})
    # one record per slug
    uniq = {d["src"]: d for d in out}
    return list(uniq.values())


def pages():
    out, lines = [], (ROOT / "data" / "pages-monthly.txt").read_text().splitlines()
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


def main():
    cdc_docs, cdc_files = cdc()
    docs = cdc_docs + plain_pdfs("ed.txt", "ED") + plain_pdfs("nih.txt", "NIH") + biden()
    docs = [d for d in docs if "2019-12" <= d["month"] <= "2023-05"]
    docs.sort(key=lambda d: (d["month"], d["agency"], d["title"]))
    data = {"docs": docs, "pages": pages(),
            "stats": {"cdc_files": cdc_files, "cdc_docs": len(cdc_docs),
                      "cdc_translated": sum(1 for d in cdc_docs if d["langs"])}}
    out = ROOT / "mockup" / "data.js"
    out.parent.mkdir(exist_ok=True)
    out.write_text("window.MOCK=" + json.dumps(data, separators=(",", ":")) + ";\n")
    by = defaultdict(int)
    for d in docs:
        by[d["agency"]] += 1
    print(dict(by), data["stats"], f"{out.stat().st_size/1024:.0f} KB", file=sys.stderr)


if __name__ == "__main__":
    main()
