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
- **«4 поток» → self-learning (temporary, until those students are moved into the main tabs):** its «День SL»
  is two tick columns sub-headed «Понедельник / Вторник» and «Четверг / Пятница». One tick + the pair in
  «Расписание» = the SL day (e.g. «Вторник, Пятница» + second tick = Пятница); the student becomes stage
  «Самообучение» with the SL card. No tick → still «Онбординг»; both ticks → «Онбординг» + a log line. With no
  ex-coach the SL card shows the badge «самообучение» and no «Коуч остался прежним» note.
  Coach: «Новый коуч» («X Support if needed» = X only helps, the coach stays the onboarding coach;
  a «Support must» note is dropped from the name; «Aruzhan Kh» = Аружан Хамзина) with «Eх-Коуч OB» (the onboarding coach) as ex-coach → badge «новый коуч»; no «Новый коуч» →
  the onboarding coach, no ex-coach.
- Never publish phones, IIN, birth dates, parent details or non-`@tumo.world` emails.
- The temporary password is only in the Render env var `TEMP_PASSWORD`, never in git.
- Self-learning cards don't show the student's TUMO email; onboarding cards do.
- Coach names are shown in Cyrillic on every card: Russian spelling on the RU page, Kazakh on
  the KZ page (`COACH_NAMES` in `index.html`; add new coaches there).
- **Workshops: the platform export («Лист3» in «Workshops 26.10») is the one source of truth.** Found by its
  columns (TumoEmail, Workshop, WorkshopSchedule, StartDate, PassStatus, WithdrawDate, CoachName…); when
  it is there, the hand-filled tabs («3d-modeling»…) are ignored. Withdrawn rows are skipped; rows with an
  empty Workshop are skipped and logged. Matched by TumoEmail; if the email isn't in the master sheet (or
  the master sheet has it on someone whose name doesn't fit), by the name in the email
  (`match_by_email_name`: spelling-insensitive, initials, SL coach to break ties; only a single fit).
  «WorkshopSchedule» «Tuesday 14:30» → «Вт, Пт 14:30–16:30»; the period ends on the Sunday of the 4th week.
  Title on the card, room and leader per workshop come from the tab «Кабинеты и лидеры»
  (Workshop | На карточке | Кабинет / Зона | Workshop Leader); no title there → the export's English name.
- **Every** export tab in «Workshops 26.10» is read («Лист3» = the running cycle, «Записи 23.11» = the next cycle's
  enrollments): rows that have started are the current workshop, rows starting after today are the next one.
  When a next-cycle enrollment exists it is the «Следующий воркшоп»; «Upcoming» then only adds the activities
  for the same student and workshop. Only without enrollments is «Upcoming»'s own plan used.
- **Upcoming workshops: the «Upcoming» tab** (platform export: Full Name | Schedule | Workshop | Start Date |
  Activity | Activity Status | Reject Count | Last Submission Date | Tumo Email | Link; one row per student per
  prerequisite activity, the plan through the year). The sync keeps only the next cycle — workshops starting in the
  week of the earliest start date after today (23–24.11), nothing later (`read_upcoming`) — with its activities as an 8th element `[[activity, status]]` of the workshop entry;
  the card's «Следующий воркшоп» shows «Задания к воркшопу · выполнено N из 3» with RU/KZ status chips
  (Awarded/Working/Pending/Rejected/Not Opened). Matched like «Лист3» (email, name in the email, then the Latin
  Full Name). The Link column is never published. Matching rules: a student found by their own email can't be
  claimed by another email's name; patronymics don't count; a student with another master-sheet email needs
  the same SL coach.
- Older layout (used only without the export): the workshop sheet «Workshops 26.10» (Drive file
  `1E1L3mJdGASq0hkV83i5knWpXgmWNF8eO1e7HBiAcIYE`, workflow var `WORKSHOP_SHEET_FILE_ID`) and/or a
  «Воркшопы» tab in the master sheet. Header row: ФИО ученика | Почта TUMO (optional) | Воркшоп |
  Кабинет / Зона | Workshop Leader (or «Лидер воркшопа» / «Коуч») | Дни и время | Дата начала | Дата окончания | Дата изменения. One row per
  student per workshop. The header must stay in row 1; a group title row (text only in column A,
  «Воркшоп» empty) is skipped. Matched by full name (email wins; a name without patronymic only if
  unique). Stored as field 9 `workshops` = [[title, room, leader, time, start, end, changed]].
  The instructor is the «Воркшоп лидер» (KZ «Воркшоп лидері»), never «коуч» (that's the SL coach).
  Never invent workshop data; the source of truth is the TUMO platform.
- The 9 workshops and their leaders (one leader per workshop):
  | Workshop | Воркшоп лидер | Email |
  |---|---|---|
  | Music | Жананов Нурасыл | nurassyl.zhananov@tumo.center |
  | Animation | Мырзахмет Аружан Болатқызы | aruzhan.myrzakhmet@tumo.center |
  | Graphic Design | Алханова Райхан Абылханқызы | alkhanova.raikhan@tumo.center |
  | Motion Graphics | Санакбеков Алишер Базарбекович | sanakbekov.alisher@tumo.center |
  | Game Dev | Ертаев Рамазан | ramazan.yertayev@tumo.center |
  | Filmmaking | Жүнісбек Марғұлан Серікқалиұлы | margulan.zhunisbek@tumo.center |
  | 3D (3D-моделирование) | Даулетбай Ризахмет Абилжанович («Rizakhmet» in the sheet) | rizahmet.dauletbay@tumo.center |
  | Robotics | Бердиходжаев Адилбек Сайлауович | berdikhodzhaev.adilbek@tumo.center |
  | Programming | Ахметова Дана Саятовна | akhmetova.dana@tumo.center |
  A workshop row's «Workshop Leader» should be the leader of that workshop; if it's empty, ask
  rather than guess.
  The workshop block shows the leader's email (`WORKSHOP_LEADERS` in `js/student-data.js`, matched by
  surname or first name, Cyrillic or Latin); add a new leader there.
- Card: «Текущий воркшоп» (running today) and «Следующий воркшоп» (earliest not started);
  alert + badge when the next one starts within 14 days or one changed in the last 14 days.
- A workshop lasts one month (no end date → start + 1 month). Dates shown as the first–last
  session, e.g. «26 октября – 19 ноября» for Пн/Чт 26.10–22.11.
- While a workshop runs (computed in the browser for today): it is the first, highlighted block;
  «Этап обучения» = «Воркшоп»; the SL schedule and main day are hidden and one banner says «Сейчас вы
  посещаете только воркшоп. Самообучение возобновится с <date>.»; no «Коуч остался прежним» note.

## Page features
- `?s=<id>` opens one student's card (`StudentData.studentId`: hash of the folded name).
- «Сохранить на этом устройстве» keeps ids in localStorage (`tumo-saved-students`).
- «Добавить в Google Календарь» (calendar SVG icon, no emoji): inside each workshop block (that workshop, weekly until its end) and
  in the card footer for the class (SL = main day weekly, onboarding = both days; hidden while a
  workshop runs). Copy link and save are icon buttons next to
  the name. (`buildIcs` stays in `js/student-data.js` but has no button.)
- PWA manifest and icons live in `js/` so every build that publishes `js/` serves them.
