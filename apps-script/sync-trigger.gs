/**
 * Starts the site sync (GitHub Actions «Sync students from master sheet») as soon as
 * the master sheet or «6 ПОТОК» changes. GitHub runs the workflow's own schedule only
 * every few hours, so this script checks the files' «last modified» time every few minutes
 * and calls the workflow when one of them changed.
 *
 * Setup (once), in the Google account that can open both files:
 *   1. script.google.com → New project → paste this file → Save.
 *   2. Project Settings (gear) → Script properties → Add: GITHUB_TOKEN = a fine-grained GitHub
 *      token (github.com → Settings → Developer settings → Fine-grained tokens): repository
 *      Lososel/tumo-sl only, permission «Actions: Read and write». Never put the token in this file.
 *   3. Run `setup` once (Run ▶, choose setup) and allow access: it creates the 5-minute trigger.
 *   4. Optional: run `checkNow` to test — the run appears in GitHub → Actions.
 */
const FILES = {
  main: '1qcmLsXYRvu6Pf0ghM17V0dvq3sUuBDqm',     // MAIN_ОБЩИЙ_… (master sheet)
  stream6: '19Q8pVsaqKuOWrx4bbR0lv9CcauLKL2hXs5qZE0iRcLQ', // 6 ПОТОК
};
const REPO = 'Lososel/tumo-sl';
const WORKFLOW = 'sync-students.yml';
const EVERY_MINUTES = 5; // 1, 5, 10, 15 or 30

function setup() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'checkForChanges')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('checkForChanges').timeBased().everyMinutes(EVERY_MINUTES).create();
  checkForChanges(); // remember the current state
}

function checkForChanges() {
  const props = PropertiesService.getScriptProperties();
  const changed = [];
  const seen = {};
  for (const [key, id] of Object.entries(FILES)) {
    const t = DriveApp.getFileById(id).getLastUpdated().getTime();
    seen[key] = t;
    const prev = Number(props.getProperty('mtime_' + key) || 0);
    if (prev && t > prev) changed.push(key);
  }
  if (changed.length) dispatch_(changed);
  // saved only after a successful dispatch (dispatch_ throws otherwise), so a failed call is retried
  for (const [key, t] of Object.entries(seen)) props.setProperty('mtime_' + key, String(t));
}

function checkNow() {
  dispatch_(['manual']);
}

function dispatch_(changed) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Script property GITHUB_TOKEN is missing');
  const res = UrlFetchApp.fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
      method: 'post',
      contentType: 'application/json',
      headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
      payload: JSON.stringify({ ref: 'main' }),
      muteHttpExceptions: true,
    });
  if (res.getResponseCode() !== 204) {
    throw new Error(`GitHub ${res.getResponseCode()}: ${res.getContentText().slice(0, 300)}`);
  }
  console.log('Sync started, changed: ' + changed.join(', '));
}
