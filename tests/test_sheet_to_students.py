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


def xlsx(tabs, fills=None):
    """fills: {(tab, row number): "RRGGBB"} — fill the whole row with that colour."""
    import openpyxl
    from openpyxl.styles import PatternFill

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in tabs.items():
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
        for (t, line), rgb in (fills or {}).items():
            if t == title:
                for cell in ws[line]:
                    cell.fill = PatternFill("solid", fgColor="FF" + rgb)
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
             "Самообучение", "batyrzhan.n@tumo.world", ""],
            ["Иван Петров", "Понедельник", "10:30-12:30", "Almas", "Nazym", "Самообучение", "", ""],
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

    def test_red_rows_are_excluded(self):
        tabs = {"ВТ ПТ 1430": [HEADER,
                               row("Активный Ученик", "Вторник", "Almas", "Almas"),
                               row("Красный Ученик", "Пятница", "Almas", "Almas"),
                               row("Светло Красный", "Пятница", "Almas", "Almas"),
                               row("Оранжевый Ученик", "Вторник", "Almas", "Almas"),
                               row("Жёлтый Ученик", "Вторник", "Almas", "Almas")]}
        fills = {("ВТ ПТ 1430", 3): "FF0000", ("ВТ ПТ 1430", 4): "E06666",
                 ("ВТ ПТ 1430", 5): "FF9900", ("ВТ ПТ 1430", 6): "FFFF00"}
        stats = {}
        students, _ = sts.parse(sts.read_tables(xlsx(tabs, fills)), stats=stats)
        self.assertEqual([s[0] for s in students], ["Активный Ученик", "Оранжевый Ученик", "Жёлтый Ученик"])
        self.assertEqual(stats, {"red": 2, "notes": 0})

    def test_red_old_row_of_a_moved_student_is_dropped(self):
        tabs = {"ПН ЧТ 1030": [HEADER, row("Сара Мухтар", "Понедельник", "Gulnaz", "Gulnaz")],
                "ВТ ПТ 1430": [HEADER, row("Сара Мухтар", "Пятница", "Gulnaz", "Alinur")]}
        students, problems = sts.parse(sts.read_tables(xlsx(tabs, {("ПН ЧТ 1030", 2): "FF0000"})))
        self.assertEqual(students, [["Сара Мухтар", "Пятница", "14:30-16:30", "Alinur", "Gulnaz", "Самообучение", "", ""]])
        self.assertEqual(problems, [])  # no duplicate left to resolve

    def test_inactive_keywords_in_notes_columns(self):
        header = HEADER + [None]  # an unlabelled note column after «Причина ухода»
        def r(name, reason="", extra=None, sched=""):
            cells = row(name, "Вторник", "Almas", "Almas", sched=sched)
            cells[12] = reason
            return cells + [extra]
        tabs = {"ВТ ПТ 1030": [header,
                               r("Первый Ученик", reason="ignore"),
                               r("Второй Ученик", reason="self initiated"),
                               r("Третий Ученик", reason="ЛИСТ ОЖИДАНИЯ 2027"),
                               r("Четвёртый Ученик", extra="отчислен"),
                               r("Пятый Ученик", sched="Вторник, Пятница : 10:30–12:30 (лист ожидания)"),
                               r("Шестой Ученик", reason="отказ, не успевает по учебе")]}
        stats = {}
        students, _ = sts.parse(sts.read_tables(xlsx(tabs)), stats=stats)
        # «Расписание» with "(лист ожидания)" is the originally requested slot, not a status
        self.assertEqual([s[0] for s in students], ["Пятый Ученик"])
        self.assertEqual(stats, {"red": 0, "notes": 5})

    def test_waitlist_notes_exclude_only_students_not_attending_now(self):
        out = ["ЛИСТ ОЖИДАНИЯ 2027", "ЛИСТ ОЖИДАНИЯ ЛЕТО 2027", "лист ожидания ноябрь", "лист ожидания - лето",
               "лист ожидания весна 2027", "Лист ожидания на ноябрь просит 16:30", "лист ожидания (16 30 в ноябре)",
               "хотят на 16:30 на след поток", "на новый поток", "хотят после НГ начать обучение",
               "не может посещать", "не сможет посещать, хочет в лист ожидания на лето", "отказ",
               "лист ожидание, отказ", "приостановлено обучени в связи с лечением", "wants to suspend till next year",
               "ignore", "self initiated", "отчислен"]
        keep = ["лист ожидания", "лист ожидания (хочет пн/чт 16:30)", "лист ожидания (хочет на 14:30)",
                "лист ожидания хочет на 16:30", "хочет на 16:30 лист ожидания", "ЛИСТ ОЖИДАНИЯ СЛ",
                "ЛИСТ ОЖИДАНИЯ 16:30", "wl 16:30 tue-fri", "хочет вт/пт 14:30", "не ответил",
                "пока будет ходить 14:30, хочет на пн/чт 16:30-18:30 (можно на сл)", "ребенок не в городе",
                "Новый коуч- отправить сообщение", "Almas Support must", "should be back in November"]
        for note in out:
            self.assertTrue(sts.INACTIVE_RE.search(note), note)
        for note in keep:
            self.assertFalse(sts.INACTIVE_RE.search(note), note)

    def test_is_red(self):
        from openpyxl.styles.colors import Color
        for rgb in ("FFFF0000", "FFE06666", "FFCC0000", "FFEA4335"):
            self.assertTrue(sts.is_red(Color(rgb=rgb)), rgb)
        for rgb in ("FFFF9900", "FFFF00FF", "FFFFFF00", "FFEA9999", "FFFFFFFF", "FF9900FF", "FF00FF00"):
            self.assertFalse(sts.is_red(Color(rgb=rgb)), rgb)
        self.assertTrue(sts.is_red(Color(indexed=10)))   # palette red
        self.assertFalse(sts.is_red(Color(theme=5)))     # theme colours aren't resolved
        self.assertFalse(sts.is_red(None))

    def test_onboarding_stream_tab(self):
        header = ["", "Номер родителя", "почта родителя", "ФИО ребенка", "Номер ребенка", "ДР ребенка",
                  "Расписание", "Коуч", "", "Зона обучения", "Почта тумо", "Создан аккаунт с графиком и коучем", ""]
        def kid(name, sched, coach, room, email, note=""):
            return ["Мама Ученика", "87001234567", "mama@gmail.com", name, "87770001122", "01.02.2013",
                    sched, coach, None, room, email, "True", note]
        tabs = {"4 поток": [header,
                            ["Понедельник, Четверг : 10:30–12:30"] + [None] * 12,  # section title row
                            kid("КУМАРБЕКОВ ДИАР", "Понедельник, Четверг : 10:30–12:30", "Ayaulym", "3 этаж, 7 WR",
                                "Diar.Kumarbekov@tumo.world"),
                            kid("Салибек Айша", " Вторник, Пятница : 16:30–18:30 ", "Aruzhan T", "2 этаж, зона SL", ""),
                            kid("Ушедший Ученик", "Вторник, Пятница : 14:30–16:30", "Alen", "3 этаж, 9 WR", "",
                                note="лист ожидания ноябрь"),
                            kid("Красный Ученик", "Вторник, Пятница : 14:30–16:30", "Alen", "3 этаж, 9 WR", "")],
                "5 поток": [header, kid("Пятый Поток", "Вторник, Пятница : 14:30–16:30", "Danel", "", "")]}
        raw = xlsx(tabs, {("4 поток", 6): "FF0000"})
        stats = {}
        students, problems = sts.parse(sts.read_tables(raw, streams=("4",)), stats=stats)
        self.assertEqual(students, [
            ["Кумарбеков Диар", "Понедельник", "10:30-12:30", "Ayaulym", "", "Онбординг",
             "diar.kumarbekov@tumo.world", "3 этаж, 7 WR"],
            ["Салибек Айша", "Вторник", "16:30-18:30", "Aruzhan Torebek", "", "Онбординг", "", "2 этаж, зона SL"],
        ])
        self.assertEqual(problems, [])
        self.assertEqual(stats, {"red": 1, "notes": 1})
        flat = repr(students)
        for private in ("Мама", "8700", "8777", "gmail", "01.02.2013"):
            self.assertNotIn(private, flat)
        # 5 поток is included by default
        with_5 = sts.parse(sts.read_tables(raw))[0]
        self.assertEqual(with_5[-1][:6], ["Пятый Поток", "Вторник", "14:30-16:30", "Danel", "", "Онбординг"])

    def test_html_login_page_is_rejected(self):
        with self.assertRaises(SystemExit):
            sts.read_tables(b"<!DOCTYPE html><html>Sign in</html>")


if __name__ == "__main__":
    unittest.main()
