# Run: python3 -m unittest discover -s tests
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import sheet_to_students as sts  # noqa: E402

HEADER = ["Номер тел", "ИИН ученика / TUMO ID", "Новое расписание (при измении)", "Почта TUMO", "Расписание",
          "ФИО ученика", "День SL", "ex-Coach", "Новый коуч SL", "Ушел к коучу:", "Изменен график в Т360",
          "Отправлено соообщение", "Причина ухода"]


def row(name, day, ex, coach, email="", new="", sched="", phone="87001234567", iin="130101500123"):
    return [phone, iin, new, email, sched, name, day, ex, coach, None, "TRUE", "FALSE", "note"]


def xlsx(tabs):
    import openpyxl

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in tabs.items():
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class SheetToStudentsTest(unittest.TestCase):
    def setUp(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl not installed")

    def test_maps_columns_and_drops_private_fields(self):
        raw = xlsx({
            "ПН ЧТ 1030": [HEADER,
                           row("БАТЫРЖАН НҰРАЛИ АМАНГЕЛДІҰЛЫ", "Четверг ", "gulnaz", "Аружан Т",
                               email=" Batyrzhan.N@tumo.world ", sched="Понедельник, Четверг : 10:30–12:97"),
                           row("Иван Петров", "Понедельник", "Nazym", "Almas", email="ivan@gmail.com"),
                           row("Сломанный День", "Пятница", "", "Almas"),
                           [None] * 13],
            "Цифры": [["ON", 531]],
        })
        students, problems = sts.parse(sts.read_tables(raw))
        self.assertEqual(students, [
            ["Батыржан Нұрали Амангелдіұлы", "Четверг", "10:30-12:30", "Aruzhan Torebek", "Gulnaz",
             "Самообучение", "batyrzhan.n@tumo.world"],
            ["Иван Петров", "Понедельник", "10:30-12:30", "Almas", "Nazym", "Самообучение", ""],
        ])
        self.assertEqual(len(problems), 1)
        self.assertIn("Сломанный День", problems[0])
        flat = repr(students)
        self.assertNotIn("8700", flat)
        self.assertNotIn("130101", flat)

    def test_duplicate_prefers_confirmed_new_schedule_then_published(self):
        tabs = {
            "ПН ЧТ 1030": [HEADER, row("Сара Мухтар", "Понедельник", "Gulnaz", "Gulnaz")],
            "ВТ ПТ 1430": [HEADER, row("Сара Мухтар", "Пятница", "Gulnaz", "Alinur",
                                       new="Вторник, Пятница : 14:30–16:30")],
        }
        students, problems = sts.parse(sts.read_tables(xlsx(tabs)))
        self.assertEqual(students[0][1:4], ["Пятница", "14:30-16:30", "Alinur"])
        self.assertEqual(len(problems), 1)

        tabs["ВТ ПТ 1430"][1][2] = ""  # no confirmation -> keep what is published
        published = {sts.norm("Сара Мухтар"): ["Сара Мухтар", "Понедельник", "10:30-12:30"]}
        students, _ = sts.parse(sts.read_tables(xlsx(tabs)), published)
        self.assertEqual(students[0][1:3], ["Понедельник", "10:30-12:30"])

    def test_csv_single_tab_takes_time_from_schedule(self):
        csv_text = ",".join(HEADER) + "\n" + ",".join(
            '"%s"' % v for v in row("ДАРХАН АСКАРОВ", "Вторник", "Nazym", "Gulnaz",
                                    sched="Вторник, Пятница : 16:30–18:30.")) + "\n"
        students, _ = sts.parse(sts.read_tables(csv_text.encode("utf-8")))
        self.assertEqual(students[0][:3], ["Дархан Аскаров", "Вторник", "16:30-18:30"])

    def test_latin_lookalikes_in_cyrillic_names_are_fixed(self):
        self.assertEqual(sts.fix_mixed_script("Tөлеуғазы Алдияр"), "Төлеуғазы Алдияр")
        self.assertEqual(sts.fix_mixed_script("Iңкар Есiмхан Mади"), "Іңкар Есімхан Мади")
        self.assertEqual(sts.fix_mixed_script("Agayeva Zakhirat"), "Agayeva Zakhirat")
        raw = xlsx({"ПН ЧТ 1630": [HEADER, row("TӨЛЕУҒАЗЫ АЛДИЯР", "Четверг", "Nurai", "Elmira")]})
        students, _ = sts.parse(sts.read_tables(raw))
        self.assertEqual(students[0][0], "Төлеуғазы Алдияр")

    def test_html_login_page_is_rejected(self):
        with self.assertRaises(SystemExit):
            sts.read_tables(b"<!DOCTYPE html><html>Sign in</html>")


if __name__ == "__main__":
    unittest.main()
