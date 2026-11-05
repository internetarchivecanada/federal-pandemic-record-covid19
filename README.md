# The Federal Pandemic Record

COVID-19 as the U.S. federal government told it on its own websites, from
December 2019 to the end of the Public Health Emergency on 11 May 2023,
preserved by the Wayback Machine.

**Live at <https://internetarchivecanada.github.io/federal-pandemic-record-covid19/>**

*Picking this up? → [PICKUP.md](PICKUP.md)*

Two views, both drawn from Wayback captures:

- **Documents**: what CDC, HHS, the White House and other agencies published.
  Every link should replay a PDF or an official issuance, with translations of
  one document folded into a single record.
- **Pages over time**: how a short list of key pages changed month by month.
  This includes the months when a page CDC had moved was only a 1 KB redirect.

## Building

GitHub Pages serves `index.html`, `app.js` and `corpus.js` from the root of `main`.
`corpus.js` is built from the pipeline's outputs, which are not committed. The build waiting to run, with what to check, is in
[NEXT-BUILD.md](NEXT-BUILD.md). The steps are:

```bash
python3 build/harvest.py
```

```bash
python3 build/dates.py
```

```bash
python3 build/languages.py
```

```bash
python3 build/build_site.py
```

To look at the page locally, serve the repository root and open
<http://localhost:8948/>:

```bash
python3 -m http.server 8948
```

Tests: `python3 -m unittest discover -s tests`.

The pipeline is laid out in PICKUP.md. It follows
[Letters from Congress](https://github.com/internetarchivecanada/congressional-letters):
one static page, a small index, and every number derived from the data at
build time.

## Credits

Built by Robin Fay, Project Manager, Digital Collections, Democracy's
Library.

Images: the SARS-CoV-2 illustration in the header is by Alissa Eckert and Dan
Higgins at the CDC ([public domain](https://commons.wikimedia.org/wiki/File:SARS-CoV-2_without_background.png)).
The microscope image on the About page is by NIAID-RML
([CC BY 2.0](https://commons.wikimedia.org/wiki/File:Novel_Coronavirus_SARS-CoV-2.jpg)).
Both are resized copies in `img/`, because the page loads images only from
itself.
