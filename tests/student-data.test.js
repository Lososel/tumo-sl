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
    stage: 'Самообучение', email: '', room: '', status: ''
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
    stage: 'Самообучение', email: 'nurai.tuleu@tumo.kz', room: '', status: ''
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

test('search: first name and last name, 3+ letters each, any order', () => {
  const recs = ['Батыржан Нұрали Амангелдіұлы', 'Батырхан Ахметов', 'Ерлан Батыров', 'Амина Сейтказы']
    .map(n => ({ n }));
  const names = q => S.searchStudents(recs, q).results.map(r => r.n);
  assert.strictEqual(S.searchStudents(recs, 'Бат').status, 'short');      // one word is not enough
  assert.strictEqual(S.searchStudents(recs, 'Батыржан').status, 'short');
  assert.deepStrictEqual(names('Бат Ама'), ['Батыржан Нұрали Амангелдіұлы']);
  assert.deepStrictEqual(names('Бат Ерл'), ['Ерлан Батыров']);
  assert.deepStrictEqual(names('ама бат'), ['Батыржан Нұрали Амангелдіұлы']);
  assert.deepStrictEqual(names('ахметов батырхан'), ['Батырхан Ахметов']);
  assert.deepStrictEqual(names('Бат Бат'), []); // two words can't both use the same name word
  assert.strictEqual(S.searchStudents(recs, 'Ба').status, 'short');
  assert.strictEqual(S.searchStudents(recs, 'Ба Ам').status, 'short');
  assert.strictEqual(S.searchStudents(recs, 'Ба Ама').status, 'short');  // "Ба" is too short
  assert.strictEqual(S.searchStudents(recs, 'Xyz Abc').status, 'none');
});

test('search: Kazakh and Russian letters are interchangeable', () => {
  const recs = ['Нұртас Бердікұл', 'Әлихан Сәкенов', 'Ғалия Қасымова', 'Өмірзақ Үсенов', 'Ілияс Шоқан', 'Артём Йорданов']
    .map(n => ({ n }));
  const first = q => (S.searchStudents(recs, q).results[0] || {}).n;
  assert.strictEqual(first('нуртас берд'), 'Нұртас Бердікұл');
  assert.strictEqual(first('БЕРДИКУЛ НУРТАС'), 'Нұртас Бердікұл');
  assert.strictEqual(first('Нұр Бер'), 'Нұртас Бердікұл');
  assert.strictEqual(first('алихан сак'), 'Әлихан Сәкенов');   // ә ~ а
  assert.strictEqual(first('элихан сак'), 'Әлихан Сәкенов');   // ә ~ э/е
  assert.strictEqual(first('секенов али'), 'Әлихан Сәкенов');  // ә ~ е
  assert.strictEqual(first('галия касым'), 'Ғалия Қасымова');
  assert.strictEqual(first('омир усен'), 'Өмірзақ Үсенов');
  assert.strictEqual(first('илияс шок'), 'Ілияс Шоқан');
  assert.strictEqual(first('шокан илияс'), 'Ілияс Шоқан');
  assert.strictEqual(first('артем иорд'), 'Артём Йорданов');
});

test('search: whole-word matches first; more than 3 matches is "too many"', () => {
  const recs = ['Батырхан Ахмедов', 'Батыржан Ахметов', 'Баты Ахметова'].map(n => ({ n }));
  const res = S.searchStudents(recs, 'баты ахм');
  assert.strictEqual(res.status, 'ok');
  assert.deepStrictEqual(res.results.map(r => r.n), ['Баты Ахметова', 'Батыржан Ахметов', 'Батырхан Ахмедов']);
  const four = recs.concat([{ n: 'Батыр Ахметжанов' }]);
  assert.deepStrictEqual(S.searchStudents(four, 'баты ахм'), { status: 'too_many', results: [], total: 4 });
  assert.strictEqual(S.MAX_RESULTS, 3);
});

test('search: Latin lookalike letters inside Cyrillic names still match', () => {
  const recs = ['Tөлеуғазы Алдияр Қуандықұлы', 'Iңкар Киясова', 'Tұрсынбек Mади Мұратұлы', 'Agayeva Zakhirat']
    .map(n => ({ n }));
  const first = q => (S.searchStudents(recs, q).results[0] || {}).n;
  assert.strictEqual(first('толеугазы алдияр'), 'Tөлеуғазы Алдияр Қуандықұлы'); // Latin T in the sheet
  assert.strictEqual(first('Төлеуғазы Алд'), 'Tөлеуғазы Алдияр Қуандықұлы');
  assert.strictEqual(first('инкар кияс'), 'Iңкар Киясова');                          // Latin I
  assert.strictEqual(first('мади турсынбек'), 'Tұрсынбек Mади Мұратұлы');     // Latin T and M
  assert.strictEqual(first('agayeva zakh'), 'Agayeva Zakhirat');                     // Latin names untouched
});

test('updated timestamp is read from students.json and formatted like the onboarding app', () => {
  const src = S.parseSource(JSON.stringify({ updated: '2026-10-16T07:24:05+00:00', students: [['Иван Петров', 'Вторник', '10:30-12:30', 'Almas', 'Almas']] }));
  assert.strictEqual(src.records.length, 1);
  assert.strictEqual(src.updated, '2026-10-16T07:24:05+00:00');
  const d = new Date('2026-10-16T07:24:05+00:00');
  const pad = n => String(n).padStart(2, '0');
  assert.strictEqual(S.formatUpdated(src.updated), `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}, ${pad(d.getHours())}:${pad(d.getMinutes())}`);
  assert.strictEqual(S.formatUpdated('2026-10-14'), '14.10.2026');   // older files stored only the date
  assert.strictEqual(S.formatUpdated(null), '');
  assert.strictEqual(S.formatUpdated('garbage'), '');
  assert.strictEqual(S.parseSource('[["Иван Петров","Вторник","10:30-12:30","",""]]').updated, null);
});

test('room (Кабинет) is read from rows and from the «Зона обучения» CSV column', () => {
  const [rec] = S.fromJson({ students: [['Кумарбеков Диар', 'Понедельник', '10:30-12:30', 'Ayaulym', '', 'Онбординг', 'diar.k@tumo.world', '3 этаж, 7 WR']] });
  assert.strictEqual(rec.room, '3 этаж, 7 WR');
  assert.strictEqual(rec.stage, 'Онбординг');
  const [csvRec] = S.fromCsv('ФИО,День SL,Время,Зона обучения\nКумарбеков Диар,Понедельник,10:30,3 этаж 7 WR\n');
  assert.strictEqual(csvRec.room, '3 этаж 7 WR');
});

test('coachName shows coach names in Cyrillic like tumo-onb-app', () => {
  assert.strictEqual(S.coachName('Dana Akhmetova', 'ru'), 'Дана Ахметова');
  assert.strictEqual(S.coachName('Alinur', 'kk'), 'Әлінұр');
  assert.strictEqual(S.coachName('Alinur', 'ru'), 'Алинур');
  assert.strictEqual(S.coachName('Ayaulym', 'ru'), 'Аяулым');
  assert.strictEqual(S.coachName('Aruzhan Torebek', 'ru'), 'Аружан Торебек');
  assert.strictEqual(S.coachName('Tahmina', 'ru'), 'Тахмина');
  assert.strictEqual(S.coachName('Gulim (+Dana Kurak)', 'kk'), 'Гүлім (+Дана Курак)');
  assert.strictEqual(S.coachName('Назым', 'ru'), 'Назым');
  assert.strictEqual(S.coachName('', 'ru'), '');
});

test('status (inactive / waitlist) is read from the 9th column', () => {
  const recs = S.fromJson({ students: [
    ['Шаймерденова Айша Азаматовна', '', '', '', '', 'Самообучение', '', '', 'inactive'],
    ['Дорт Эсманур', '', '', '', '', 'Самообучение', '', '', 'waitlist'],
    ['Аскерұлы Есбер', 'Понедельник', '10:30-12:30', 'Gulnaz', 'Gulnaz', 'Самообучение', 'a@tumo.world']] });
  assert.deepStrictEqual(recs.map(r => r.status), ['inactive', 'waitlist', '']);
  assert.strictEqual(S.searchStudents(recs, 'шаймерденова айша').results[0].status, 'inactive');
});
