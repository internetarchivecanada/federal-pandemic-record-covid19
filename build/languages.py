#!/usr/bin/env python3
"""Fold CDC's translations into one document each, listing the languages.

CDC names a translation by suffix, spelled many ways: `-sp`, `-es`, `_ESP`,
`-spanish`, `_ZHCN_HR`, `_KO_HR_Korean`, `_FAAF_Dari`, `-tigrynia`,
`-kinyardwanda`, `TempLog_IItalian`, `-cape-verdean-creole`, `_eng-fr_4-9-20`.
The method, from the Cowork survey and checked against every cdc-dl filename
on 26 Oct 2026:

  1. Split the filename on `[-_ .]`.
  2. Find the **tag run**: walk back from the end over tokens that are
     languages, regional qualifiers, noise or digits, and stop at the first
     word that is none of these. `..._print_am_hr_amharic` has the run
     `am hr amharic`.
  3. A two-to-four-letter code (`am`, `my`, `ko`, `ptbr`) counts as a language
     only inside the run. That is what stops `how_do_i_set_up_my_classroom`
     being Burmese: `classroom` ends the run before `my` is reached. A language
     name of five letters or more (`spanish`, `korean`) counts anywhere but
     first, as in `templog_portuguese-314925-e_covid-19_ptbr-p`.
  4. Drop the languages, the run's qualifiers and the noise; what is left,
     with the directory, is the document's identity.
  5. Keep the English or untagged file as the representative and list the
     other languages.

`to` is an ISO code (Tongan) and appears 66 times, never as a language, so it
is not one here. Two tokens are left unread on purpose, each in one file:
`_ch` (probably Chinese, beside `_ko` and `_vi` siblings) and `-fi-` before
`cape-verdean-creole`. An unread token costs a missed fold, not a false one. Labels are the base language only: Simplified and Traditional
Chinese both read "Chinese", Brazilian and European Portuguese both
"Portuguese". Each member keeps its own key, so the variant is recoverable.

Folding prefers to under-merge: `324228-a_fs-vaxpromo-en-es-print-only` stays
a document of its own, because `only` ends the run before `en-es` is reached.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

# Only CDC names translations this way. White House slugs such as
# "...-republic-of-korea" would be misread as Korean by step 3.
FOLD_SOURCES = {"cdc-dl"}

ENGLISH = "English"

# Two-to-four-letter codes: languages only inside the tag run.
CODES = {
    "am": "Amharic", "ar": "Arabic", "en": ENGLISH, "eng": ENGLISH,
    "es": "Spanish", "esp": "Spanish", "sp": "Spanish", "spa": "Spanish", "span": "Spanish",
    "ck": "Chuukese", "fa": "Farsi", "faaf": "Dari", "fr": "French", "hi": "Hindi",
    "hm": "Hmong", "ht": "Haitian Creole",
    "ja": "Japanese", "ke": "Karen", "km": "Khmer", "ko": "Korean", "lao": "Lao",
    "mand": "Chinese", "mh": "Marshallese", "ms": "Malay", "my": "Burmese", "ne": "Nepali",
    "pl": "Polish", "ps": "Pashto",
    "pt": "Portuguese", "ru": "Russian", "rw": "Kinyarwanda", "so": "Somali",
    "sw": "Swahili", "th": "Thai", "ti": "Tigrinya", "tl": "Tagalog", "ua": "Ukrainian",
    "uk": "Ukrainian", "vi": "Vietnamese", "zh": "Chinese",
}

# Code + region, written as one token: zhcn, ptbr, frfr, swke, hiin, uauk.
REGIONS = {"af", "br", "cn", "es", "et", "fr", "hk", "ht", "in", "ke", "mx", "pt", "ru", "so", "tw", "uk", "us"}

# Names: languages anywhere but first. Misspellings are CDC's own.
NAMES = {
    "amharic": "Amharic", "arabic": "Arabic", "bengali": "Bengali", "burmese": "Burmese",
    "chamorro": "Chamorro", "chinese": "Chinese", "chuukese": "Chuukese", "dari": "Dari",
    "dzongkha": "Dzongkha", "english": ENGLISH, "espanol": "Spanish", "farsi": "Farsi",
    "french": "French", "german": "German", "greek": "Greek", "gujarati": "Gujarati",
    "haitian": "Haitian Creole", "haitiancreole": "Haitian Creole", "hebrew": "Hebrew", "hindi": "Hindi", "hmong": "Hmong",
    "ilocano": "Ilocano", "italian": "Italian", "japanese": "Japanese", "karen": "Karen",
    "khmer": "Khmer", "kinyardwanda": "Kinyarwanda", "kinyarwanda": "Kinyarwanda",
    "kirundi": "Kirundi", "korean": "Korean", "kunama": "Kunama", "kurdish": "Kurdish",
    "laotian": "Lao", "malay": "Malay", "maylay": "Malay", "marshallese": "Marshallese", "navajo": "Navajo",
    "nepali": "Nepali", "oromo": "Oromo", "pashto": "Pashto", "polish": "Polish",
    "portuguese": "Portuguese", "punjabi": "Punjabi", "rohingya": "Rohingya",
    "russian": "Russian", "samoan": "Samoan", "serbian": "Serbian", "somali": "Somali",
    "spanish": "Spanish", "swahili": "Swahili", "tagalog": "Tagalog", "tamil": "Tamil",
    "telugu": "Telugu", "thai": "Thai", "verdean": "Cape Verdean Creole", "tigrinya": "Tigrinya", "tigrynia": "Tigrinya",
    "tigryna": "Tigrinya", "tongan": "Tongan", "turkish": "Turkish", "ukrainian": "Ukrainian",
    "ukranian": "Ukrainian", "urdu": "Urdu", "uzbek": "Uzbek", "vietnamese": "Vietnamese",
    "yiddish": "Yiddish", "yupik": "Yupik",
}
# A name run into a qualifier or a stray letter: simplifiedchinese,
# chinesetraditional, frenchfrance, portuguesebrazil, iitalian. Only inside the
# tag run, or "polishing" would be Polish.
LONG_NAMES = sorted((n for n in NAMES if len(n) >= 5), key=len, reverse=True)

# Words that qualify a language next to it, and mean nothing on their own here.
# "cape verdean creole" is one language; "verdean" carries it.
# A region on its own (zh-cn, portuguese-br, ne-np) only qualifies too.
QUALIFIERS = {"bosnia", "brazil", "cape", "creole", "france", "portugal",
              "simplified", "traditional", "br", "cn", "np"}

NOISE = {"hr", "p", "508", "print", "plain", "final", "c", "fs"}

SPLIT = re.compile(r"[-_ .]+")


def tokens(filename: str) -> list[str]:
    stem = re.sub(r"\.[a-z0-9]{2,4}$", "", urllib.parse.unquote(filename).lower())
    return [t for t in SPLIT.split(stem) if t]


def name_language(tok: str, in_run: bool = True) -> str | None:
    if tok in NAMES:
        return NAMES[tok]
    if not in_run:
        return None
    for name in LONG_NAMES:
        if tok.startswith(name) or tok.endswith(name):
            return NAMES[name]
    return None


def code_language(tok: str) -> str | None:
    if tok in CODES:
        return CODES[tok]
    if len(tok) == 4 and tok[:2] in CODES and tok[2:] in REGIONS:
        return CODES[tok[:2]]
    return None


def split_languages(toks: list[str]) -> tuple[set[str], list[str]]:
    """The languages a filename's tokens name, and the tokens that are left."""
    run_start = len(toks)
    while run_start > 1:
        t = toks[run_start - 1]
        if t in NOISE or t in QUALIFIERS or t.isdigit() or code_language(t) or name_language(t):
            run_start -= 1
        else:
            break
    langs, rest = set(), []
    for i, t in enumerate(toks):
        in_run = i >= run_start
        lang = (name_language(t, in_run) if i > 0 else None) or (code_language(t) if in_run else None)
        if lang:
            langs.add(lang)
        elif t in NOISE or (in_run and t in QUALIFIERS):
            continue
        else:
            rest.append(t)
    return langs, rest


def fold(records: list[dict]) -> list[dict]:
    """Records of one source to documents: one per directory + remaining tokens."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for rec in records:
        directory, _, filename = rec["key"].rpartition("/")
        langs, rest = split_languages(tokens(filename))
        groups[(directory, " ".join(rest))].append(rec | {"languages": sorted(langs)})
    docs = []
    for members in groups.values():
        members.sort(key=lambda m: (bool(set(m["languages"]) - {ENGLISH}), m["timestamp"], m["key"]))
        rep = members[0]
        others = sorted({lang for m in members for lang in m["languages"]} - {ENGLISH})
        docs.append({k: v for k, v in rep.items() if k != "languages"} | {
            "languages": others,
            "first_ts": min(m["timestamp"] for m in members),
            "members": [{"key": m["key"], "languages": m["languages"], "timestamp": m["timestamp"]}
                        for m in members],
        })
    return sorted(docs, key=lambda d: d["key"])


def single(rec: dict) -> dict:
    return rec | {"languages": [], "first_ts": rec["timestamp"],
                  "members": [{"key": rec["key"], "languages": [], "timestamp": rec["timestamp"]}]}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--harvest", type=Path, default=root / "data" / "harvest.jsonl")
    ap.add_argument("--out", type=Path, default=root / "data" / "documents.jsonl")
    args = ap.parse_args()

    by_source: dict[str, list[dict]] = defaultdict(list)
    for line in args.harvest.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        by_source[rec["source"]].append(rec)

    print(f"{'source':<18} {'files':>7} {'docs':>6} {'translated':>11}", file=sys.stderr)
    languages = Counter()
    total = 0
    with args.out.open("w", encoding="utf-8") as sink:
        for source, records in by_source.items():
            docs = fold(records) if source in FOLD_SOURCES else [single(r) for r in records]
            translated = sum(1 for d in docs if d["languages"])
            print(f"{source:<18} {len(records):>7,} {len(docs):>6,} {translated:>11,}", file=sys.stderr)
            for d in docs:
                languages.update(d["languages"])
                sink.write(json.dumps(d, ensure_ascii=False) + "\n")
            total += len(docs)
    print(f"\nlanguages (documents with each): " +
          ", ".join(f"{lang} {n}" for lang, n in languages.most_common()), file=sys.stderr)
    print(f"wrote {total:,} documents to {args.out.relative_to(root)}", file=sys.stderr)


if __name__ == "__main__":
    main()
