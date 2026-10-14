// Run: node --test tests/*.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const S = require('../js/student-data.js');

test('properCase formats names in Title Case', () => {
  assert.strictEqual(S.properCase('БАТЫРЖАН НҰРАЛИ АМАНГЕЛДІҰЛЫ'), 'Батыржан Нұрали Амангелдіұлы');
  assert.strictEqual(S.properCase('  мейрбек   елнур БЕРІКҰЛЫ '), 'Мейрбек Елнур Берікұлы');
  assert.strictEqual(S.properCase('анна-мария'), 'Анна-Мария');
  assert.strictEqual(S.properCase('DANA TELZHAN (+dana kurak)'), 'Dana Telzhan (+Dana Kurak)');
  assert.strictEqual(S.properCase(''), '');
  assert.strictEqual(S.properCase(null), '');
});

test('normalizeTime maps start times and dashes to slots', () => {
  assert.strictEqual(S.normalizeTime('10:30'), '10:30-12:30');
  assert.strictEqual(S.normalizeTime('14:30 – 16:30'), '14:30-16:30');
  assert.strictEqual(S.normalizeTime('16.30'), '16:30-18:30');
});

test('fromJson accepts positional rows and title-cases names', () => {
  const recs = S.fromJson({ students: [
    ['ШОШАЕВ АЛДИЯР', 'Понедельник', '10:30-12:30', 'GULNAZ', 'nazym', 'Самообучение'],
    ['', 'Вторник', '10:30-12:30', '', '', ''],
  ] });
  assert.strictEqual(recs.length, 1);
  assert.deepStrictEqual(recs[0], {
    n: 'Шошаев Алдияр', d: 'Понедельник', t: '10:30-12:30', c: 'Gulnaz', ex: 'Nazym',
    stage: 'Самообучение', email: ''
  });
});

test('fromCsv maps Google Sheets headers, quotes and email column', () => {
  const csv = '﻿ФИО,День SL,Время,Новый коуч SL,ex-Coach,Почта TUMO ученика\r\n' +
    '"ТҮЛЕУ НҰРАЙ АЗАМАТҚЫЗЫ",четверг,14:30,Almas,"Gulim, Elmira",Nurai.Tuleu@tumo.kz\r\n' +
    ',,,,,\r\n';
  const recs = S.fromCsv(csv);
  assert.strictEqual(recs.length, 1);
  assert.deepStrictEqual(recs[0], {
    n: 'Түлеу Нұрай Азаматқызы', d: 'Четверг', t: '14:30-16:30', c: 'Almas', ex: 'Gulim, Elmira',
    stage: 'Самообучение', email: 'nurai.tuleu@tumo.kz'
  });
});

test('fromCsv rejects a sheet without a name column', () => {
  assert.throws(() => S.fromCsv('a,b\n1,2\n'), /ФИО/);
});

test('loadStudents falls back to the next source and bypasses cache', async () => {
  const calls = [];
  const fakeFetch = async (url, opts) => {
    calls.push([url, opts.cache]);
    if (url === 'sheet.csv') return { ok: false, status: 500 };
    return { ok: true, headers: { get: () => 'application/json' }, text: async () => '[["иван петров","Вторник","10:30-12:30","almas","almas"]]' };
  };
  const { records, source } = await S.loadStudents(['', 'sheet.csv', 'data/students.json'], fakeFetch);
  assert.strictEqual(source, 'data/students.json');
  assert.strictEqual(records[0].n, 'Иван Петров');
  assert.deepStrictEqual(calls, [['sheet.csv', 'no-store'], ['data/students.json', 'no-store']]);
});

test('loadStudents rejects when every source fails', async () => {
  await assert.rejects(S.loadStudents(['x'], async () => ({ ok: false, status: 404 })), /404/);
});

test('data/students.json parses and every name is already in Title Case', () => {
  const text = fs.readFileSync(path.join(__dirname, '..', 'data', 'students.json'), 'utf8');
  const raw = JSON.parse(text).students;
  const recs = S.parseStudents(text, 'application/json');
  assert.ok(recs.length > 1000);
  assert.strictEqual(recs.length, raw.length);
  raw.forEach(r => {
    assert.strictEqual(r[0], S.properCase(r[0]), r[0]);
    assert.strictEqual(r[3], S.properCase(r[3]), r[3]);
  });
});

test('search: 3-letter prefixes of first and/or last name, any order', () => {
  const recs = ['Батыржан Нұрали Амангелдіұлы', 'Батырхан Ахметов', 'Ерлан Батыров', 'Амина Сейтказы']
    .map(n => ({ n }));
  const names = q => S.searchStudents(recs, q).results.map(r => r.n);
  assert.deepStrictEqual(names('Бат'), ['Батыржан Нұрали Амангелдіұлы', 'Батырхан Ахметов', 'Ерлан Батыров']);
  assert.deepStrictEqual(names('Ама'), ['Батыржан Нұрали Амангелдіұлы']);
  assert.deepStrictEqual(names('Бат Ама'), ['Батыржан Нұрали Амангелдіұлы']);
  assert.deepStrictEqual(names('ама бат'), ['Батыржан Нұрали Амангелдіұлы']);
  assert.deepStrictEqual(names('ахметов батырхан'), ['Батырхан Ахметов']);
  assert.deepStrictEqual(names('Бат Бат'), []); // two words can't both use the same name word
  assert.strictEqual(S.searchStudents(recs, 'Ба').status, 'short');
  assert.strictEqual(S.searchStudents(recs, 'Ба Ам').status, 'short');
  assert.deepStrictEqual(names('Ба Ама'), ['Батыржан Нұрали Амангелдіұлы']); // short words ignored
  assert.strictEqual(S.searchStudents(recs, 'Xyz').status, 'none');
});

test('search: Kazakh and Russian letters are interchangeable', () => {
  const recs = ['Нұртас Бердікұл', 'Әлихан Сәкенов', 'Ғалия Қасымова', 'Өмірзақ Үсенов', 'Ілияс Шоқан', 'Артём Йорданов']
    .map(n => ({ n }));
  const first = q => (S.searchStudents(recs, q).results[0] || {}).n;
  assert.strictEqual(first('нуртас'), 'Нұртас Бердікұл');
  assert.strictEqual(first('БЕРДИКУЛ'), 'Нұртас Бердікұл');
  assert.strictEqual(first('Нұр'), 'Нұртас Бердікұл');
  assert.strictEqual(first('алихан'), 'Әлихан Сәкенов');   // ә ~ а
  assert.strictEqual(first('элихан'), 'Әлихан Сәкенов');   // ә ~ э/е
  assert.strictEqual(first('секенов'), 'Әлихан Сәкенов');  // ә ~ е
  assert.strictEqual(first('галия касым'), 'Ғалия Қасымова');
  assert.strictEqual(first('омир усен'), 'Өмірзақ Үсенов');
  assert.strictEqual(first('илияс'), 'Ілияс Шоқан');
  assert.strictEqual(first('шокан'), 'Ілияс Шоқан');
  assert.strictEqual(first('артем иорд'), 'Артём Йорданов');
});

test('search: whole-word matches first, results limited', () => {
  const recs = ['Баты Ахметова', 'Батыржан Алиев', 'Батырхан Бек'].map(n => ({ n }));
  const res = S.searchStudents(recs, 'баты', 2);
  assert.strictEqual(res.total, 3);
  assert.deepStrictEqual(res.results.map(r => r.n), ['Баты Ахметова', 'Батыржан Алиев']);
});

test('search: Latin lookalike letters inside Cyrillic names still match', () => {
  const recs = ['Tөлеуғазы Алдияр Қуандықұлы', 'Iңкар Киясова', 'Tұрсынбек Mади Мұратұлы', 'Agayeva Zakhirat']
    .map(n => ({ n }));
  const first = q => (S.searchStudents(recs, q).results[0] || {}).n;
  assert.strictEqual(first('толеугазы алдияр'), 'Tөлеуғазы Алдияр Қуандықұлы'); // Latin T in the sheet
  assert.strictEqual(first('Төлеуғазы'), 'Tөлеуғазы Алдияр Қуандықұлы');
  assert.strictEqual(first('инкар'), 'Iңкар Киясова');                          // Latin I
  assert.strictEqual(first('мади турсынбек'), 'Tұрсынбек Mади Мұратұлы');     // Latin T and M
  assert.strictEqual(first('agayeva'), 'Agayeva Zakhirat');                     // Latin names untouched
});
