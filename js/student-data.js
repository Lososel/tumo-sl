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
  // Every word (also after "-", "(" or "+") gets a capital first letter, the rest lowercase.
  function properCase(value) {
    const s = (value == null ? '' : String(value)).replace(/\s+/g, ' ').trim().toLowerCase();
    return s.replace(/(^|[\s\-(+])(\p{L})/gu, (m, sep, ch) => sep + ch.toUpperCase());
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
      email: cleanText(o.email).toLowerCase()
    };
  }

  // Positional row: [name, day, time, coach, exCoach, stage, email]
  function fromRow(r) {
    return makeRecord({ name: r[0], day: r[1], time: r[2], coach: r[3], exCoach: r[4], stage: r[5], email: r[6] });
  }

  const HEADER_ALIASES = {
    name: ['фио', 'фио ученика', 'ученик', 'name', 'student', 'full name'],
    day: ['день sl', 'день', 'day'],
    time: ['время', 'time'],
    coach: ['новый коуч sl', 'коуч sl', 'коуч', 'coach', 'new coach'],
    exCoach: ['ex-coach', 'ex coach', 'прежний коуч', 'старый коуч'],
    stage: ['этап', 'этап обучения', 'stage'],
    email: ['почта tumo ученика', 'почта ученика', 'почта tumo', 'почта', 'email', 'e-mail', 'student email']
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
      exCoach: r[map.exCoach], stage: r[map.stage], email: r[map.email]
    })).filter(Boolean);
  }

  // Accepts [[...]], [{name,...}] or {students: [...]}.
  function fromJson(json) {
    const list = Array.isArray(json) ? json : (json && json.students);
    if (!Array.isArray(list)) throw new Error('JSON: список учеников не найден');
    return list.map(item => Array.isArray(item) ? fromRow(item) : makeRecord(item || {})).filter(Boolean);
  }

  function parseStudents(text, contentType) {
    const trimmed = String(text).replace(/^﻿/, '').trim();
    const looksJson = /json/i.test(contentType || '') || trimmed.startsWith('[') || trimmed.startsWith('{');
    return looksJson ? fromJson(JSON.parse(trimmed)) : fromCsv(trimmed);
  }

  // Tries each URL in order and returns {records, source} from the first one that works.
  async function loadStudents(urls, fetchImpl) {
    const doFetch = fetchImpl || fetch;
    let lastError = new Error('Нет источников данных');
    for (const url of urls.filter(Boolean)) {
      try {
        const res = await doFetch(url, { cache: 'no-store' });
        if (!res.ok) throw new Error(url + ': HTTP ' + res.status);
        const records = parseStudents(await res.text(), res.headers && res.headers.get('content-type'));
        if (!records.length) throw new Error(url + ': пустой список');
        return { records, source: url };
      } catch (err) {
        lastError = err;
      }
    }
    throw lastError;
  }

  return { properCase, normalizeTime, parseCsv, parseStudents, fromJson, fromCsv, loadStudents, DEFAULT_STAGE };
});
