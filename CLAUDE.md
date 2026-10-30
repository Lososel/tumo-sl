# TUMO Astana — self-learning schedule page

Static site (`index.html`, `js/`, `data/students.json`) deployed on Render (`render.yaml`).
`.github/workflows/sync-students.yml` rebuilds `data/students.json` from the master Google
Sheet ("MAIN_ОБЩИЙ_1,2,3 БАТЧ_ВСЕХ_УЧЕНИКОВ_SL + ON", Drive file `1qcmLsXYRvu6Pf0ghM17V0dvq3sUuBDqm`)
with `tools/sheet_to_students.py`. Tests: `python3 -m unittest discover -s tests` and
`node --test tests/*.test.js`.

## Rules for reading the master sheet

- **Row colour** (fill of the «ФИО» cell) is the student's status:
  - **red** → inactive. Card: name + «Если вы хотите продолжить обучение в TUMO, свяжитесь с
    нами через WhatsApp» + WhatsApp button.
  - **dark purple** (`#9900FF`, `#674EA7`, `#351C75`) → waitlist. Card: name + «Сейчас ваш
    аккаунт приостановлен. Ожидайте обновления информации о вашем месте в TUMO или свяжитесь с
    нами через WhatsApp» + WhatsApp button.
  - Light purples / pastels in the "N поток" tabs are room groups, not a status.
- **Notes columns** («Причина ухода», «Ушел к коучу», unlabelled ones): left (отказ, отчислен,
  ignore, self initiated, не может посещать) → inactive; paused or waitlist for a later period
  (приостановлено, ЛИСТ ОЖИДАНИЯ 2027 / лето / ноябрь, след. поток) → waitlist. «лист ожидания
  (хочет пн/чт 16:30)», «хочет на 16:30» = attends now, active.
- «Расписание» "(лист ожидания)" is the slot first requested, not a status.
- Inactive / waitlist students keep only their name in `data/students.json`.
- Schedule tabs `ПН ЧТ 1030` … `ВТ ПТ 1630`: the tab name is the time slot. `4 поток`, `5 поток`
  are onboarding (stage «Онбординг», card laid out like tumo-onb-app's).
- Never publish phones, IIN, birth dates, parent details or non-`@tumo.world` emails.
- The temporary password is only in the Render env var `TEMP_PASSWORD`, never in git.
- Self-learning cards don't show the student's TUMO email; onboarding cards do.
- Coach names are shown in Cyrillic on every card: Russian spelling on the RU page, Kazakh on
  the KZ page (`COACH_NAMES` in `index.html`; add new coaches there).
- Workshops come only from an optional «Воркшопы» tab (columns: ФИО ученика / Почта TUMO,
  Воркшоп, Кабинет, Дни и время, Дата изменения), matched by TUMO email then name. No tab = no
  workshop block. Never invent workshop data; the source of truth is the TUMO platform.

## Page features
- `?s=<id>` opens one student's card (`StudentData.studentId`: hash of the folded name).
- «Сохранить на этом устройстве» keeps ids in localStorage (`tumo-saved-students`).
- Calendar: `.ics` + Google Calendar link; SL = main day weekly, onboarding = both days.
- PWA manifest and icons live in `js/` so every build that publishes `js/` serves them.
