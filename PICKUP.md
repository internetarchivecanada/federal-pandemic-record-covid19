# The Federal Pandemic Record: pickup

Hand this file to Claude Code and say "start the work". It records what a
Cowork session found on 22–25 October 2026 before moving here, so nothing
below needs to be re-surveyed. `data/pages-monthly.txt` is the page-timeline
file it refers to.

## Since the handoff (26 October 2026)

- Repository created: `internetarchivecanada/federal-pandemic-record-covid19`,
  **public** (Robin's decision). Steps 1 and 2 of "Start here" are done: CDX and
  `advancedsearch.php` both answer directly from Robin's Mac over https.
- A **mockup** is in `mockup/`, built by `build/mockup_data.py` from a CDX
  sample in `data/sample/` (harvested 26 Oct 2026). CDC downloads returned 2,550
  rows, matching the handoff. Its translation folding is a rough first pass —
  1,363 CDC documents from 1,983 files, against 1,294 below — and is not
  `build/languages.py`. ED and NIH are PDFs with status 200, not yet checked for
  topic or against the corpus rule. Biden actions: 44 in range by slug keyword
  (the handoff had 42). Trump White House items are not in yet.
- Archive-It partner 593 is corrected below.
- **Step 3 is done.** `build/sources.tsv` holds the table below as data, and
  `build/harvest.py` re-ran the 11 sources marked harvested, partial or retry
  in about 3 minutes, 26 Oct 2026. Run it again with `python3 build/harvest.py`.
  Raw rows match the survey exactly wherever it gave a count: CDC 2,550, ED
  134, NIH 289, HHS `covid*` 97, DHS 15, CISA 6. CDC folds to exactly the
  survey's 1,990 distinct files, and Trump actions give exactly 65 COVID.
  PHE, which failed twice in the survey, returned 215 rows and 124 distinct
  files. HHS `coronavirus*` returned 4. After cleaning: **2,824 records** in
  `data/harvest.jsonl`. Differences, recorded but not resolved:
  - ED keeps 29 of 134 rows: most are the same PDF with `utm_` query strings.
  - Biden actions: 44, all dated in the URL from 20 Jan 2021 to 9 May 2023,
    inside the period. The survey said 42 in range, without saying which cutoff
    it used.
  - Trump briefings: 208 against the survey's 195. The keyword list catches
    false positives such as "reopening the Washington Monument", so the list
    needs a read by hand either way.
- **Step 4 is done.** `build/dates.py` looked up the first status-200 capture
  of each of the 273 Trump White House items (65 actions, 208 briefings) at its
  `www.whitehouse.gov` address, 26 Oct 2026: about 16 minutes on 2 workers, 9
  network failures, all recovered on a re-run. Two items checked by hand: the national-emergency
  proclamation is first captured 13 Mar 2020 and "15 Days to Slow the Spread"
  16 Mar 2020, their issue dates. Result: **231 in the period**, peaking at
  71 in March 2020. **35 outside the period**: keyword false positives,
  dropping out on date as intended. Examples: the 2019 influenza-vaccine order,
  2017-2019 Defense Production Act determinations, and unrelated task forces.
  **7 have no capture**. Most are malformed mirror URLs (a stray `]`, a trailing
  `-` or `.5`) whose clean address is also in the corpus. The harvest's cleaning
  should probably drop them; not done yet.
- Not run yet: the paged sources (`cdc-ncov`, `hhs-files`) and the `wp-content`
  mirrors, which run only when named with `--source`.
- Still open: whether HTML issuances (statements, press releases) belong in the
  corpus, and whether state material is in scope. The mockup assumes federal
  only and links Archive-It 15784 as a companion.

## What we are building

An explorer of the COVID-19 pandemic as the U.S. federal government told it
on its own websites, preserved by the Wayback Machine. It follows
**Letters from Congress** (`internetarchivecanada/congressional-letters`, branch
`harvest-member-letters`): one static page, a small index, data fetched on
demand, the URL holding the whole state, and every number on the page derived
from the data at build time.

Decisions already made with Robin:

| | |
| --- | --- |
| Views | **Both**: (1) a corpus of published documents, (2) "how the page changed" timelines for a short list of key pages |
| Dates | **December 2019 – 11 May 2023** (end of the federal Public Health Emergency) |
| First milestone | Survey + working prototype + written plan for the full pipeline |
| Sources | Wayback for CDC, HHS, DHS, White House and other federal agencies; then archive.org collections |

**Read first:** `congressional-letters` README.md, CLAUDE.md and PICKUP.md.
Its conventions apply here: branch and PR, never commit to `main`; merging is
Robin's call; repos are private by default; GitHub Pages allows 10 builds an
hour; bump `app.js?v=` whenever it changes; stamp everything a build rewrites.

## The corpus rule (proposed)

**Every document opens as a document.** A Wayback link in the corpus must
replay a PDF or an official issuance page (executive order, proclamation,
memorandum, declaration, statement), not a hub page, a search page, a 404 shell
or a redirect stub. Fold translations of one document into one record that
lists its languages. Check the rule on a random sample of replays before
quoting any count.

## Environment notes

- The Cowork sandbox could not reach archive.org (proxy 403), so the survey ran
  as `fetch()` calls in a Chrome tab. Claude Code on Robin's machine should
  reach `web.archive.org/cdx/search/cdx` and `archive.org/advancedsearch.php`
  directly. Confirm with one request first.
- **Use https.** Letters from Congress found the http CDX endpoint returns 503s.
- Long jobs run from a **terminal under `caffeinate -i`**, not from inside a
  Claude session. Two workers with a pause is the stable rate there. Expect the
  same here.

## CDX: what worked and what didn't (measured)

| Query shape | Result |
| --- | --- |
| Domain-wide `cdc.gov` + regex filter on urlkey | **504 after ~68 s** |
| Prefix `www.cdc.gov/coronavirus/2019-ncov/` + mimetype filter | **504 after ~60 s** |
| Same prefix, `showNumPages=true` | **1,767 pages** (~6,000 rows each, ~32 s per page ≈ 16 h) |
| Prefix `.../2019-ncov/downloads/`, `collapse=urlkey`, `filter=mimetype:application/pdf`, `from=201912&to=202305` | **200 in 70 s, 2,550 rows** |
| Any **prefix** query on `www.whitehouse.gov/...` | **503 "Temporarily Offline" in ~5 s**, every time, including monthly sub-prefixes |
| **Exact** URL on `whitehouse.gov` | 200, fast |
| Prefixes on `trumpwhitehouse.archives.gov` / `bidenwhitehouse.archives.gov` | 200 in 8–20 s |
| Exact-URL timelines (`collapse=digest`) for single pages | 200 in 0.3–6 s |
| Prefix + regex keyword filter on large folders (`hhs.gov/sites/default/files/`, `fema.gov/sites/default/files/` …) | 503 / 504 |
| Filename-prefix trick (`.../files/covid`, `.../files/coronavirus`) | Fast when it works, but 503/504 on about half the attempts |

So the rule is **narrow prefixes, no regex on big folders**. For large folders,
use paged queries (`page=N`) with a per-page on-disk cache, filter locally, and
resume. Expensive pages fail first, so a partial run understates. Record failures
as failures and retry only those, as `harvest.py` does in Letters from Congress.

`collapse=urlkey` with `from=201912` returns the **first capture in range**,
which is the document's "by" date, an upper bound. Show it as "by March 2020",
never as a day, unless a date is in the URL or the document.

## Sources: status per agency

| Code | Source | Prefix | Status |
| --- | --- | --- | --- |
| CDC | CDC COVID downloads | `www.cdc.gov/coronavirus/2019-ncov/downloads/` | **Harvested:** 2,550 rows → 1,990 distinct files after stripping query strings → **1,294 documents** after folding translations; 336 have ≥1 translation (one fact sheet in 32 languages). First seen per year: 2020 1,369 · 2021 822 · 2022 274 · 2023 85 (rows) |
| CDC | Rest of `2019-ncov/` (PDFs outside `downloads/`) | same, paged | **Not done.** Needs the paged harvest (1,767 pages) |
| CDC | MMWR COVID reports | `www.cdc.gov/mmwr/volumes/69…72/` | Not done. Filenames (`mm6912e2-H.pdf`) carry no subject, so titles have to come from the MMWR tables of contents |
| ED | Dept. of Education | `www2.ed.gov/documents/coronavirus/` | **Harvested:** 134 rows |
| NIH | COVID-19 Treatment Guidelines files | `files.covid19treatmentguidelines.nih.gov/` | **Harvested:** 289 rows |
| WH-T | Trump presidential actions | `trumpwhitehouse.archives.gov/presidential-actions/` | **Harvested:** 1,787 actions, **65 COVID** by slug keyword. Archive-site captures start Jan 2021; date each by an exact-URL first-capture lookup on `www.whitehouse.gov/presidential-actions/<slug>/` (not done yet). |
| WH-T | Trump briefings & statements | `trumpwhitehouse.archives.gov/briefings-statements/` | **Harvested** with the keyword filter: **195** COVID items. Date them the same way. |
| WH-B | Biden presidential actions | `bidenwhitehouse.archives.gov/briefing-room/presidential-actions/` | **Harvested:** 1,183 actions, 44 COVID by slug, **42 in range**. Date is in the URL (`/2021/01/21/`). Link to `www.whitehouse.gov/...` at that date. |
| WH | White House PDFs (`wp-content/uploads/2020…2023/`) | | **Blocked** by the whitehouse.gov prefix 503. Try the archives.gov mirrors' `wp-content/uploads/`. |
| HHS | `www.hhs.gov/sites/default/files/` | | Partial: `covid*` = 97 rows. Other prefixes 503. Needs paging (425 pages). |
| PHE | PHE declarations | `www.phe.gov/emergency/news/healthactions/phe/` | Failed twice (network). Small; retry. |
| DHS | `www.dhs.gov/sites/default/files/publications/` | | Partial: `covid*` = 15 |
| CISA | `www.cisa.gov/sites/default/files/publications/` | | Partial: `covid*` = 6. The essential critical infrastructure workforce guidance PDFs are not named `covid*`; look at `cisa.gov/identifying-critical-infrastructure-during-covid-19` for their URLs. |
| FEMA, CMS, OSHA, Treasury, SBA, DOL, USDA, VA | see `build/sources.tsv` to write | | Queued, not finished when the browser dropped |
| FDA | `www.fda.gov/media/<id>/download` | | Filenames are numeric; titles must come from the linking pages. Do this later. |

Keyword regex used on slugs (tested; an earlier version matched "ppe" inside
"copper", so keep the word boundaries):

```
(covid|coronavirus|pandemic|vaccin|sars-cov|public-health-emergency|novel-corona|
(^|-)masks?(-|$)|mask-wearing|(^|-)testing(-|$)|reopen|cares-act|american-rescue|
paycheck|stimulus|quarantine|social-distanc|ventilator|(^|-)dpa(-|$)|
defense-production-act|(^|-)ppe(-|$)|personal-protective|long-covid|omicron|
delta-variant|suspension-of-entry|suspending-entry|immigrants-who-present-risk|
economic-relief|eviction|student-loan|task-force|opening-up-america|warp-speed|
hydroxychloroquine)
```

Slug keywords both over- and under-match. Review the Trump/Biden lists by hand
(65 + 195 + 42 items is a short read). For example, a 2019 influenza-vaccine
executive order matches and falls out only on date.

### Folding translations (CDC)

CDC names translations by suffix in many spellings: `-sp`, `-es`, `_ESP`,
`-spanish`, `_ZHCN_HR`, `-chinese`, `_KO_HR_Korean`, `_FAAF_Dari`, `-tigryna`,
`-tigrynia`, `-kinyardwanda`, `TempLog_IItalian`. Method that worked: split the
filename on `[-_ .]`, treat a known language token as the language when it is
not the first token (two- to four-letter codes only near the end), drop noise
tokens (`hr`, `p`, `508`, `print`, `plain`, `final`, `c`, `fs`), and group by
directory + remaining tokens. Keep the English or untagged file as the
representative and list the languages. Write this as `build/languages.py` with
unit tests, including cases that look like languages but aren't (`to` and `my`
are also ISO codes).

## View 2: key pages over time

`data/pages-monthly.txt` holds 27 pages already measured with
`collapse=digest`, `filter=statuscode:200`, Dec 2019–May 2023. Format:

```
#key|url|versions|first_ts|last_ts
YYYYMM:DDhhmmss(first capture that month):versions_that_month:median_KB ...
```

"Versions" means adjacent-digest changes. CDC pages carry dynamic markup, so
the CDC home page shows 14,968 versions. Digest change is **not** content
change. For "what changed", compare extracted text between monthly snapshots,
for example with the org's `compare` tool (wayback-labs.sf.archive.org/wayback-changes/compare/,
repo `internetarchivecanada/compare`), and link Wayback's own diff
(`web.archive.org/web/diff/<ts1>/<ts2>/<url>`).

**Finding: CDC's moved pages become 1 KB placeholders.** When CDC moved a page,
the old URL kept answering **200** with a ~1 KB redirect page, and Wayback kept
capturing it. Median size by month:

| Page | Real page | Then |
| --- | --- | --- |
| `prevent-getting-sick/cloth-face-cover.html` | 50–57 KB, Apr–Jun 2020 | ~1 KB from Jul 2020 |
| `if-you-are-sick/quarantine.html` | 53–77 KB to Aug 2021 | ~1 KB from Sep 2021 |
| `your-health/quarantine-isolation.html` (its successor) | 73–81 KB | ~1 KB from Sep 2022 |
| `cases-updates/cases-in-us.html` | 48–73 KB | ~1 KB from Sep 2020 |
| `schools-childcare/operation-strategy.html` | 94–107 KB | ~1 KB from Feb 2022 |
| `schools-childcare/k-12-guidance.html` | 92–94 KB | ~1 KB from Jun 2022 |
| `need-extra-precautions/people-at-increased-risk.html` | 52–71 KB | 1–2.4 KB from Oct 2020 |

The same trap shows up in the document corpus (Letters from Congress calls it
the "download wrapper"). The explorer should mark placeholder months and follow
the page to its successor. Flag a month when its median size is under ~15% of
that page's largest monthly median.

Other measured shapes worth showing: coronavirus.gov runs Mar 2020–Oct 2021 at
~5 KB (a portal to CDC); covid.gov first appears Mar 2022; covidtests.gov is
captured only Jan–Mar 2022 in range; the FDA COVID hub grows steadily from 28 KB
to 129 KB; the PHE declaration page has 590 versions, with a capture spike in
Jan 2023 (61 that month).

## archive.org: what is there (searched 25 Oct 2026)

Federal material worth linking. Verify partner names before publishing them:

- **Archive-It 13721** "Coronavirus (COVID-19)" and **19129** "COVID.gov", both
  Archive-It partner **593**, which is the **Federal Depository Library Program
  Web Archive** (title of `ArchiveIt-Partner-593`, checked 26 Oct 2026), not NLM.
- **Archive-It 18608** COVIDtests.gov.
- **Archive-It 16018** "David J. Sencer CDC Museum COVID-19 Collection Web
  Archive" and **20471** "David J. Sencer CDC Museum COVID-19 Timeline Links".
  The museum's own timeline is a strong backbone for the events track.
- **Archive-It 15784** "State Executive Actions Related to the COVID-19 Pandemic"
  (states, not federal, but a natural companion).
- **TV News Archive**: C-SPAN "White House Coronavirus Task Force Briefing"
  recordings, Mar–Jul 2020 (`collection:TV-CSPAN`). Get the full count.
- `cdc-youtube-channel`: CDC YouTube videos (`yt_*` items).
- `COVID-19_Apps`: archived apps, including `gov.cdc.general.apk`.
- `USGovernmentDocuments`: e.g. `presidenttrumpscoronavirusguidelinesforamerica`.
- More than 300 COVID Archive-It collections exist, mostly universities and
  localities. Searching `mediatype:collection` for COVID with "federal" in the
  title or description found only 7.

Leave out of the explorer: `opensource`/`community` uploads tagged `fringe` or
`deemphasize`, and `perma_cc` items.

## Events track (verify each before use)

Draft dates for markers on the timeline: HHS PHE declared 31 Jan 2020; national
emergency proclamation 13 Mar 2020; "15 Days to Slow the Spread" 16 Mar 2020;
CARES Act 27 Mar 2020; CDC cloth face-covering recommendation 3 Apr 2020;
Opening Up America Again 16 Apr 2020; first vaccine EUA 11 Dec 2020; Biden
national strategy 21 Jan 2021; American Rescue Plan 11 Mar 2021; CDC
fully-vaccinated mask guidance 13 May 2021 and its reversal 27 Jul 2021;
isolation shortened 27 Dec 2021; COVIDtests.gov opens Jan 2022; CDC streamlined
guidance 11 Aug 2022; national emergency ended 10 Apr 2023; PHE ended 11 May
2023. Prefer linking each to its own archived federal page in the corpus.

## Proposed pipeline (mirrors congressional-letters)

```
build/sources.tsv          agency, prefix, mode (prefix|paged|exact|archives-mirror), filters
build/harvest.py           CDX per source → data/cdx-cache/ (raw rows, resumable, failures recorded)
build/dates.py             exact-URL first-capture lookups (Trump WH items), URL dates (Biden)
build/languages.py         translation folding + tests
build/classify.py          slug → title, doc type (EO, proclamation, memo, guidance, fact sheet,
                           poster, checklist, FAQ, toolkit, transcript, form), topics
build/pages.py             key-page monthly timelines → payload/pages/<key>.json
build/verify_sample.py     replay N random corpus links; record PDF/HTML/stub/404
build/thumbs.py            later: first-page renders, WebP q72, by digest (as in Letters)
build/build_site.py        index.json (counts, facets, histogram, stamp) + payload/
tests/
```

Prototype explorer, in this order:

1. **Documents.** Month histogram Dec 2019–May 2023 with event markers. Facets
   for agency, topic, document type and "translated". Search over titles. Each
   row shows its date ("by Mar 2020"), agency, title from the slug, languages,
   and a Wayback link.
2. **Pages over time.** One row per key page: a sparkline of versions per
   month, a size line, placeholder months marked, and a link to the successor
   page. Expanding a row shows monthly snapshot links plus diff and compare
   links.
3. **On archive.org.** The collections above, with counts derived from search.
4. **About.** The corpus rule, the traps, and caveats with their measured
   numbers.

## Start here

1. Confirm direct access: one CDX request and one advancedsearch request.
2. Create the repo (private, under internetarchivecanada, after asking Robin
   about the name) and copy this file in as `PICKUP.md`, with
   `data/pages-monthly.txt`.
3. Write `build/sources.tsv` from the table above and run `harvest.py` on the
   sources marked Harvested. That rebuilds what the browser held, in minutes.
4. Run `dates.py` for the 260 Trump White House items. Exact lookups are cheap.
   Keep it to 2 workers.
5. Build the prototype on that corpus and open a PR. Then start the long paged
   harvests (CDC `2019-ncov/`, HHS files) from a terminal.

Open questions for Robin: the repo name; whether the corpus should include HTML
issuances (statements, press releases) or only PDFs and formal actions; and
whether state-level material belongs in scope.
