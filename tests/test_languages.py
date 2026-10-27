import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import languages  # noqa: E402


def split(filename):
    langs, rest = languages.split_languages(languages.tokens(filename))
    return sorted(langs), " ".join(rest)


def rec(key, ts="20200401000000"):
    return {"source": "cdc-dl", "agency": "CDC", "key": key, "url_day": None,
            "original": "https://www." + key, "timestamp": ts, "mimetype": "application/pdf",
            "statuscode": "200", "digest": "D", "length": "1"}


class Tokens(unittest.TestCase):
    def test_split_unquote_and_extension(self):
        self.assertEqual(languages.tokens("Stop%20the_Spread-SP.pdf"), ["stop", "the", "spread", "sp"])


class SplitLanguages(unittest.TestCase):
    def test_code_and_name_in_the_tag_run(self):
        self.assertEqual(split("covid-19-share-facts-stop-fear_print_am_hr_amharic.pdf"),
                         (["Amharic"], "covid 19 share facts stop fear"))

    def test_my_outside_the_run_is_not_burmese(self):
        self.assertEqual(split("how_do_i_set_up_my_classroom.pdf"),
                         ([], "how do i set up my classroom"))
        self.assertEqual(split("covid19_family-guidance_my_hr_burmese.pdf"),
                         (["Burmese"], "covid19 family guidance"))

    def test_to_is_never_tongan(self):
        self.assertEqual(split("how-to-wear-a-mask-dari.pdf"), (["Dari"], "how to wear a mask"))
        self.assertEqual(split("how-to-wear-a-mask-english.pdf"), (["English"], "how to wear a mask"))

    def test_name_counts_anywhere_but_first(self):
        self.assertEqual(split("templog_portuguese-314925-e_covid-19_ptbr-p.pdf"),
                         (["Portuguese"], "templog 314925 e covid 19"))
        self.assertEqual(split("spanish-guide.pdf"), ([], "spanish guide"))

    def test_compound_tokens(self):
        for filename, lang in [("templog_iitalian.pdf", "Italian"),
                               ("key-steps-zh-cn.pdf", "Chinese"),
                               ("guide_simplifiedchinese.pdf", "Chinese"),
                               ("refugees-risk_uauk_hr-p.pdf", "Ukrainian"),
                               ("poster-swke-swahili.pdf", "Swahili"),
                               ("refugees-risk_psaf_hr-p.pdf", "Pashto")]:
            self.assertEqual(split(filename)[0], [lang], filename)

    def test_compound_names_only_in_the_run(self):
        # "polishing" starts with "polish"; mid-name it is a word, not Polish.
        self.assertEqual(split("polishing-floors-guide.pdf"), ([], "polishing floors guide"))

    def test_multi_word_languages_drop_their_qualifiers(self):
        self.assertEqual(split("covid19-symptoms-cape-verdean-creole.pdf"),
                         (["Cape Verdean Creole"], "covid19 symptoms"))
        self.assertEqual(split("2019-ncov-factsheet-serbian-bosnia.pdf"),
                         (["Serbian"], "2019 ncov factsheet"))

    def test_haitian_creole_is_a_language_not_two_qualifiers(self):
        # Before this, "10things-haitian-creole" folded in as if it were English.
        self.assertEqual(split("10things-haitian-creole.pdf"), (["Haitian Creole"], "10things"))

    def test_bilingual_before_a_date(self):
        self.assertEqual(split("doyourpart_t-han_nborder_eng-fr_4-9-20.pdf")[0], ["English", "French"])

    def test_a_word_after_the_codes_ends_the_run(self):
        # Under-merging by design: "only" ends the run before "en-es" is reached.
        self.assertEqual(split("324228-a_fs-vaxpromo-en-es-print-only.pdf"),
                         ([], "324228 a vaxpromo en es only"))


class Fold(unittest.TestCase):
    def test_translations_fold_under_the_english_file(self):
        docs = languages.fold([
            rec("cdc.gov/d/covid19-symptoms-sp.pdf", "20200301000000"),
            rec("cdc.gov/d/covid19-symptoms.pdf", "20200401000000"),
            rec("cdc.gov/d/covid19-symptoms-ko_hr_korean.pdf", "20200501000000")])
        self.assertEqual(len(docs), 1)
        d = docs[0]
        self.assertEqual(d["key"], "cdc.gov/d/covid19-symptoms.pdf")
        self.assertEqual(d["languages"], ["Korean", "Spanish"])
        self.assertEqual(d["first_ts"], "20200301000000")
        self.assertEqual(len(d["members"]), 3)

    def test_translation_only_document_keeps_its_earliest_file(self):
        docs = languages.fold([rec("cdc.gov/d/guide-es.pdf", "20200601000000"),
                               rec("cdc.gov/d/guide-arabic.pdf", "20200501000000")])
        self.assertEqual([d["key"] for d in docs], ["cdc.gov/d/guide-arabic.pdf"])
        self.assertEqual(docs[0]["languages"], ["Arabic", "Spanish"])

    def test_different_folders_do_not_fold(self):
        docs = languages.fold([rec("cdc.gov/a/guide.pdf"), rec("cdc.gov/b/guide-sp.pdf")])
        self.assertEqual(len(docs), 2)


if __name__ == "__main__":
    unittest.main()
