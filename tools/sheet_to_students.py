#!/usr/bin/env python3
"""Build data/students.json from the master student spreadsheet
("MAIN_ОБЩИЙ_1,2,3 БАТЧ_ВСЕХ_УЧЕНИКОВ_SL + ON").

The master sheet contains private data (parent/student phones, IIN, personal emails,
internal notes). Only the fields the public page needs are copied:
name, SL day, time slot, coach, ex-coach, stage and the student's @tumo.world email.

Input: the workbook as .xlsx (all schedule tabs) or a CSV export of a single tab.
  - xlsx: every tab named like "ПН ЧТ 1030" / "ВТ ПТ 1630" is read; the tab name gives the time slot.
  - csv:  the time slot is taken from "Новое расписание" or "Расписание".

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
SLOT_BY_HOUR = {"10": "10:30-12:30", "14": "14:30-16:30", "16": "16:30-18:30"}
TAB_RE = re.compile(r"^(ПН\s*ЧТ|ВТ\s*ПТ)\s*(\d{2})\d{2}$", re.I)
DAYS_BY_PAIR = {"пнчт": {"Понедельник", "Четверг"}, "втпт": {"Вторник", "Пятница"}}
TUMO_EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@tumo\.world$")

# Column header (lowercased, prefix match) -> field. Anything else in the sheet is ignored.
HEADERS = {
    "фио ученика": "name",
    "день sl": "day",
    "новый коуч sl": "coach",
    "ex-coach": "ex",
    "почта tumo": "email",
    "новое расписание": "new_schedule",
    "расписание": "schedule",
}


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


def read_tables(raw):
    """bytes -> [(tab_name or None, rows)]"""
    if raw[:2] == b"PK":
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
        return [(ws.title.strip(), list(ws.iter_rows(values_only=True)))
                for ws in wb.worksheets if TAB_RE.match(ws.title.strip())]
    text = raw.decode("utf-8-sig")
    if text.lstrip()[:1] == "<":
        raise SystemExit("Got an HTML page instead of the sheet: check the link/sharing or the credentials.")
    return [(None, list(csv.reader(io.StringIO(text))))]


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


def parse(tables, published=None):
    """-> (students, problems). published: {norm(name): row} of the current data/students.json."""
    published = published or {}
    by_key, problems = {}, []
    for tab, rows in tables:
        if not rows:
            continue
        cols = map_header(rows[0])
        if "name" not in cols or "day" not in cols:
            problems.append(f"[{tab}] нет колонок «ФИО ученика» / «День SL» — вкладка пропущена")
            continue
        m = TAB_RE.match(tab or "")
        tab_slot = SLOT_BY_HOUR.get(m.group(2)) if m else None
        pair_days = DAYS_BY_PAIR[re.sub(r"\s", "", m.group(1)).lower()] if m else set(DAYS_OK)

        def get(row, field):
            i = cols.get(field)
            return row[i] if i is not None and i < len(row) else None

        for line_no, row in enumerate(rows[1:], start=2):
            name = proper_case(get(row, "name"))
            if not name:
                continue
            where = f"[{tab or 'csv'}:{line_no}] {name}"
            day = clean_ws(get(row, "day")).capitalize()
            time = tab_slot or slot_from_text(get(row, "new_schedule")) or slot_from_text(get(row, "schedule"))
            if day not in DAYS_OK or day not in pair_days:
                problems.append(f"{where}: день SL не распознан: {day!r}")
                continue
            if not time:
                problems.append(f"{where}: время не распознано")
                continue
            email = clean_ws(get(row, "email")).lower()
            rec = [name, day, time, canon_coach(get(row, "coach")), canon_coach(get(row, "ex")), STAGE,
                   email if TUMO_EMAIL_RE.match(email) else ""]
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
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    current = load_student_data(out) if out.exists() else []
    students, problems = parse(read_tables(Path(args.source).read_bytes()), {norm(r[0]): r for r in current})
    print(f"Учеников: {len(students)}, с почтой TUMO: {sum(1 for s in students if s[6])}, проблем: {len(problems)}")
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
