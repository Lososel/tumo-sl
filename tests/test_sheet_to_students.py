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
             "Самообучение", "batyrzhan.n@tumo.world", "", "", []],
            ["Иван Петров", "Понедельник", "10:30-12:30", "Almas", "Nazym", "Самообучение", "", "", "", []],
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

    def test_row_colours_give_the_status(self):
        tabs = {"ВТ ПТ 1430": [HEADER,
                               row("Активный Ученик", "Вторник", "Almas", "Almas", email="a@tumo.world"),
                               row("Красный Ученик", "Пятница", "Almas", "Almas", email="r@tumo.world"),
                               row("Светло Красный", "Пятница", "Almas", "Almas"),
                               row("Оранжевый Ученик", "Вторник", "Almas", "Almas"),
                               row("Жёлтый Ученик", "Вторник", "Almas", "Almas"),
                               row("Фиолетовый Ученик", "Вторник", "Almas", "Almas", email="p@tumo.world"),
                               row("Тёмно Фиолетовый", "Вторник", "Almas", "Almas"),
                               row("Светло Фиолетовый", "Вторник", "Almas", "Almas"),
                               row("Пурпурный Ученик", "Вторник", "Almas", "Almas")]}
        fills = {("ВТ ПТ 1430", 3): "FF0000", ("ВТ ПТ 1430", 4): "E06666",
                 ("ВТ ПТ 1430", 5): "FF9900", ("ВТ ПТ 1430", 6): "FFFF00",
                 ("ВТ ПТ 1430", 7): "9900FF", ("ВТ ПТ 1430", 8): "674EA7",
                 ("ВТ ПТ 1430", 9): "B4A7D6", ("ВТ ПТ 1430", 10): "FF00FF"}
        stats = {}
        students, _ = sts.parse(sts.read_tables(xlsx(tabs, fills)), stats=stats)
        status = {s[0]: s[8] for s in students}
        self.assertEqual(status, {"Активный Ученик": "", "Красный Ученик": "inactive", "Светло Красный": "inactive",
                                  "Оранжевый Ученик": "", "Жёлтый Ученик": "", "Фиолетовый Ученик": "waitlist",
                                  "Тёмно Фиолетовый": "waitlist", "Светло Фиолетовый": "", "Пурпурный Ученик": ""})
        # inactive / waitlist rows keep only the name and stage
        red = next(s for s in students if s[0] == "Красный Ученик")
        self.assertEqual(red, ["Красный Ученик", "", "", "", "", "Самообучение", "", "", "inactive", []])
        purple = next(s for s in students if s[0] == "Фиолетовый Ученик")
        self.assertEqual(purple, ["Фиолетовый Ученик", "", "", "", "", "Самообучение", "", "", "waitlist", []])
        self.assertEqual(stats, {"red": 2, "purple": 2, "notes_inactive": 0, "notes_waitlist": 0})

    def test_active_row_wins_over_red_or_purple_old_row(self):
        tabs = {"ПН ЧТ 1030": [HEADER, row("Сара Мухтар", "Понедельник", "Gulnaz", "Gulnaz")],
                "ВТ ПТ 1430": [HEADER, row("Сара Мухтар", "Пятница", "Gulnaz", "Alinur")],
                "ВТ ПТ 1630": [HEADER, row("Сара Мухтар", "Вторник", "Gulnaz", "Gulnaz")]}
        fills = {("ПН ЧТ 1030", 2): "FF0000", ("ВТ ПТ 1630", 2): "9900FF"}
        students, problems = sts.parse(sts.read_tables(xlsx(tabs, fills)))
        self.assertEqual(students, [["Сара Мухтар", "Пятница", "14:30-16:30", "Alinur", "Gulnaz", "Самообучение", "", "", "", []]])
        self.assertEqual(problems, [])  # an old red/purple copy is not an ambiguity
        # only red + purple rows: waitlist wins over inactive
        only_old = {k: v for k, v in tabs.items() if k != "ВТ ПТ 1430"}
        students, _ = sts.parse(sts.read_tables(xlsx(only_old, fills)))
        self.assertEqual(students[0][8], "waitlist")

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
        self.assertEqual({s[0]: s[8] for s in students}, {
            "Первый Ученик": "inactive", "Второй Ученик": "inactive", "Третий Ученик": "waitlist",
            "Четвёртый Ученик": "inactive", "Пятый Ученик": "", "Шестой Ученик": "inactive"})
        self.assertEqual(stats, {"red": 0, "purple": 0, "notes_inactive": 4, "notes_waitlist": 1})

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
            self.assertEqual(sts.note_status(note), "", note)
        # left -> inactive (red-row message); paused / later waitlist -> waitlist (suspended message)
        for note in ("отказ", "лист ожидание, отказ", "не может посещать", "ignore", "self initiated", "отчислен"):
            self.assertEqual(sts.note_status(note), "inactive", note)
        for note in ("ЛИСТ ОЖИДАНИЯ 2027", "лист ожидания ноябрь", "приостановлено обучени", "на новый поток",
                     "wants to suspend till next year", "хотят после НГ начать обучение"):
            self.assertEqual(sts.note_status(note), "waitlist", note)

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
             "diar.kumarbekov@tumo.world", "3 этаж, 7 WR", "", []],
            ["Салибек Айша", "Вторник", "16:30-18:30", "Aruzhan Torebek", "", "Онбординг", "", "2 этаж, зона SL", "", []],
            ["Ушедший Ученик", "", "", "", "", "Онбординг", "", "", "waitlist", []],
            ["Красный Ученик", "", "", "", "", "Онбординг", "", "", "inactive", []],
        ])
        self.assertEqual(problems, [])
        self.assertEqual(stats, {"red": 1, "purple": 0, "notes_inactive": 0, "notes_waitlist": 1})
        flat = repr(students)
        for private in ("Мама", "8700", "8777", "gmail", "01.02.2013"):
            self.assertNotIn(private, flat)
        # 5 поток is included by default
        with_5 = sts.parse(sts.read_tables(raw))[0]
        self.assertEqual(with_5[-1][:6], ["Пятый Поток", "Вторник", "14:30-16:30", "Danel", "", "Онбординг"])

    def test_workshop_sheet_is_attached_by_full_name(self):
        import datetime
        tabs = {"ПН ЧТ 1030": [HEADER,
                               row("Аскерұлы Есбер", "Понедельник", "Gulnaz", "Gulnaz", email="askeruly.esber@tumo.world"),
                               row("Иван Петров Сергеевич", "Четверг", "Almas", "Almas"),
                               row("Красный Ученик", "Понедельник", "Almas", "Almas"),
                               row("Айгерим Сапарова", "Понедельник", "Almas", "Almas"),
                               row("Айгерим Сапарова Ерлановна", "Четверг", "Almas", "Almas")]}
        master = xlsx(tabs, {("ПН ЧТ 1030", 4): "FF0000"})
        workshops = xlsx({"Лист1": [
            ["ФИО ученика", "Воркшоп", "Кабинет / Зона", "Коуч", "Дни и время", "Дата начала", "Дата окончания",
             "Дата изменения", "Телефон"],
            ["АСКЕРУЛЫ ЕСБЕР", "Game Development 2", "3 этаж, 5 WR", "Ахмет", "Вт, Пт 16:30–18:30",
             datetime.datetime(2026, 11, 2), datetime.datetime(2026, 11, 27), "29.10.2026", "87001234567"],
            ["Аскерұлы Есбер", "Robotics 1", "2 этаж", "Dana Kurak", "Вт, Пт 16:30–18:30", "01.10.2026", "31.10.2026", "", ""],
            ["Иван Петров", "Music 1", "", "", "", "", "", "", ""],        # no patronymic, unique -> matched
            ["Айгерим Сапарова", "Film 1", "", "", "", "", "", "", ""],    # exact name wins over the longer one
            ["Красный Ученик", "Design 1", "", "", "", "", "", "", ""],    # inactive -> not attached
            ["Неизвестный Ученик", "3D 1", "", "", "", "", "", "", ""],
            [None, None, None, None, None, None, None, None, None]]})
        students, _ = sts.parse(sts.read_tables(master))
        rows = sts.read_workshop_rows(workshops)
        self.assertEqual(len(rows), 6)
        unmatched = sts.attach_workshops(students, rows)
        by_name = {s[0]: s for s in students}
        self.assertEqual(by_name["Аскерұлы Есбер"][9], [
            ["Robotics 1", "2 этаж", "Dana Kurak", "Вт, Пт 16:30–18:30", "2026-10-01", "2026-10-31", ""],
            ["Game Development 2", "3 этаж, 5 WR", "Akhmet", "Вт, Пт 16:30–18:30", "2026-11-02", "2026-11-27", "2026-10-29"],
        ])  # sorted by start date; coach stored like master-sheet coaches; the phone column is never read
        self.assertNotIn("87001234567", repr(students))
        self.assertEqual([w[0] for w in by_name["Иван Петров Сергеевич"][9]], ["Music 1"])
        self.assertEqual([w[0] for w in by_name["Айгерим Сапарова"][9]], ["Film 1"])
        self.assertEqual(by_name["Айгерим Сапарова Ерлановна"][9], [])
        self.assertEqual(by_name["Красный Ученик"][9], [])
        self.assertEqual([w["title"] for w in unmatched], ["Design 1", "3D 1"])
        # the master sheet's own «Воркшопы» tab is read too; no such tab / CSV -> nothing
        self.assertEqual(sts.read_workshop_rows(master, sts.WORKSHOP_TAB_RE), [])
        self.assertEqual(sts.read_workshop_rows(b"a,b\n1,2\n"), [])

    def test_workshop_leader_header_is_the_coach(self):
        workshops = xlsx({"3d-modeling": [
            ["ФИО ученика", "Почта TUMO", "Воркшоп", "Кабинет / Зона", "Workshop Leader", "Дни и время"],
            ["Иван Петров", None, "3D-моделирование I", "3 этаж, WR 5", "Rizakhmet", "Пн, Чт 10:30–12:30"]]})
        [row_] = sts.read_workshop_rows(workshops)
        self.assertEqual((row_["title"], row_["room"], row_["leader"]), ("3D-моделирование I", "3 этаж, WR 5", "Rizakhmet"))

    def test_group_title_rows_are_skipped(self):
        # «Workshops 26.10» has one merged title row per group under the header
        workshops = xlsx({"3d-modeling": [
            ["ФИО ученика", "Почта TUMO", "Воркшоп", "Кабинет / Зона", "Workshop Leader", "Дни и время"],
            ["3D-моделирование I, Пн и Чт 10:30–12:30"],
            ["Иван Петров", None, "3D-моделирование I", "3 этаж, WR 5", "Rizakhmet", "Пн, Чт 10:30–12:30"],
            ["3D-моделирование I, Пн и Чт 14:30–16:30"],
            ["Анна Смирнова", None, "3D-моделирование I", "3 этаж, WR 5", "Rizakhmet", "Пн, Чт 14:30–16:30"]]})
        self.assertEqual([r["name"] for r in sts.read_workshop_rows(workshops)], ["Иван Петров", "Анна Смирнова"])

    def test_platform_export_is_the_source_of_truth(self):
        # «Лист3»: the TUMO platform export (one row per student, matched by TumoEmail) + «Кабинеты и лидеры»
        hdr = ["Location", "Year", "Month", "StartDate", "Workshop", "WorkshopSchedule", "StudentSchedule",
               "AppliedStatus", "TumoEmail", "TumoID", "Attendance", "PassStatus", "Star", "WithdrawDate", "Comment",
               "CoachName"]
        row_ = lambda ws, sched, email, coach, passed="null", withdraw="null": [  # noqa: E731
            "Astana", "2026", "November", "Oct 27, 2026", ws, sched, "Friday 14:30", "Approved", email, "260210000001",
            "", passed, "false", withdraw, "null", coach]
        workshops = xlsx({
            "Лист3": [hdr,
                      row_("3D Modeling I", "Tuesday 14:30", "ivan.petrov@tumo.world", "Almas Musalimov"),  # by email
                      row_("Music I", "Monday 16:30", "sagat.nuraly@tumo.world", "Aruzhan Khamzina"),       # by name in it
                      row_("Robotics I", "Tuesday 10:30", "ailana.s@tumo.world", "Nuray Ergazyeva"),        # initial + coach
                      row_("Robotics I", "Tuesday 10:30", "left.one@tumo.world", "Almas", passed="Withdrawn"),
                      row_("", "Tuesday 14:30", "no.title@tumo.world", "Almas Musalimov")],
            "Кабинеты и лидеры": [["Workshop", "На карточке", "Кабинет / Зона", "Workshop Leader"],
                                  ["3D Modeling I", "3D-моделирование I", "3 этаж, WR 5", "Даулетбай Ризахмет"]],
            "3d-modeling": [["ФИО ученика", "Воркшоп"], ["Иван Петров", "Old tab is ignored"]]})
        rows, info = sts.read_platform_export(workshops)
        self.assertEqual(info["3d modeling i"], ("3D-моделирование I", "3 этаж, WR 5", "Даулетбай Ризахмет"))
        self.assertEqual([r["email"] for r in rows],
                         ["ivan.petrov@tumo.world", "sagat.nuraly@tumo.world", "ailana.s@tumo.world", "no.title@tumo.world"])
        self.assertEqual({k: rows[0][k] for k in ("title", "room", "leader", "time", "start", "end")},
                         {"title": "3D-моделирование I", "room": "3 этаж, WR 5", "leader": "Даулетбай Ризахмет",
                          "time": "Вт, Пт 14:30–16:30", "start": "2026-10-27", "end": "2026-11-22"})
        self.assertEqual((rows[1]["title"], rows[1]["time"], rows[1]["room"]), ("Music I", "Пн, Чт 16:30–18:30", ""))
        rec = lambda name, email="", coach="Almas": [name, "Вторник", "14:30-16:30", coach, coach, "Самообучение", email, "", "", []]  # noqa: E731
        students = [rec("Петров Иван Сергеевич", "ivan.petrov@tumo.world"), rec("Сағат Нұралы Етболатұлы"),
                    rec("Салханова Айлана Ерхатовна", coach="Nurai"), rec("Сагиранова Айлана Адлетовна", coach="Alen")]
        unmatched = sts.attach_workshops(students, [r for r in rows if r["title"]])
        self.assertEqual(unmatched, [])
        self.assertEqual([s[9][0][0] if s[9] else None for s in students],
                         ["3D-моделирование I", "Music I", "Robotics I", None])

    def test_email_name_matching(self):
        fits = lambda e, n: sts._email_fits(sts._email_parts(e), n)  # noqa: E731
        self.assertTrue(fits("yersultan.y@tumo.world", "Есенғали Ерсұлтан Қамбарұлы"))
        self.assertTrue(fits("diarali.nurgaliyev@tumo.world", "Нургалиев Диар Али Жеңісұлы"))
        self.assertTrue(fits("abu_muslim.aman@tumo.world", "Абу-Муслим Аман Серикұлы"))
        self.assertTrue(fits("belonosov.artyom@tumo.world", "Белоносов Артём Александрович"))
        self.assertTrue(fits("mariyam.y@tumo.world", "Мариям Есентай"))
        self.assertTrue(fits("alikhan.yntalbek1@tumo.world", "Ынталбек Алихан Қанатұлы"))
        self.assertFalse(fits("yuliana.pak@tumo.world", "Кабарова Нурай Ануаровна"))
        self.assertEqual(sts._email_parts("a.b@tumo.world"), [])
        # the master sheet has someone else's email on a student: the name in the email wins
        a = ["Кабарова Нурай Ануаровна", "", "", "Aruzhan", "", "Самообучение", "yuliana.pak@tumo.world", "", "", []]
        b = ["Пак Юлиана Владимировна", "", "", "Aruzhan", "", "Самообучение", "", "", "", []]
        w = {"where": "[x]", "name": "", "email": "yuliana.pak@tumo.world", "coach": "Aruzhan Khamzina", "title": "Film",
             "room": "", "leader": "", "time": "", "start": "", "end": "", "changed": ""}
        sts.attach_workshops([a, b], [w])
        self.assertEqual((a[9], b[9][0][0]), ([], "Film"))
        self.assertIn("Кабарова", w["note"])

    def test_upcoming_keeps_each_students_next_workshop_with_its_activities(self):
        import datetime
        hdr = ["Full Name", "Schedule", "Workshop", "Start Date", "Activity", "Activity Status", "Reject Count",
               "Last Submission Date", "Tumo Email", "Link"]
        r = lambda name, ws, start, act, st, email, sched="Thursday 14:30": [  # noqa: E731
            name, sched, ws, start, act, st, "", "", email, "https://360.ast.tumo.world/reg/view?id=x"]
        raw = xlsx({"Upcoming": [hdr,
            r("Ivan Petrov", "Programming I", "Nov 23, 2026", "JS Basics", "Awarded", "ivan.petrov@tumo.world"),
            r("Ivan Petrov", "Programming I", "Nov 23, 2026", "JS Math", "Not Opened", "ivan.petrov@tumo.world"),
            r("Ivan Petrov", "Robotics II", "Feb 8, 2027", "Bananas", "Working", "ivan.petrov@tumo.world"),
            r("Ivan Petrov", "Music I", "Oct 26, 2026", "Old", "Awarded", "ivan.petrov@tumo.world"),   # started
            r("Aigerim Saparova", "Music I", "Nov 24, 2026", "Beats", "Pending", "a.saparova@tumo.world"),
            r("Diana Zhambulova", "Music I", "Nov 24, 2026", "Beats", "Rejected", "diana.zhambulova@tumo.world"),
            r("Later Student", "Music I", "Jan 11, 2027", "Beats", "Awarded", "later.student@tumo.world")]})
        info = {"programming i": ("Программирование I", "3 этаж, WR 14", "Ахметова Дана")}
        up = sts.read_upcoming(raw, info, today=datetime.date(2026, 11, 2))
        ivan = next(w for w in up if w["email"] == "ivan.petrov@tumo.world")
        self.assertEqual({k: ivan[k] for k in ("title", "room", "time", "start", "end", "activities")},
                         {"title": "Программирование I", "room": "3 этаж, WR 14", "time": "Пн, Чт 14:30–16:30",
                          "start": "2026-11-23", "end": "2026-12-20",
                          "activities": [["JS Basics", "Awarded"], ["JS Math", "Not Opened"]]})
        self.assertNotIn("360.ast", repr(up))  # the link is never kept
        self.assertNotIn("later.student@tumo.world", [w["email"] for w in up])  # only the next cycle (23–24.11)
        rec = lambda name, email="": [name, "Вторник", "14:30-16:30", "Almas", "", "Самообучение", email, "", "", []]  # noqa: E731
        students = [rec("Петров Иван Сергеевич", "ivan.petrov@tumo.world"), rec("Сапарова Айгерим Ерлановна"),
                    rec("Сапарова Аяна Джамбуловна")]
        unmatched = sts.attach_workshops(students, up)
        self.assertEqual([s[9][0][7] if s[9] else None for s in students],
                         [[["JS Basics", "Awarded"], ["JS Math", "Not Opened"]], [["Beats", "Pending"]], None])
        self.assertEqual([w["email"] for w in unmatched], ["diana.zhambulova@tumo.world"])  # not her patronymic

    def test_a_student_found_by_email_is_not_claimed_by_another_email(self):
        rec = lambda name, email: [name, "", "", "Aruzhan", "", "Самообучение", email, "", "", []]  # noqa: E731
        amir = rec("Алибаев Амир Нурболұлы", "alibaev.amir@tumo.world")
        row = lambda email: {"where": "[x]", "name": "", "email": email, "coach": "", "title": email, "room": "",  # noqa: E731
                             "leader": "", "time": "", "start": "", "end": "", "changed": ""}
        unmatched = sts.attach_workshops([amir], [row("alibaev.amir@tumo.world"), row("amira.alibaeva@tumo.world")])
        self.assertEqual([w[0] for w in amir[9]], ["alibaev.amir@tumo.world"])
        self.assertEqual([w["email"] for w in unmatched], ["amira.alibaeva@tumo.world"])

    def test_stream_4_students_with_an_sl_day_move_to_self_learning(self):
        hdr = ["", "Номер родителя", "почта родителя", "ФИО ребенка", "Номер ребенка", "ДР ребенка", "Расписание",
               "День SL", None, "Коуч ", None, "Зона обучения", "Почта тумо"]
        sub = [None] * 7 + ["Понедельник\nВторник", "Четверг\nПятница"] + [None] * 4
        r = lambda name, sched, first, second: [None, "", "", name, "", "", sched, first, second, "Ayaulym", None,  # noqa: E731
                                               "3 этаж, 7 WR", ""]
        tab = [hdr, sub, ["Понедельник, Четверг : 10:30–12:30"] + [None] * 12,
               r("Иван Петров", "Понедельник, Четверг : 10:30–12:30", True, None),
               r("Анна Смирнова", "Вторник, Пятница : 14:30–16:30", None, True),
               r("Без Дня", "Вторник, Пятница : 16:30–18:30", None, None),
               r("Оба Дня", "Понедельник, Четверг : 10:30–12:30", True, True),
               r("Текстом Записан", "Понедельник, Четверг : 10:30–12:30", "Понедельник", None)]
        students, problems = sts.parse([("4 поток", tab)])
        got = {s[0]: (s[1], s[2], s[5]) for s in students}
        self.assertEqual(got["Иван Петров"], ("Понедельник", "10:30-12:30", "Самообучение"))
        self.assertEqual(got["Анна Смирнова"], ("Пятница", "14:30-16:30", "Самообучение"))
        self.assertEqual(got["Без Дня"][2], "Онбординг")
        self.assertEqual(got["Оба Дня"][2], "Онбординг")
        self.assertEqual(got["Текстом Записан"], ("Понедельник", "10:30-12:30", "Самообучение"))
        self.assertTrue(any("оба дня SL" in p for p in problems))

    def test_workshops_survive_save_and_load(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "students.json"
            ws = [["Game Development 2", "3 этаж", "Ахмет", "Вт, Пт 16:30–18:30", "2026-11-02", "2026-11-27", ""]]
            sts.save_student_data([["Иван Петров", "Вторник", "10:30-12:30", "Almas", "", "Самообучение", "", "", "", ws]], path)
            self.assertEqual(sts.load_student_data(path)[0][9], ws)

    def test_html_login_page_is_rejected(self):
        with self.assertRaises(SystemExit):
            sts.read_tables(b"<!DOCTYPE html><html>Sign in</html>")


if __name__ == "__main__":
    unittest.main()
