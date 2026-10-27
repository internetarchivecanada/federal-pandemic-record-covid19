import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import harvest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def src(**kw):
    base = {"code": "t", "agency": "T", "prefix": "www.example.gov/files/",
            "mode": "prefix", "filters": "", "dated": "yes", "select": "all"}
    return base | kw


def row(url, ts="20200401000000"):
    return {"original": url, "timestamp": ts, "mimetype": "application/pdf",
            "statuscode": "200", "digest": "D", "length": "1"}


class Keywords(unittest.TestCase):
    def test_matches(self):
        for s in ["covid-19-guidance", "face-masks", "mask", "ppe-shortage",
                  "proclamation-on-the-suspension-of-entry", "invoking-the-dpa",
                  "testing", "opening-up-america-again"]:
            self.assertTrue(harvest.KEYWORDS.search(s), s)

    def test_word_boundaries(self):
        # "ppe" inside "copper" was the bug that made the boundaries necessary.
        for s in ["copper-mining", "maskell-report", "contesting-results",
                  "dpaa-accounting", "upper-basin"]:
            self.assertFalse(harvest.KEYWORDS.search(s), s)


class ParseRows(unittest.TestCase):
    def test_rows(self):
        body = "http://a/x.pdf 20200101000000 application/pdf 200 D 10\n"
        self.assertEqual(harvest.parse_rows(body)[0]["timestamp"], "20200101000000")

    def test_resume_key_is_a_failure(self):
        body = "http://a/x.pdf 20200101000000 application/pdf 200 D 10\n\ngov,a)/y.pdf+20200102\n"
        with self.assertRaises(RuntimeError):
            harvest.parse_rows(body)

    def test_empty_is_empty_not_a_failure(self):
        self.assertEqual(harvest.parse_rows(""), [])


class Clean(unittest.TestCase):
    def test_query_strings_fold_and_earliest_wins(self):
        rows = [row("https://www.example.gov/files/a.pdf?v=2", "20200501000000"),
                row("http://www.example.gov/files/a.pdf", "20200301000000"),
                row("https://example.gov/files/A.pdf", "20200401000000")]
        out = harvest.clean(src(), rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["timestamp"], "20200301000000")

    def test_index_page_dropped(self):
        out = harvest.clean(src(), [row("https://www.example.gov/files/"),
                                    row("https://www.example.gov/files/b.pdf")])
        self.assertEqual([r["key"] for r in out], ["example.gov/files/b.pdf"])

    def test_keyword_select_reads_the_last_segment(self):
        s = src(select="keywords", prefix="www.example.gov/coronavirus-actions/")
        out = harvest.clean(s, [row("https://www.example.gov/coronavirus-actions/budget-memo/"),
                                row("https://www.example.gov/coronavirus-actions/covid-memo/")])
        self.assertEqual(len(out), 1)

    def test_url_date_outside_the_period_is_dropped(self):
        s = src(select="keywords", prefix="www.example.gov/actions/")
        out = harvest.clean(s, [
            row("https://www.example.gov/actions/2019/09/19/order-modernizing-influenza-vaccines/"),
            row("https://www.example.gov/actions/2021/01/21/order-covid-19-response/"),
            row("https://www.example.gov/actions/2023/05/12/memo-vaccine-requirements/")])
        self.assertEqual([r["url_day"] for r in out], ["20210121"])

    def test_filename_prefix_source_keeps_its_files(self):
        # A prefix like .../files/covid ends mid-filename; it is not a folder.
        s = src(prefix="www.example.gov/files/covid")
        out = harvest.clean(s, [row("https://www.example.gov/files/covid-guidance.pdf"),
                                row("https://www.example.gov/files/budget.pdf")])
        self.assertEqual([r["key"] for r in out], ["example.gov/files/covid-guidance.pdf"])

    def test_mangled_link_with_a_twin_is_dropped(self):
        s = src(prefix="www.example.gov/actions/")
        good = "https://www.example.gov/actions/proclamation-covid-19-outbreak/"
        out = harvest.clean(s, [row(good),
                                row("https://www.example.gov/actions/proclamation-covid-19-outbreak]/"),
                                row("https://www.example.gov/actions/proclamation-covid-19-outbreak-.5/"),
                                row("https://www.example.gov/actions/proclamation-covid-19-outbreak-"),
                                row("https://www.example.gov/actions/page.aspx%20"),
                                row("https://www.example.gov/actions/page.aspx&data=05|01|a@b.edu&reserved=0"),
                                row("https://www.example.gov/actions/page.aspx"),
                                row('https://www.example.gov/actions%22,%22contextTitle%22:%22X%22')])
        self.assertEqual([r["key"] for r in out],
                         ["example.gov/actions/page.aspx",
                          "example.gov/actions/proclamation-covid-19-outbreak"])

    def test_mangled_link_without_a_twin_is_kept(self):
        out = harvest.clean(src(), [row("https://www.example.gov/files/only-trace.pdf%3E")])
        self.assertEqual([r["key"] for r in out], ["example.gov/files/only-trace.pdf>"])

    def test_second_real_extension_is_not_a_tail(self):
        # Measured 26 Oct 2026: the cdc-dl .pdf.pdf and .pdf files differ in digest.
        for k in ["example.gov/files/a.pdf.pdf", "example.gov/files/a.html.pdf",
                  "example.gov/files/manual final_508.docx", "example.gov/files/data.xlsx"]:
            self.assertEqual(harvest.well_formed(k), k)


class Sources(unittest.TestCase):
    def test_sources_tsv_loads(self):
        sources = harvest.load_sources(ROOT / "build" / "sources.tsv")
        self.assertTrue(any(s["status"] == "harvested" for s in sources))
        for s in sources:
            self.assertNotIn("whitehouse.gov/", s["prefix"].replace("archives.gov", ""),
                             f"{s['code']}: whitehouse.gov prefix queries answer 503")


if __name__ == "__main__":
    unittest.main()
