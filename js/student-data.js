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
      status: cleanText(o.status).toLowerCase() // '' | 'inactive' (red row) | 'waitlist' (dark purple row)
    };
  }

  // Positional row: [name, day, time, coach, exCoach, stage, email, room, status]
  function fromRow(r) {
    return makeRecord({ name: r[0], day: r[1], time: r[2], coach: r[3], exCoach: r[4], stage: r[5], email: r[6], room: r[7], status: r[8] });
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

  return { properCase, coachName, normalizeTime, parseCsv, parseStudents, parseSource, formatUpdated, fromJson, fromCsv, loadStudents,
           nameTokens, queryTokens, matchesName, searchStudents, MIN_QUERY_LETTERS, MIN_QUERY_WORDS, MAX_RESULTS,
           DEFAULT_STAGE };
});
