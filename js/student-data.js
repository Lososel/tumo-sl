/* Student data loading for the self-learning schedule page.
 *
 * The page no longer embeds the student list. It is fetched at runtime from
 * one or more sources (first that succeeds wins):
 *   - a Google Sheets "Publish to web" CSV link (optional, see index.html), or
 *   - data/students.json in this repo (written by tools/sync_schedule.py).
 * Records are normalised to {n, d, t, c, ex, stage, email} with names in Title Case.
 *
 * Works both in the browser (window.StudentData) and in Node (module.exports) for tests.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.StudentData = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DEFAULT_STAGE = 'Самообучение';
  const TIME_SLOTS = ['10:30-12:30', '14:30-16:30', '16:30-18:30'];

  // "БАТЫРЖАН НҰРАЛИ АМАНГЕЛДІҰЛЫ" -> "Батыржан Нұрали Амангелдіұлы".
  // Same rule as titleCase() in the onboarding app: every word (also after "-", an apostrophe,
  // "(" or "+") gets a capital first letter, the rest lowercase.
  function properCase(value) {
    const s = (value == null ? '' : String(value)).replace(/\s+/g, ' ').trim().toLowerCase();
    return s.replace(/(^|[\s\-‐'’ʼ(+])(\p{L})/gu, (m, sep, ch) => sep + ch.toUpperCase());
  }

  // ---------- coach names (ported 1:1 from tumo-onb-app frontend/src/coaches.ts) ----------
  // The sheet has Latin names ("Nazym", "Dana Akhmetova"); the onboarding card shows them in
  // Cyrillic: Russian spelling on the RU page, Kazakh on the KZ page. Unknown words are
  // transliterated by rule; Cyrillic names are left as they are.
  const COACH_KNOWN = {
    akbota: { ru: 'Акбота', kk: 'Ақбота' }, akhmet: { ru: 'Ахмет', kk: 'Ахмет' },
    akhmetova: { ru: 'Ахметова', kk: 'Ахметова' }, aigerim: { ru: 'Айгерим', kk: 'Әйгерім' },
    aizhan: { ru: 'Айжан', kk: 'Айжан' }, alinur: { ru: 'Алинур', kk: 'Әлінұр' },
    aliya: { ru: 'Алия', kk: 'Әлия' }, almas: { ru: 'Алмас', kk: 'Алмас' },
    arman: { ru: 'Арман', kk: 'Арман' }, aruzhan: { ru: 'Аружан', kk: 'Аружан' },
    asel: { ru: 'Асель', kk: 'Әсел' }, dana: { ru: 'Дана', kk: 'Дана' },
    dinara: { ru: 'Динара', kk: 'Динара' }, elmira: { ru: 'Эльмира', kk: 'Эльмира' },
    gulim: { ru: 'Гулим', kk: 'Гүлім' }, madina: { ru: 'Мадина', kk: 'Мадина' },
    moldir: { ru: 'Мольдир', kk: 'Мөлдір' }, nazym: { ru: 'Назым', kk: 'Назым' },
    samat: { ru: 'Самат', kk: 'Самат' }, telzhan: { ru: 'Тельжан', kk: 'Телжан' }
  };
  const TR_DIGRAPHS = [['shch', 'щ'], ['zh', 'ж'], ['kh', 'х'], ['sh', 'ш'], ['ch', 'ч'], ['ts', 'ц'],
                       ['ya', 'я'], ['yu', 'ю'], ['yo', 'ё'], ['ye', 'е']];
  const TR_LETTERS = { a: 'а', b: 'б', c: 'к', d: 'д', e: 'е', f: 'ф', g: 'г', h: 'х', i: 'и', j: 'дж', k: 'к',
                       l: 'л', m: 'м', n: 'н', o: 'о', p: 'п', q: 'к', r: 'р', s: 'с', t: 'т', u: 'у', v: 'в',
                       w: 'у', x: 'кс', z: 'з' };

  function transliterate(word) {
    const w = word.toLowerCase();
    let out = '';
    for (let i = 0; i < w.length;) {
      const di = TR_DIGRAPHS.find(([lat]) => w.startsWith(lat, i));
      if (di) { out += di[1]; i += di[0].length; continue; }
      const ch = w[i];
      const prevOut = out.slice(-1);
      if (ch === 'e' && i === 0) out += 'э'; // Elnur -> Элнур: initial E
      // "i" after a vowel and before a consonant/end is a glide: Aibek -> Айбек
      else if (ch === 'i' && 'аеоуэ'.includes(prevOut) && !'aeou'.includes(w[i + 1] || '-')) out += 'й';
      // "y" is ы after a consonant or й, a glide (й) after a vowel: Nurym -> Нурым
      else if (ch === 'y') out += 'аеоуэ'.includes(prevOut) && prevOut !== '' ? 'й' : 'ы';
      else out += TR_LETTERS[ch] || ch;
      i += 1;
    }
    return out.charAt(0).toUpperCase() + out.slice(1);
  }

  // coachName('Dana Akhmetova', 'ru') -> 'Дана Ахметова'; lang: 'ru' | 'kk'
  function coachName(name, lang) {
    if (!name) return name;
    const loc = lang === 'ru' ? 'ru' : 'kk';
    return properCase(String(name).replace(/[A-Za-z]+/g,
      word => (COACH_KNOWN[word.toLowerCase()] || {})[loc] || transliterate(word)));
  }

  // ---------- share links, calendar ----------

  // Stable short id of a student for share links (?s=…): FNV-1a of the folded name, so it
  // survives re-syncs and spelling variants (Kazakh/Russian letters, case, extra spaces).
  function studentId(name) {
    const key = words(name).map(fold).join(' ');
    let h = 0x811c9dc5;
    for (const byte of new TextEncoder().encode(key)) {
      h ^= byte;
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h.toString(36).padStart(7, '0');
  }

  const DAY_CODES = { 'понедельник': 'MO', 'вторник': 'TU', 'среда': 'WE', 'четверг': 'TH', 'пятница': 'FR', 'суббота': 'SA', 'воскресенье': 'SU' };
  const DAY_ALIASES = [ // prefixes, Russian / Kazakh / short forms
    [/^(понед|пн|дүйс|дс)/, 'MO'], [/^(вторн|вт|сейс|сс)/, 'TU'], [/^(сред|ср|сәрс)/, 'WE'],
    [/^(четв|чт|бейс|бс)/, 'TH'], [/^(пятн|пт|жұма|жм)/, 'FR'], [/^(субб|сб|сенб)/, 'SA']];
  const PAIRS = { MO: ['MO', 'TH'], TH: ['MO', 'TH'], TU: ['TU', 'FR'], FR: ['TU', 'FR'] };

  // "Вторник, Пятница : 16:30–18:30", "Вт/Пт 16:30-18:30", "ср 15.00" -> {days:['TU','FR'], start:'16:30', end:'18:30'}
  function parseScheduleText(text) {
    const s = String(text || '').toLowerCase();
    const times = s.match(/\d{1,2}[:.]\d{2}/g) || [];
    const days = [];
    for (const w of s.split(/[^а-яёәғқңөұүһі]+/)) {
      const hit = DAY_ALIASES.find(([re]) => w && re.test(w));
      if (hit && !days.includes(hit[1])) days.push(hit[1]);
    }
    if (!days.length || !times.length) return null;
    const norm = t => t.replace('.', ':').padStart(5, '0');
    const start = norm(times[0]);
    const end = times[1] ? norm(times[1]) : `${String(+start.slice(0, 2) + 2).padStart(2, '0')}${start.slice(2)}`;
    return { days, start, end };
  }

  // The regular class: self-learning = the main SL day once a week; onboarding = both days of the pair.
  function classSchedule(rec) {
    const code = DAY_CODES[String(rec.d || '').toLowerCase()];
    const m = /^(\d{2}:\d{2})-(\d{2}:\d{2})$/.exec(rec.t || '');
    if (!code || !m) return null;
    return { days: rec.stage === 'Онбординг' ? PAIRS[code] || [code] : [code], start: m[1], end: m[2] };
  }

  const pad2 = n => String(n).padStart(2, '0');
  const ymd = d => `${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}`;
  const CODE_INDEX = { SU: 0, MO: 1, TU: 2, WE: 3, TH: 4, FR: 5, SA: 6 };

  // First date on/after `now` that falls on one of the schedule's days.
  function firstDate(days, now) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    for (let i = 0; i < 7; i++, d.setDate(d.getDate() + 1)) {
      if (days.some(c => CODE_INDEX[c] === d.getDay())) return new Date(d);
    }
    return d;
  }

  const icsText = s => String(s || '').replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');

  // RFC 5545 line folding at 75 octets (Cyrillic is 2 bytes per letter in UTF-8).
  function foldLine(line) {
    const enc = new TextEncoder();
    const out = [];
    let cur = '', size = 0;
    for (const ch of line) {
      const n = enc.encode(ch).length;
      if (size + n > (out.length ? 74 : 75)) {
        // don't separate an escape ("\\,") from its backslash: some calendar apps choke on it
        const carry = cur.endsWith('\\') ? '\\' : '';
        out.push(carry ? cur.slice(0, -1) : cur); cur = carry; size = carry.length;
      }
      cur += ch; size += n;
    }
    out.push(cur);
    return out.join('\r\n ');
  }

  // .ics with weekly recurring events (Asia/Almaty, 1 h reminder): the regular class and, if
  // known and parseable, the workshop. opts: {now, location, classTitle, workshopTitle}
  function buildIcs(rec, opts) {
    const now = opts.now || new Date();
    const stamp = now.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
    const id = studentId(rec.n);
    const events = [];
    const add = (uid, title, sched, location, range) => {
      const day = firstDate(sched.days, (range && range.from) || now);
      const t = s => s.replace(':', '') + '00';
      // until the workshop's last day, 23:59 Almaty = 18:59 UTC
      const until = range && range.until ? `;UNTIL=${ymd(range.until)}T185959Z` : '';
      events.push(['BEGIN:VEVENT', `UID:${uid}-${id}@tumo-astana-sl`, `DTSTAMP:${stamp}`,
        `DTSTART;TZID=Asia/Almaty:${ymd(day)}T${t(sched.start)}`, `DTEND;TZID=Asia/Almaty:${ymd(day)}T${t(sched.end)}`,
        `RRULE:FREQ=WEEKLY;BYDAY=${sched.days.join(',')}${until}`, `SUMMARY:${icsText(title)}`,
        `LOCATION:${icsText(location)}`, `DESCRIPTION:${icsText(rec.n)}`,
        'BEGIN:VALARM', 'ACTION:DISPLAY', `DESCRIPTION:${icsText(title)}`, 'TRIGGER:-PT1H', 'END:VALARM',
        'END:VEVENT']);
    };
    const cls = classSchedule(rec);
    if (cls) add('class', opts.classTitle, cls, [rec.room, opts.location].filter(Boolean).join(', '));
    const tl = workshopTimeline(rec, now);
    [tl.current, tl.next].filter(Boolean).forEach((w, i) => {
      const sched = parseScheduleText(w.time);
      if (!sched) return;
      const from = isoDay(w.start);
      add('workshop' + i, `${opts.workshopTitle}: ${w.title}`, sched,
          [w.room, opts.location].filter(Boolean).join(', '),
          { from: from && from > now ? from : now, until: isoDay(w.end) });
    });
    if (!events.length) return '';
    const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//TUMO Astana//Schedule//RU', 'CALSCALE:GREGORIAN',
      'BEGIN:VTIMEZONE', 'TZID:Asia/Almaty', 'BEGIN:STANDARD', 'DTSTART:19700101T000000',
      'TZOFFSETFROM:+0500', 'TZOFFSETTO:+0500', 'TZNAME:+05', 'END:STANDARD', 'END:VTIMEZONE']
      .concat(...events, ['END:VCALENDAR']);
    return lines.map(foldLine).join('\r\n') + '\r\n';
  }

  // Google Calendar "add event" link for the regular class (weekly).
  function googleCalendarUrl(rec, opts) {
    const cls = classSchedule(rec);
    if (!cls) return '';
    const day = ymd(firstDate(cls.days, opts.now || new Date()));
    const t = s => s.replace(':', '') + '00';
    const q = new URLSearchParams({
      action: 'TEMPLATE', text: opts.classTitle, ctz: 'Asia/Almaty',
      dates: `${day}T${t(cls.start)}/${day}T${t(cls.end)}`,
      recur: `RRULE:FREQ=WEEKLY;BYDAY=${cls.days.join(',')}`,
      location: [rec.room, opts.location].filter(Boolean).join(', '), details: rec.n
    });
    return 'https://calendar.google.com/calendar/render?' + q.toString();
  }

  const isoDay = iso => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(iso || '')) return null;
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d);
  };

  // Current and next workshop of a student and the alerts to show:
  //   current: running today (start <= today <= end; missing dates count as open-ended)
  //   next:    the earliest one that hasn't started yet
  //   nextSoon: next starts within `soonDays` days (default 14) -> «скоро новый воркшоп»
  //   changed:  current or next was changed within `soonDays` days -> «воркшоп изменён»
  function workshopTimeline(rec, now, soonDays) {
    const days = soonDays || 14;
    const today = new Date((now || new Date()).getFullYear(), (now || new Date()).getMonth(), (now || new Date()).getDate());
    const list = (rec.workshops || []).filter(w => {
      const end = isoDay(w.end);
      return !end || end >= today;                     // finished workshops are dropped
    });
    const started = w => { const s = isoDay(w.start); return !s || s <= today; };
    const current = list.filter(started).pop() || null; // the latest one already running
    const next = list.find(w => !started(w)) || null;
    const within = (iso, sign) => {
      const d = isoDay(iso);
      if (!d) return false;
      const diff = (d - today) / 86400000 * sign;
      return diff >= 0 && diff <= days;
    };
    return {
      current, next,
      nextSoon: !!(next && within(next.start, 1)),
      changed: [current, next].some(w => w && within(w.changed, -1))
    };
  }

  // ---------- search ----------
  // Kazakh letters fold to their closest Russian letter (as in the onboarding app), plus ё/й/э,
  // so either keyboard layout finds the name: "нуртас" finds "Нұртас", "Әлихан" finds "Алихан".
  const FOLD = { 'ә': 'а', 'ғ': 'г', 'қ': 'к', 'ң': 'н', 'ө': 'о', 'ұ': 'у', 'ү': 'у', 'һ': 'х', 'і': 'и',
                 'ё': 'е', 'й': 'и', 'э': 'е' };
  const MIN_QUERY_LETTERS = 3;
  const MIN_QUERY_WORDS = 2; // first name + last name, as in the onboarding app
  const MAX_RESULTS = 3;     // more matches than this: the query is too vague to show anything

  // Latin letters that look like Cyrillic ones (lowercased). Typed by mistake inside Cyrillic
  // names in the sheet: "Tөлеуғазы" (Latin T), "Iңкар" (Latin I). Only used for mixed words.
  const LATIN_LOOKALIKE = { a: 'а', b: 'в', c: 'с', e: 'е', h: 'н', i: 'і', k: 'к', m: 'м', o: 'о',
                            p: 'р', t: 'т', x: 'х', y: 'у' };
  const CYRILLIC = /[\u0400-\u04ff]/;

  function words(text) {
    return (String(text == null ? '' : text).toLowerCase()
      .normalize('NFKD').replace(/[\u0300-\u036f]/g, '') // Latin diacritics; й/ё are folded below
      .normalize('NFC').match(/[\p{L}\p{N}]+/gu) || [])
      .map(w => CYRILLIC.test(w) ? w.replace(/[abcehikmoptxy]/g, ch => LATIN_LOOKALIKE[ch]) : w);
  }

  const fold = w => w.replace(/[әғқңөұүһіёйэ]/g, ch => FOLD[ch]);

  // Each word of a name as its comparable spellings. "ә" is typed as "а" or "е" on a Russian
  // keyboard ("Әлихан" -> "Алихан", "Сәкен" -> "Сакен"/"Секен"), so both are kept.
  function nameTokens(name) {
    return words(name).map(w => {
      const base = fold(w);
      return w.includes('ә') ? [base, fold(w.replace(/ә/g, 'е'))] : [base];
    });
  }

  function queryTokens(query) {
    return words(query).map(fold);
  }

  // Every query word must be the start of a *different* word of the name, in any order
  // (onboarding app rule). Longest query words are placed first to avoid greedy mis-pairing.
  function matchesName(qTokens, nTokens) {
    const free = nTokens.slice();
    for (const q of qTokens.slice().sort((a, b) => b.length - a.length)) {
      const i = free.findIndex(variants => variants.some(v => v.startsWith(q)));
      if (i === -1) return false;
      free.splice(i, 1);
    }
    return true;
  }

  // -> {status: 'short' | 'none' | 'too_many' | 'ok', results, total}
  // Same rules as the onboarding app: needs a first name and a last name of 3+ letters each
  // (shorter words are ignored); more than maxResults matches (default 3) shows nothing.
  // Whole-word matches are listed first.
  function searchStudents(records, query, maxResults) {
    const max = maxResults || MAX_RESULTS;
    const q = queryTokens(query).filter(w => w.length >= MIN_QUERY_LETTERS);
    if (q.length < MIN_QUERY_WORDS) return { status: 'short', results: [], total: 0 };
    const found = [];
    for (const r of records) {
      const tokens = r._t || (r._t = nameTokens(r.n));
      if (matchesName(q, tokens)) {
        const whole = q.filter(w => tokens.some(vs => vs.includes(w))).length;
        found.push({ r, whole });
      }
    }
    if (!found.length) return { status: 'none', results: [], total: 0 };
    if (found.length > max) return { status: 'too_many', results: [], total: found.length };
    found.sort((a, b) => b.whole - a.whole || a.r.n.localeCompare(b.r.n, 'ru'));
    return { status: 'ok', results: found.map(f => f.r), total: found.length };
  }

  function cleanText(value) {
    return (value == null ? '' : String(value)).replace(/\s+/g, ' ').trim();
  }

  // "10:30", "10:30–12:30", "10.30-12.30" -> "10:30-12:30"
  function normalizeTime(value) {
    const s = cleanText(value).replace(/[–—]/g, '-').replace(/\./g, ':').replace(/\s*-\s*/g, '-');
    if (TIME_SLOTS.includes(s)) return s;
    const start = s.split('-')[0].replace(/^(\d):/, '0$1:');
    return TIME_SLOTS.find(slot => slot.startsWith(start + '-')) || s;
  }

  function normalizeDay(value) {
    const s = cleanText(value).toLowerCase();
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
  }

  function makeRecord(o) {
    const name = properCase(o.name);
    if (!name) return null;
    return {
      n: name,
      d: normalizeDay(o.day),
      t: normalizeTime(o.time),
      c: properCase(o.coach),
      ex: properCase(o.exCoach),
      stage: cleanText(o.stage) || DEFAULT_STAGE,
      email: cleanText(o.email).toLowerCase(),
      room: cleanText(o.room),
      status: cleanText(o.status).toLowerCase(), // '' | 'inactive' (red row) | 'waitlist' (dark purple row)
      // Workshops from the workshop sheet: [{title, room, coach, time, start, end, changed}],
      // dates ISO 'YYYY-MM-DD' or ''. Sorted by start date.
      workshops: (Array.isArray(o.workshops) ? o.workshops : []).map(w => Array.isArray(w)
        ? { title: cleanText(w[0]), room: cleanText(w[1]), coach: cleanText(w[2]), time: cleanText(w[3]),
            start: cleanText(w[4]), end: cleanText(w[5]), changed: cleanText(w[6]) }
        : { title: cleanText(w.title), room: cleanText(w.room), coach: cleanText(w.coach), time: cleanText(w.time),
            start: cleanText(w.start), end: cleanText(w.end), changed: cleanText(w.changed) })
        .filter(w => w.title)
    };
  }

  // Positional row: [name, day, time, coach, exCoach, stage, email, room, status, workshops]
  function fromRow(r) {
    return makeRecord({ name: r[0], day: r[1], time: r[2], coach: r[3], exCoach: r[4], stage: r[5], email: r[6], room: r[7], status: r[8],
                        workshops: r[9] });
  }

  const HEADER_ALIASES = {
    name: ['фио', 'фио ученика', 'ученик', 'name', 'student', 'full name'],
    day: ['день sl', 'день', 'day'],
    time: ['время', 'time'],
    coach: ['новый коуч sl', 'коуч sl', 'коуч', 'coach', 'new coach'],
    exCoach: ['ex-coach', 'ex coach', 'прежний коуч', 'старый коуч'],
    stage: ['этап', 'этап обучения', 'stage'],
    email: ['почта tumo ученика', 'почта ученика', 'почта tumo', 'почта', 'email', 'e-mail', 'student email'],
    room: ['зона обучения', 'кабинет', 'room']
  };

  function headerMap(headers) {
    const norm = headers.map(h => cleanText(h).toLowerCase());
    const map = {};
    Object.keys(HEADER_ALIASES).forEach(field => {
      const idx = norm.findIndex(h => HEADER_ALIASES[field].includes(h));
      if (idx !== -1) map[field] = idx;
    });
    return map;
  }

  // RFC 4180 CSV (quoted fields, "" escapes, CRLF) -> array of rows.
  function parseCsv(text) {
    const rows = [];
    let row = [], field = '', inQuotes = false;
    const src = String(text).replace(/^﻿/, '');
    for (let i = 0; i < src.length; i++) {
      const ch = src[i];
      if (inQuotes) {
        if (ch === '"') {
          if (src[i + 1] === '"') { field += '"'; i++; }
          else inQuotes = false;
        } else field += ch;
      } else if (ch === '"') inQuotes = true;
      else if (ch === ',') { row.push(field); field = ''; }
      else if (ch === '\n' || ch === '\r') {
        if (ch === '\r' && src[i + 1] === '\n') i++;
        row.push(field); rows.push(row); row = []; field = '';
      } else field += ch;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    return rows.filter(r => r.some(v => cleanText(v)));
  }

  function fromCsv(text) {
    const rows = parseCsv(text);
    if (!rows.length) return [];
    const map = headerMap(rows[0]);
    if (map.name === undefined) throw new Error('CSV: колонка с ФИО не найдена');
    return rows.slice(1).map(r => makeRecord({
      name: r[map.name], day: r[map.day], time: r[map.time], coach: r[map.coach],
      exCoach: r[map.exCoach], stage: r[map.stage], email: r[map.email], room: r[map.room]
    })).filter(Boolean);
  }

  // Accepts [[...]], [{name,...}] or {students: [...]}.
  function fromJson(json) {
    const list = Array.isArray(json) ? json : (json && json.students);
    if (!Array.isArray(list)) throw new Error('JSON: список учеников не найден');
    return list.map(item => Array.isArray(item) ? fromRow(item) : makeRecord(item || {})).filter(Boolean);
  }

  function parseStudents(text, contentType) {
    return parseSource(text, contentType).records;
  }

  // -> {records, updated}: updated is the "updated" timestamp of data/students.json (or null).
  function parseSource(text, contentType) {
    const trimmed = String(text).replace(/^﻿/, '').trim();
    const looksJson = /json/i.test(contentType || '') || trimmed.startsWith('[') || trimmed.startsWith('{');
    if (!looksJson) return { records: fromCsv(trimmed), updated: null };
    const json = JSON.parse(trimmed);
    return { records: fromJson(json), updated: (json && !Array.isArray(json) && json.updated) || null };
  }

  // "2026-10-16T07:24:05+00:00" -> "16.10.2026, 12:24" in the viewer's time zone; a bare date
  // ("2026-10-16") -> "16.10.2026". Fixed format, like the onboarding app (not every browser
  // ships Kazakh locale data for Intl).
  function formatUpdated(value) {
    if (!value) return '';
    const pad = n => String(n).padStart(2, '0');
    const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (dateOnly) return `${dateOnly[3]}.${dateOnly[2]}.${dateOnly[1]}`;
    const d = new Date(value);
    if (isNaN(d)) return '';
    return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  // Tries each URL in order and returns {records, source} from the first one that works.
  async function loadStudents(urls, fetchImpl) {
    const doFetch = fetchImpl || fetch;
    let lastError = new Error('Нет источников данных');
    for (const url of urls.filter(Boolean)) {
      try {
        const res = await doFetch(url, { cache: 'no-store' });
        if (!res.ok) throw new Error(url + ': HTTP ' + res.status);
        const { records, updated } = parseSource(await res.text(), res.headers && res.headers.get('content-type'));
        if (!records.length) throw new Error(url + ': пустой список');
        return { records, updated, source: url };
      } catch (err) {
        lastError = err;
      }
    }
    throw lastError;
  }

  return { properCase, coachName, studentId, parseScheduleText, classSchedule, buildIcs, googleCalendarUrl,
           workshopTimeline, normalizeTime, parseCsv, parseStudents, parseSource, formatUpdated, fromJson, fromCsv, loadStudents,
           nameTokens, queryTokens, matchesName, searchStudents, MIN_QUERY_LETTERS, MIN_QUERY_WORDS, MAX_RESULTS,
           DEFAULT_STAGE };
});
