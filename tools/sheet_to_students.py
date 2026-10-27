#!/usr/bin/env python3
"""Build data/students.json from the master student spreadsheet
("MAIN_ОБЩИЙ_1,2,3 БАТЧ_ВСЕХ_УЧЕНИКОВ_SL + ON").

The master sheet contains private data (parent/student phones, IIN, personal emails,
internal notes). Only the fields the public page needs are copied:
name, SL day, time slot, coach, ex-coach, stage and the student's @tumo.world email.

Input: the workbook as .xlsx (all schedule tabs) or a CSV export of a single tab.
  - xlsx: every tab named like "ПН ЧТ 1030" / "ВТ ПТ 1630" is read; the tab name gives the time slot.
    Onboarding stream tabs ("4 поток", see --streams) are read too: name from «ФИО ребенка»,
    days and slot from «Расписание», coach from «Коуч», room from «Зона обучения», stage «Онбординг».
  - csv:  the time slot is taken from "Новое расписание" or "Расписание".

Inactive students are left out:
  - rows highlighted red (fill of the «ФИО ученика» cell; .xlsx only, a CSV has no colours);
  - rows whose notes/status columns («Причина ухода», «Ушел к коучу», unlabelled note
    columns...) say "ignore", "self initiated", "лист ожидания" or "отчислен".
  The «Расписание» column is not checked: "(лист ожидания)" there is the slot the family
  first asked for, not the student's current status.

Usage:
  python3 tools/sheet_to_students.py master.xlsx            # write data/students.json if changed
  python3 tools/sheet_to_students.py export.csv --dry-run   # only print the summary
Run automatically by .github/workflows/sync-students.yml.
"""
import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_schedule import (  # noqa: E402
    CYR_TO_LATIN_COACH, DAYS_OK, STUDENTS_JSON, clean_ws, load_student_data, norm, proper_case,
    save_student_data,
)

STAGE = "Самообучение"
ONBOARDING_STAGE = "Онбординг"
STREAM_TAB_RE = re.compile(r"^(\d+)\s*поток$", re.I)
DEFAULT_STREAMS = ("4",)  # onboarding stream tabs to include, by number
SLOT_BY_HOUR = {"10": "10:30-12:30", "14": "14:30-16:30", "16": "16:30-18:30"}
TAB_RE = re.compile(r"^(ПН\s*ЧТ|ВТ\s*ПТ)\s*(\d{2})\d{2}$", re.I)
DAYS_BY_PAIR = {"пнчт": {"Понедельник", "Четверг"}, "втпт": {"Вторник", "Пятница"}}
TUMO_EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@tumo\.world$")

# Notes/status columns checked for INACTIVE_RE (prefix match), plus columns with an empty header.
NOTE_HEADERS = ("причина ухода", "ушел к коучу", "ушёл к коучу", "статус", "примечан", "коммент", "status", "notes")
INACTIVE_RE = re.compile(r"ignore|self[\s-]*initiated|лист\s*ожидани|отчисл", re.I)


def is_red(color):
    """openpyxl Color -> True for red highlights (#FF0000, #E06666, #CC0000...), not for orange,
    magenta, pink or yellow. Theme colours can't be resolved without the theme and count as not red."""
    if color is None:
        return False
    rgb = None
    if color.type == "rgb" and isinstance(color.rgb, str):
        rgb = color.rgb[-6:]
    elif color.type == "indexed" and color.indexed is not None:
        from openpyxl.styles.colors import COLOR_INDEX

        if 0 <= color.indexed < len(COLOR_INDEX):
            rgb = COLOR_INDEX[color.indexed][-6:]
    if not rgb or not re.fullmatch(r"[0-9A-Fa-f]{6}", rgb):
        return False
    r, g, b = (int(rgb[i:i + 2], 16) for i in (0, 2, 4))
    return r >= 200 and g <= 115 and b <= 115 and r - max(g, b) >= 90


def red_fill(cell):
    fill = getattr(cell, "fill", None)
    if fill is None or fill.fill_type in (None, "none"):
        return False
    return is_red(fill.fgColor) or is_red(fill.start_color)


# Column header (lowercased, prefix match) -> field. Anything else in the sheet is ignored.
HEADERS = {
    "фио ученика": "name",
    "фио ребенка": "name",
    "фио ребёнка": "name",
    "день sl": "day",
    "новый коуч sl": "coach",
    "коуч": "coach",
    "ex-coach": "ex",
    "почта tumo": "email",
    "почта тумо": "email",
    "зона обучения": "room",
    "новое расписание": "new_schedule",
    "расписание": "schedule",
}


# Latin letters that look like Cyrillic ones, typed by mistake inside Cyrillic names
# ("Tөлеуғазы" with a Latin T, "Iңкар" with a Latin I). Fixed only in words that mix both scripts,
# so Latin names ("Agayeva Zakhirat") stay as they are.
LATIN_TO_CYRILLIC = str.maketrans("ABCEHIKMOPTXYabceikmopxy", "АВСЕНІКМОРТХУавсеікморху")
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")


def fix_mixed_script(name):
    return " ".join(w.translate(LATIN_TO_CYRILLIC) if CYRILLIC_RE.search(w) else w for w in name.split(" "))


def slot_from_text(text):
    m = re.search(r"(\d{1,2})[:.]\d{2}", str(text or ""))
    return SLOT_BY_HOUR.get(m.group(1).zfill(2)) if m else None


def canon_coach(raw):
    s = clean_ws(raw)
    return CYR_TO_LATIN_COACH.get(s.lower(), proper_case(s)) if s else ""


def map_header(row):
    cols = {}
    for i, cell in enumerate(row):
        h = clean_ws(cell).lower()
        for prefix, field in HEADERS.items():
            if h.startswith(prefix) and field not in cols:
                cols[field] = i
                break
    return cols


def stream_of(tab):
    m = STREAM_TAB_RE.match(tab or "")
    return m.group(1) if m else None


def read_tables(raw, streams=DEFAULT_STREAMS):
    """bytes -> [(tab_name or None, rows, red)] where red[i] says row i is highlighted red
    (its «ФИО ученика» cell, or the first cell if the tab has no such column). CSV: red is None."""
    if raw[:2] == b"PK":
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        tables = []
        for ws in wb.worksheets:
            title = ws.title.strip()
            if not (TAB_RE.match(title) or stream_of(title) in set(streams)):
                continue
            rows, red, name_col = [], [], 0
            for i, cells in enumerate(ws.iter_rows()):
                values = tuple(c.value for c in cells)
                if i == 0:
                    name_col = map_header(values).get("name", 0)
                rows.append(values)
                red.append(i > 0 and name_col < len(cells) and red_fill(cells[name_col]))
            tables.append((ws.title.strip(), rows, red))
        return tables
    text = raw.decode("utf-8-sig")
    if text.lstrip()[:1] == "<":
        raise SystemExit("Got an HTML page instead of the sheet: check the link/sharing or the credentials.")
    return [(None, list(csv.reader(io.StringIO(text))), None)]


def note_columns(header, name_col):
    """Indexes of notes/status columns: known headers, or unlabelled columns after the name."""
    cols = []
    for i, cell in enumerate(header):
        h = clean_ws(cell).lower()
        if (h and h.startswith(NOTE_HEADERS)) or (not h and i > name_col):
            cols.append(i)
    return cols


def pick_duplicate(cands, published):
    """A student listed in several tabs (usually moved between slots). Prefer, in order:
    the row whose "Новое расписание" confirms its tab slot, the row matching what is
    published now (so an ambiguous sheet doesn't flip the schedule), then the last row."""
    confirmed = [c for c in cands if c["confirmed"]]
    if len(confirmed) == 1:
        return confirmed[0]
    if published:
        same = [c for c in cands if c["rec"][1:3] == published[1:3]]
        if same:
            return same[-1]
    return cands[-1]


def parse(tables, published=None, stats=None):
    """-> (students, problems). published: {norm(name): row} of the current data/students.json.
    stats (optional dict) receives the counts of rows excluded as inactive."""
    published = published or {}
    stats = stats if stats is not None else {}
    stats.update(red=0, notes=0)
    by_key, problems = {}, []
    for table in tables:
        tab, rows = table[0], table[1]
        red = table[2] if len(table) > 2 and table[2] else [False] * len(rows)
        if not rows:
            continue
        cols = map_header(rows[0])
        onboarding = stream_of(tab) is not None
        if "name" not in cols or ("schedule" if onboarding else "day") not in cols:
            problems.append(f"[{tab}] нет колонок «ФИО» / «{'Расписание' if onboarding else 'День SL'}» — вкладка пропущена")
            continue
        notes = note_columns(rows[0], cols["name"])
        m = TAB_RE.match(tab or "")
        tab_slot = SLOT_BY_HOUR.get(m.group(2)) if m else None
        pair_days = DAYS_BY_PAIR[re.sub(r"\s", "", m.group(1)).lower()] if m else set(DAYS_OK)

        def get(row, field):
            i = cols.get(field)
            return row[i] if i is not None and i < len(row) else None

        for line_no, row in enumerate(rows[1:], start=2):
            name = proper_case(fix_mixed_script(clean_ws(get(row, "name"))))
            if not name:
                continue
            if red[line_no - 1]:
                stats["red"] += 1
                continue
            if any(i < len(row) and row[i] and INACTIVE_RE.search(str(row[i])) for i in notes):
                stats["notes"] += 1
                continue
            where = f"[{tab or 'csv'}:{line_no}] {name}"
            if onboarding:
                # «Понедельник, Четверг : 10:30–12:30»: the pair's first day stands for the pair
                # (onboarding has no main SL day yet); the slot comes from the start time.
                sched = clean_ws(get(row, "schedule")).lower()
                day = "Понедельник" if "понедельник" in sched or "четверг" in sched else (
                      "Вторник" if "вторник" in sched or "пятница" in sched else sched.capitalize())
                pair_days = set(DAYS_OK)
            else:
                day = clean_ws(get(row, "day")).capitalize()
            time = tab_slot or slot_from_text(get(row, "new_schedule")) or slot_from_text(get(row, "schedule"))
            if day not in DAYS_OK or day not in pair_days:
                problems.append(f"{where}: день SL не распознан: {day!r}")
                continue
            if not time:
                problems.append(f"{where}: время не распознано")
                continue
            email = clean_ws(get(row, "email")).lower()
            rec = [name, day, time, canon_coach(get(row, "coach")), canon_coach(get(row, "ex")),
                   ONBOARDING_STAGE if onboarding else STAGE,
                   email if TUMO_EMAIL_RE.match(email) else "", clean_ws(get(row, "room"))]
            confirmed = bool(tab_slot) and slot_from_text(get(row, "new_schedule")) == tab_slot
            by_key.setdefault(norm(name), []).append({"rec": rec, "where": where, "confirmed": confirmed})

    students = []
    for key, cands in by_key.items():
        if len({tuple(c["rec"]) for c in cands}) > 1:
            chosen = pick_duplicate(cands, published.get(key))
            problems.append(f"{chosen['where']}: ученик есть в нескольких строках ("
                            + "; ".join(c["where"].split("]")[0] + "]" for c in cands)
                            + f") — выбрано {chosen['rec'][1]} {chosen['rec'][2]}")
            students.append(chosen["rec"])
        else:
            students.append(cands[0]["rec"])
    return students, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="Downloaded master sheet (.xlsx or .csv)")
    ap.add_argument("--out", default=str(STUDENTS_JSON))
    ap.add_argument("--min-students", type=int, default=200,
                    help="Refuse to write if fewer students were parsed (protects against a broken download)")
    ap.add_argument("--max-drop", type=float, default=0.2,
                    help="Refuse to write if the student count falls by more than this share "
                         "(e.g. a single-tab CSV instead of the whole workbook)")
    ap.add_argument("--streams", default=",".join(DEFAULT_STREAMS),
                    help='Onboarding stream tabs to include, e.g. "4" or "4,5" (default: %(default)s)')
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    current = load_student_data(out) if out.exists() else []
    stats = {}
    streams = tuple(s.strip() for s in args.streams.split(",") if s.strip())
    students, problems = parse(read_tables(Path(args.source).read_bytes(), streams),
                               {norm(r[0]): r for r in current}, stats)
    onboarding = sum(1 for s in students if s[5] == ONBOARDING_STAGE)
    print(f"Учеников: {len(students)} (самообучение: {len(students) - onboarding}, онбординг: {onboarding}), "
          f"с почтой TUMO: {sum(1 for s in students if s[6])}, проблем: {len(problems)}")
    print(f"Исключено как неактивные: {stats['red'] + stats['notes']} строк — "
          f"красная заливка: {stats['red']}, отметка в примечаниях: {stats['notes']}")
    for p in problems:
        print("  " + p)
    if len(students) < args.min_students:
        raise SystemExit(f"Слишком мало учеников ({len(students)} < {args.min_students}) — файл не записан.")

    if current and len(students) < len(current) * (1 - args.max_drop):
        raise SystemExit(f"Учеников стало {len(students)} вместо {len(current)} (> {args.max_drop:.0%} меньше) — "
                         "файл не записан. Проверьте, что выгружается вся книга, а не одна вкладка, "
                         "или запустите с --max-drop 1.")
    if current == students:
        print("Без изменений.")
        return
    if args.dry_run:
        print("Dry-run: файл не записан.")
        return
    save_student_data(students, out)
    print(f"Записано: {out}")


if __name__ == "__main__":
    main()
