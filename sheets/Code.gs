/**
 * Jeani onboarding survey -> Google Sheet.
 *
 * Bound Apps Script for the results spreadsheet. Deployed as a web app it
 * receives POSTs from survey/index.html and upserts one row per response.
 *
 * Setup (about 5 minutes, see sheets/README.md):
 *   1. New Google Sheet -> Extensions -> Apps Script. Paste this file over Code.gs.
 *   2. Run setup() once (authorise when asked). It creates "Responses" + "Summary".
 *   3. Deploy -> New deployment -> Web app. Execute as: Me. Who has access: Anyone.
 *   4. Copy the /exec URL into SURVEY_ENDPOINT at the top of survey/index.html.
 */

var SHEET_NAME = 'Responses';
var SUMMARY_NAME = 'Summary';
var HEADERS = ['created_at', 'updated_at', 'response_id', 'uid', 'source', 'rating', 'partial',
               'use_cases', 'use_cases_other', 'features', 'usage', 'design', 'improve',
               'contact_ok', 'user_agent', 'page'];
var LIST_FIELDS = ['use_cases', 'features', 'design'];
var TEXT_LIMITS = { usage: 120, use_cases_other: 120, improve: 1000, uid: 128, source: 64, user_agent: 300, page: 300 };
var COL = {};
HEADERS.forEach(function (h, i) { COL[h] = i; });

// ---- Web app entry points ---------------------------------------------------

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var body = e && e.postData && e.postData.contents;
    if (!body || body.length > 16 * 1024) throw new Error('bad body');
    var row = clean_(JSON.parse(body));
    return json_({ ok: true, result: upsert_(row) });
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  } finally {
    lock.releaseLock();
  }
}

function doGet() {
  return json_({ ok: true, sheet: SHEET_NAME });
}

// ---- Core -------------------------------------------------------------------

function clean_(d) {
  if (!d || typeof d !== 'object') throw new Error('body must be an object');
  var rid = d.response_id;
  if (typeof rid !== 'string' || rid.length < 8 || rid.length > 64 || !/^[a-zA-Z0-9]+$/.test(rid)) throw new Error('bad response_id');
  var out = { response_id: rid };

  var rating = d.rating;
  if (rating !== null && rating !== undefined) {
    if (typeof rating !== 'number' || rating % 1 !== 0 || rating < 1 || rating > 5) throw new Error('rating must be 1-5');
  }
  out.rating = (rating === undefined) ? null : rating;

  LIST_FIELDS.forEach(function (f) {
    var v = d[f] || [];
    if (!Array.isArray(v) || v.length > 20) throw new Error('bad list ' + f);
    v.forEach(function (x) { if (typeof x !== 'string' || x.length > 120) throw new Error('bad list ' + f); });
    out[f] = v.join(' | ');
  });

  Object.keys(TEXT_LIMITS).forEach(function (f) {
    var v = d[f];
    if (v === null || v === undefined) { out[f] = ''; return; }
    if (typeof v !== 'string') throw new Error('bad text ' + f);
    out[f] = v.trim().slice(0, TEXT_LIMITS[f]);
  });

  out.contact_ok = !!d.contact_ok;
  out.partial = !!d.partial;
  return out;
}

function upsert_(row) {
  var sh = sheet_();
  var now = new Date().toISOString();
  var last = sh.getLastRow();
  var found = -1;
  if (last > 1) {
    var ids = sh.getRange(2, COL.response_id + 1, last - 1, 1).getValues();
    for (var i = 0; i < ids.length; i++) {
      if (String(ids[i][0]) === row.response_id) { found = i + 2; break; }
    }
  }
  var createdAt = now;
  if (found > 0) {
    var existing = sh.getRange(found, 1, 1, HEADERS.length).getValues()[0];
    createdAt = existing[COL.created_at] || now;
    // A late partial ping (the rating recorded on email tap) must never overwrite a full answer.
    if (existing[COL.partial] === false && row.partial) return 'kept';
  }
  var values = HEADERS.map(function (h) {
    if (h === 'created_at') return createdAt;
    if (h === 'updated_at') return now;
    return row[h] === undefined ? '' : row[h];
  });
  if (found > 0) {
    sh.getRange(found, 1, 1, HEADERS.length).setValues([values]);
    return 'updated';
  }
  sh.appendRow(values);
  return 'created';
}

function sheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) sh = ss.insertSheet(SHEET_NAME);
  if (sh.getLastRow() === 0) {
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
  }
  return sh;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// ---- One-time setup ---------------------------------------------------------

/** Run once from the editor. Creates the Responses sheet and a live Summary sheet. */
function setup() {
  sheet_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sm = ss.getSheetByName(SUMMARY_NAME) || ss.insertSheet(SUMMARY_NAME);
  sm.clear();

  // Column letters in Responses: F rating, G partial, H use_cases, J features, K usage, L design, M improve, N contact_ok.
  var complete = 'Responses!G2:G=FALSE';
  function breakdown(colLetter) {
    // Splits "a | b | c" cells from completed responses and counts each option.
    return '=IFERROR(QUERY(FLATTEN(SPLIT(FILTER(Responses!' + colLetter + '2:' + colLetter + ', ' + complete +
      ', Responses!' + colLetter + '2:' + colLetter + '<>""), " | ", FALSE)), ' +
      '"select Col1, count(Col1) where Col1 is not null group by Col1 order by count(Col1) desc label count(Col1) \'\'", 0), "none yet")';
  }

  var rows = [
    ['Responses', '=COUNTA(Responses!C2:C)', '', 'Use cases', '', '', 'Useful features', '', '', 'Usage pattern', '', '', 'Design likes'],
    ['Complete', '=COUNTIF(Responses!G2:G, FALSE)', '', breakdown('H'), '', '', breakdown('J'), '', '', breakdown('K'), '', '', breakdown('L')],
    ['Average rating', '=IFERROR(ROUND(AVERAGE(Responses!F2:F), 2), "")'],
    ['Would take a call', '=COUNTIFS(Responses!N2:N, TRUE, Responses!G2:G, FALSE)'],
    [],
    ['Rating', 'Count'],
    [1, '=COUNTIF(Responses!F2:F, A7)'],
    [2, '=COUNTIF(Responses!F2:F, A8)'],
    [3, '=COUNTIF(Responses!F2:F, A9)'],
    [4, '=COUNTIF(Responses!F2:F, A10)'],
    [5, '=COUNTIF(Responses!F2:F, A11)'],
    [],
    ['One thing to improve (rating, text)'],
    ['=IFERROR(SORT(FILTER({Responses!F2:F, Responses!M2:M}, Responses!M2:M<>"", ' + complete + '), 1, TRUE), "none yet")']
  ];
  rows.forEach(function (r, i) { if (r.length) sm.getRange(i + 1, 1, 1, r.length).setValues([r]); });
  [1, 6, 13].forEach(function (r) { sm.getRange(r, 1, 1, 13).setFontWeight('bold'); });
  sm.setColumnWidth(1, 220); [4, 7, 10, 13].forEach(function (c) { sm.setColumnWidth(c, 260); });
  sm.setFrozenRows(0);
}

/** Optional: post a fake response to yourself to check the pipeline without the page. */
function testInsert() {
  var rid = 'test' + Utilities.getUuid().replace(/-/g, '').slice(0, 20);
  Logger.log(upsert_(clean_({ response_id: rid, rating: 4, source: 'apps_script_test', partial: true })));
  Logger.log(upsert_(clean_({ response_id: rid, rating: 5, source: 'apps_script_test', partial: false,
    use_cases: ['Trail or ultra'], features: ['The texts to my phone', 'Sleep insights'],
    usage: 'I read the texts, rarely open the app', design: ['Feels personal to me'],
    improve: 'Texts land too early.', contact_ok: true })));
  Logger.log(upsert_(clean_({ response_id: rid, rating: 1, partial: true }))); // -> kept
}
