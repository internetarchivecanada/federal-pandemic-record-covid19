import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import dates  # noqa: E402


class LiveUrl(unittest.TestCase):
    def test_mirror_to_live(self):
        self.assertEqual(
            dates.live_url("https://trumpwhitehouse.archives.gov/presidential-actions/eo-x/"),
            "https://www.whitehouse.gov/presidential-actions/eo-x/")

    def test_adds_slash_and_drops_query(self):
        self.assertEqual(
            dates.live_url("http://trumpwhitehouse.archives.gov/briefings-statements/y?utm_source=x"),
            "https://www.whitehouse.gov/briefings-statements/y/")

    def test_refuses_other_hosts(self):
        with self.assertRaises(ValueError):
            dates.live_url("https://bidenwhitehouse.archives.gov/briefing-room/x/")


class ParseFirst(unittest.TestCase):
    def test_found(self):
        r = dates.parse_first("20200313234554 https://www.whitehouse.gov/p/ L5LS\n")
        self.assertEqual((r["status"], r["first_ts"]), ("found", "20200313234554"))

    def test_empty_answer_is_none_not_error(self):
        self.assertEqual(dates.parse_first(""), {"status": "none"})


class Settled(unittest.TestCase):
    def test_one_empty_answer_is_asked_again(self):
        self.assertFalse(dates.settled({"status": "none"}))
        self.assertTrue(dates.settled({"status": "none", "asked": 2}))
        self.assertTrue(dates.settled({"status": "found", "first_ts": "20200429133024"}))
        self.assertFalse(dates.settled({"status": "error"}))
        self.assertFalse(dates.settled({}))

    def test_empty_then_found_is_found(self):
        answers = iter(["", "20200429133024 https://www.whitehouse.gov/p/ TRT2\n"])
        real = dates.ask_first
        dates.ask_first = lambda url: dates.parse_first(next(answers))
        try:
            r = dates.first_capture("https://www.whitehouse.gov/p/", pause=0)
        finally:
            dates.ask_first = real
        self.assertEqual((r["status"], r["first_ts"]), ("found", "20200429133024"))


class Period(unittest.TestCase):
    def test_bounds(self):
        self.assertTrue(dates.in_period("20191201000000"))
        self.assertTrue(dates.in_period("20230511235959"))
        self.assertFalse(dates.in_period("20190919120000"))
        self.assertFalse(dates.in_period("20230512000000"))


class Cache(unittest.TestCase):
    def test_last_line_wins_and_a_cut_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.jsonl"
            p.write_text('{"key": "a", "status": "error"}\n'
                         '{"key": "a", "status": "found", "first_ts": "20200101000000"}\n'
                         '{"key": "b", "sta')
            c = dates.read_cache(p)
            self.assertEqual(c["a"]["status"], "found")
            self.assertNotIn("b", c)


if __name__ == "__main__":
    unittest.main()
