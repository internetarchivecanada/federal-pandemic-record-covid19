# The Federal Pandemic Record

COVID-19 as the U.S. federal government told it on its own websites, from
December 2019 to the end of the Public Health Emergency on 11 May 2023,
preserved by the Wayback Machine.

*Picking this up? → [PICKUP.md](PICKUP.md)*

**Status: mockup.** Two views are planned, both drawn from Wayback captures:

- **Documents**: what CDC, HHS, the White House and other agencies published.
  Every link should replay a PDF or an official issuance, with translations of
  one document folded into a single record.
- **Pages over time**: how a short list of key pages changed month by month.
  This includes the months when a page CDC had moved was only a 1 KB redirect.

The mockup in `mockup/` runs on a real CDX sample harvested on 26 October 2026.
Serve the repository root and open it:

```bash
python3 -m http.server 8948
```

Then go to <http://localhost:8948/mockup/>. To rebuild its data from
`data/sample/`:

```bash
python3 build/mockup_data.py
```

The full pipeline is laid out in PICKUP.md. It follows
[Letters from Congress](https://github.com/internetarchivecanada/congressional-letters):
one static page, a small index, data fetched on demand, and every number
derived from the data at build time.
