# Next build on the Mac

Written 5 November 2026. The live `corpus.js` was built on 27 October 2026
from a harvest of 26 October. Since then, pipeline changes have been merged
that only a full build puts on the page. This file is the run that does it.
Delete it, or replace it, once the build is merged.

## Why a build is needed

- **#39, PHE renewals.** A new source, `phe-aspr`
  (`aspr.hhs.gov/legal/PHE/Pages/`), adds the six renewals from January 2022
  to February 2023. The build also drops `covid19-7April2021`, an opioid crisis
  renewal that the live page lists as a COVID one. HHS (ASPR) should go from 9
  to 14. Merge #39 before building; this file assumes it is on `main`.

Nothing else waiting needs a rebuild. Text, images and the events list are
already live.

## Before you start

The harvested data is not in the repository (`data/` is ignored), so this is
a full run from an empty cache unless the Mac still has `data/` from the
October build. Either way is fine: the cache only saves time.

```bash
cd /path/to/federal-pandemic-record-covid19
```

```bash
git switch main && git pull
```

```bash
git switch -c rebuild-$(date +%Y-%m-%d)
```

```bash
python3 -m unittest discover -s tests
```

The tests should pass, 43 of them, before anything is fetched.

## The run

Run these from a terminal, not from inside an editor or an agent session, and
keep the Mac awake with `caffeinate -i`. A sleeping machine pauses the run and
the Wayback Machine drops the connection.

1. **Harvest** the sources marked harvested, partial or retry. About 3 minutes.

   ```bash
   caffeinate -i python3 build/harvest.py
   ```

   It prints one row per source. Check that no row says `FAILED`. Re-run the
   same command to retry only the failed ones. Expect `phe` about 215 raw /
   115 kept and `phe-aspr` about 102 raw / 55 kept (measured 5 Nov 2026).

2. **Date** the Trump White House items by their first capture on
   `www.whitehouse.gov`. About 16 minutes; keep it to 2 workers.

   ```bash
   caffeinate -i python3 build/dates.py
   ```

   A few network failures are normal. Re-run until it reports none.

3. **Fold** CDC translations into one record each. Seconds.

   ```bash
   python3 build/languages.py
   ```

4. **Build** `corpus.js`. Seconds.

   ```bash
   python3 build/build_site.py
   ```

   It prints a count per agency. Compare with the live build:

   | Agency | 27 Oct 2026 | Expected now |
   |---|---|---|
   | CDC | 1,259 | about the same |
   | White House (Trump) | 232 | about the same |
   | NIH | 217 | about the same |
   | White House (Biden) | 44 | about the same |
   | ED | 29 | about the same |
   | HHS | 28 | about the same |
   | DHS | 15 | about the same |
   | **HHS (ASPR)** | **9** | **14** |
   | CISA | 6 | about the same |
   | Total | 1,839 | about 1,844 |

   "About the same" because the Wayback index keeps growing: a few more
   captures can move a number by one or two. A large change in any other
   agency means something went wrong; stop and look before committing.

## Check it

```bash
python3 -m http.server 8948
```

Open <http://localhost:8948/>, tick **HHS (ASPR)** on Browse the Documents,
and check the list: the 2020 determination, then renewals from 21 Apr 2020 to
9 Feb 2023, with no 7 Apr 2021 and none twice.

Then run the explorer checks skill on the branch, all five views:
`./`, `./#documents`, `./#pages`, `./#archive`, `./#about`. The previous run
passed with 9 items for review (all cleared) and 3 advisories. A new data file
should not change that. If it does, read the report before committing.

## Commit

Commit `corpus.js` and the re-rendered `security-accessibility-checks.md`
only. Nothing under `data/`.

```bash
git add corpus.js security-accessibility-checks.md
```

```bash
git commit -m "Rebuild corpus.js: PHE renewals to Feb 2023, opioid renewal out"
```

```bash
git push -u origin HEAD
```

```bash
gh pr create --base main --title "Rebuild corpus.js" --body "Closes #17."
```

In the PR, paste the per-agency counts from step 4 beside the table above.
Merging it closes #17. The header line "Wayback Machine searched …" will show
the new harvest date.

## Longer harvests, when there is time

Each adds a lot of new material. Run one, rebuild (steps 2 to 4), and open its
own PR, so a problem in one does not hold up the others. Run each by name:

| Issue | Source | Command | Time |
|---|---|---|---|
| #14 | CDC `2019-ncov/` beyond downloads | `caffeinate -i python3 build/harvest.py --source cdc-ncov` | about 16 hours, resumable |
| #16 | HHS files folder | `caffeinate -i python3 build/harvest.py --source hhs-files` | hours, resumable |
| #18 | Trump White House attachments | `caffeinate -i python3 build/harvest.py --source wh-uploads-trump` | not yet measured |
| #19 | Biden White House attachments | `caffeinate -i python3 build/harvest.py --source wh-uploads-biden` | not yet measured |

The paged runs write one cache file per index page, so stopping and starting
again picks up where they left off. Trump attachments need dating like the
other Trump items before they can go in; check `build_site.py` handles them
before building.

## Do not

- Edit `corpus.js` by hand. It is rebuilt from the data, and a hand edit
  disappears on the next build.
- Commit `data/`. It is large and it is ignored on purpose.
- Build on another machine and copy `corpus.js` over. Counts depend on the
  harvest date, and mixing harvests makes them impossible to explain.
