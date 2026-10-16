# Run: python3 -m unittest discover -s tests
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import sync_schedule as ss  # noqa: E402


class ProperCaseTest(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(ss.proper_case("БАТЫРЖАН НҰРАЛИ АМАНГЕЛДІҰЛЫ"), "Батыржан Нұрали Амангелдіұлы")
        self.assertEqual(ss.proper_case("анна-мария  іван"), "Анна-Мария Іван")
        self.assertEqual(ss.proper_case("gulim (+DANA KURAK)"), "Gulim (+Dana Kurak)")
        self.assertEqual(ss.proper_case(None), "")

    def test_ex_coach_is_title_cased(self):
        self.assertEqual(ss.canon_ex_coach("ELMIRA (gulim)"), "Elmira (Gulim)")
        self.assertEqual(ss.canon_ex_coach("гульназ"), "Gulnaz")


class StudentsJsonTest(unittest.TestCase):
    def test_round_trip_title_cases_and_pads_email(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "students.json"
            ss.save_student_data([["ИВАН ПЕТРОВ", "Вторник", "10:30-12:30", "ALMAS", "nazym", "Самообучение"]], path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["fields"], ss.STUDENT_FIELDS)
            self.assertEqual(
                ss.load_student_data(path),
                [["Иван Петров", "Вторник", "10:30-12:30", "Almas", "Nazym", "Самообучение", ""]],
            )

    def test_updated_is_a_utc_timestamp(self):
        import datetime
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "students.json"
            ss.save_student_data([["Иван Петров", "Вторник", "10:30-12:30", "Almas", "Almas", "Самообучение"]], path)
            updated = json.loads(path.read_text(encoding="utf-8"))["updated"]
            ts = datetime.datetime.fromisoformat(updated)
            self.assertEqual(ts.utcoffset(), datetime.timedelta(0))
            self.assertLess(abs((datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds()), 60)

    def test_repo_data_is_valid(self):
        data = ss.load_student_data()
        self.assertGreater(len(data), 1000)
        for rec in data:
            self.assertEqual(len(rec), len(ss.STUDENT_FIELDS))
            self.assertEqual(rec[0], ss.proper_case(rec[0]))
            self.assertIn(rec[1], ss.DAYS_OK + ["Среда"])
            self.assertIn(rec[2], ss.TIMES_OK)


if __name__ == "__main__":
    unittest.main()
