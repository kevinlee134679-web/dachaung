// Exercise the actual native page logic; Node built-ins only, without browser dependencies.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const { webcrypto } = require('node:crypto');

class Element {
  constructor(tag, text = '') {
    this.tagName = tag.toUpperCase(); this.children = []; this.events = {}; this.attributes = {};
    this.value = ''; this.type = ''; this.checked = false; this.selected = false; this.disabled = false;
    this.className = ''; this.style = {}; this.files = []; this._text = text;
  }
  append(...nodes) {
    for (const node of nodes) {
      this.children.push(node);
      if (this.tagName === 'SELECT' && node.tagName === 'OPTION' && (node.selected || this.children.length === 1)) this.value = node.value;
    }
  }
  replaceChildren(...nodes) { this.children = []; this._text = ''; this.append(...nodes); }
  addEventListener(name, action) { this.events[name] = action; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(''); }
  set textContent(text) { this._text = text; this.children = []; }
  get firstChild() { return this.children[0]; }
  click() { return this.events.click?.({ currentTarget: this }); }
  change() { return this.events.change?.({ currentTarget: this }); }
  input() { return this.events.input?.({ currentTarget: this }); }
}
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
function success(data) { return { ok: true, status: 200, json: async () => ({ status: 'success', data, error: null }) }; }
function failure(status, code, message) { return { ok: false, status, json: async () => ({ status: 'error', data: null, error: { code, message } }) }; }
function find(node, predicate) {
  if (predicate(node)) return node;
  for (const child of node.children) { const result = find(child, predicate); if (result) return result; }
  return null;
}
function byText(root, tag, text) {
  const node = find(root, n => n.tagName === tag.toUpperCase() && n.textContent === text);
  assert.ok(node, `${tag} ${text} not found`); return node;
}
function field(root, text) {
  const label = find(root, n => n.tagName === 'LABEL' && n.children[0]?.textContent === text);
  assert.ok(label, `field ${text} not found`); return label.children[1];
}
function check(root, text) { return byText(root, 'label', text).children[0]; }
function setup(fetch) {
  const roots = Object.fromEntries(['#main', '#identity', '#notice', '#health', '#refresh'].map(k => [k, new Element('div')]));
  const stored = new Map();
  const context = vm.createContext({ Node: Element, FormData, TextEncoder, Uint8Array, ArrayBuffer, URL, URLSearchParams,
    AbortController, setTimeout, clearTimeout, Blob, Intl, crypto: webcrypto, fetch,
    localStorage: { getItem: key => stored.get(key) ?? null, setItem: (key, value) => stored.set(key, String(value)), removeItem: key => stored.delete(key) },
    document: { createElement: tag => new Element(tag), createTextNode: text => new Element('#text', String(text)), querySelector: selector => roots[selector], querySelectorAll: () => [] } });
  const source = fs.readFileSync(path.join(__dirname, '..', 'medplatform', 'static', 's02.js'), 'utf8');
  const cutoff = source.lastIndexOf('for (const b of document.querySelectorAll');
  vm.runInContext(source.slice(0, cutoff) + '\nglobalThis.frontend = {state,api,button,render,scheduleView,reportView,summaryView,medicationReportForm,measurementForm,eventCard,eventListView,taskView,demoView};', context);
  const app = context.frontend;
  function choose(patient = 'pa', account = 'account-a', relationship = 'self') {
    const access = { patient: { patient_id: patient, display_name: patient, timezone: 'Asia/Shanghai' }, relationship,
      effective_scopes: ['plan:read', 'records:read', 'records:report', 'records:correct', 'statistics:read', 'summary:read', 'measurements:read', 'measurements:write', 'reminder:read', 'reminder:write', 'tasks:read'] };
    app.state.context = { account: { account_id: account, display_name: account, is_simulated: true }, current_patient_id: patient, patients: [access], csrf_token: 'csrf-' + account };
    app.state.patient = access;
  }
  choose(); return { app, roots, stored, choose };
}
const tick = () => new Promise(resolve => setImmediate(resolve));
const slot = { dose_slot_id: 'slot-a', medication_id: 'med-a', plan_id: 'plan-a', plan_version: 1, plan_entry_id: 'entry-a', scheduled_at: '2026-11-16T00:00:00Z', status: 'active' };
function statistic(as_of = '2026-11-17T00:00:00Z') {
  return { statistics_id: 'statistics-a', patient_id: 'pa', window_start: '2026-11-10T00:00:00+08:00', window_end: '2026-11-17T00:00:00+08:00',
    as_of, patient_confirmed_count: 1, reported_not_taken_count: 0, postponed_count: 0, unconfirmed_evidence_count: 2, unknown_count: 1,
    planned_dose_count: 4, patient_confirmation_ratio: 0.25, data_status: 'ready', issues: [], is_simulated: true };
}
function summary() { return { summary_id: 'summary-a', data_status: 'insufficient', generated_at: '2026-11-17T00:00:00Z', valid_until: '2026-11-17T00:15:00Z', record_overview: statistic(), measurement_overview: [], feedback_overview: { sources: [{ source_module: 'B', availability: 'not_integrated', reason: 'not integrated' }, { source_module: 'C', availability: 'not_integrated', reason: 'not integrated' }] }, missing_items: [] }; }
function event(payload = {}) { return { event_id: 'event-a', event_kind: 'medication', source: 'manual', evidence_type: 'self_report', reporter_account_id: 'account-a', occurred_at: '2026-11-16T00:00:45.123456Z', received_at: '2026-11-16T01:00:00Z', state: 'effective', payload: { reported_status: 'taken', observation: null, medication_id: 'med-a', dose_slot_id: 'slot-a', plan_ref: { plan_id: 'plan-a', plan_version: 1 }, raw_text: 'original', ...payload }, quality: { status: 'valid', issues: [] }, link_status: 'matched', meta: { revision: 2, is_simulated: true } }; }

test('report entry only reads; explicit refresh binds statistics and trend to the returned cutoff', async () => {
  const calls = []; let ready = false;
  const env = setup(async (url, options) => {
    calls.push({ url, method: options.method, body: options.body && JSON.parse(options.body) });
    if (options.method === 'POST') { ready = true; return success(summary()); }
    if (!ready) return failure(409, 'SNAPSHOT_NOT_READY', 'explicit refresh required');
    if (url.includes('/medication-trends')) return success({ items: [statistic()], aggregate: statistic() });
    if (url.includes('/dose-matches')) return success({ items: [], next_cursor: null });
    return success(statistic());
  });
  env.app.state.page = 'profile'; env.app.state.tab = 'report';
  await env.app.render();
  assert.equal(calls.some(call => call.method === 'POST'), false);
  await byText(env.roots['#main'], 'button', '明确刷新统计与摘要').click();
  assert.equal(calls.filter(call => call.method === 'POST').length, 1);
  for (const call of calls.filter(call => /medication-statistics|medication-trends|dose-matches/.test(call.url))) assert.equal(new URL('http://test' + call.url).searchParams.get('as_of'), '2026-11-17T00:00:00Z');
  assert.equal(env.roots['#main'].textContent.includes('25.0%'), true);
  assert.equal(env.roots['#main'].textContent.includes('50.0%'), false);
});

test('successful report refresh after a rejected window replaces its old error notice', async () => {
  let ready = false;
  const env = setup(async (url, options) => {
    if (options.method === 'POST') { ready = true; return success(summary()); }
    if (!ready) return failure(409, 'SNAPSHOT_NOT_READY', 'OLD_WINDOW_ERROR');
    if (url.includes('/medication-trends')) return success({ items: [statistic()], aggregate: statistic() });
    if (url.includes('/dose-matches')) return success({ items: [], next_cursor: null });
    return success(statistic());
  });
  env.app.state.page = 'profile'; env.app.state.tab = 'report';
  await env.app.render();
  await byText(env.roots['#main'], 'button', '读取已保存报告').click();
  assert.equal(env.roots['#notice'].textContent, 'OLD_WINDOW_ERROR');
  assert.equal(env.roots['#notice'].className, 'error');
  field(env.roots['#main'], '起始日期（北京时间）').value = '2026-11-10';
  field(env.roots['#main'], '结束日期（不含当日，北京时间）').value = '2026-11-17';
  await byText(env.roots['#main'], 'button', '明确刷新统计与摘要').click();
  assert.equal(env.roots['#notice'].textContent.includes('OLD_WINDOW_ERROR'), false);
  assert.equal(env.roots['#notice'].textContent.includes('已刷新统计与摘要'), true);
  assert.equal(env.roots['#notice'].className, 'success');
  assert.equal(env.roots['#main'].textContent.includes('25.0%'), true);
});

test('render initial 409 leaves no detached old error after a successful report refresh', async () => {
  let ready = false;
  const env = setup(async (url, options) => {
    if (options.method === 'POST') { ready = true; return success(summary()); }
    if (!ready) return failure(409, 'SNAPSHOT_NOT_READY', 'DETACHED_INITIAL_ERROR');
    if (url.includes('/medication-trends')) return success({ items: [statistic()], aggregate: statistic() });
    if (url.includes('/dose-matches')) return success({ items: [], next_cursor: null });
    return success(statistic());
  });
  env.app.state.page = 'profile'; env.app.state.tab = 'report';
  await env.app.render();
  assert.equal(env.roots['#main'].textContent.includes('尚无此范围的可用快照'), true);
  await byText(env.roots['#main'], 'button', '明确刷新统计与摘要').click();
  const allPageText = env.roots['#main'].textContent + env.roots['#notice'].textContent;
  assert.equal(allPageText.includes('DETACHED_INITIAL_ERROR'), false);
  assert.equal(allPageText.includes('尚无此范围的可用快照'), false);
  assert.equal(allPageText.includes('25.0%'), true);
  assert.equal(allPageText.includes('已刷新统计与摘要'), true);
});

test('received unusable measurements display unavailable with their actual quality reason', () => {
  const env = setup(async () => success({}));
  const result = summary();
  result.measurement_overview = [{ metric_code: 'sleep_duration', availability: 'unavailable', latest_value: null, unit: null, sampled_at: null, missing_items: ['已有记录，但原单位未知，当前不能形成可用指标'] }];
  const content = env.app.summaryView(result).textContent;
  assert.equal(content.includes('睡眠时长：不可用'), true);
  assert.equal(content.includes('已有记录，但原单位未知'), true);
  assert.equal(content.includes('未采集'), false);
  assert.equal(content.includes('未采样'), false);
});

test('slot report retries an unknown result with the same source and idempotency keys', async () => {
  const posts = []; let attempts = 0;
  const env = setup(async (url, options) => {
    posts.push({ url, body: JSON.parse(options.body), key: options.headers['Idempotency-Key'] });
    if (!attempts++) throw new TypeError('connection interrupted');
    return success(event());
  });
  env.app.medicationReportForm(env.roots['#main'], slot);
  const save = byText(env.roots['#main'], 'button', '明确保存服药报告');
  await save.click(); await save.click();
  assert.equal(posts.length, 2);
  assert.equal(posts[0].key, posts[1].key);
  assert.deepEqual(posts[0].body, posts[1].body);
  assert.equal(posts[1].body.dose_slot_id, 'slot-a');
  assert.equal('evidence_type' in posts[1].body, false);
});

test('family report controls keep the family boundary and cannot act after patient switch', async () => {
  const calls = [];
  const env = setup(async (...args) => { calls.push(args); return success(event()); });
  env.choose('pa', 'family-a', 'family'); env.app.medicationReportForm(env.roots['#main'], slot);
  assert.equal(env.roots['#main'].textContent.includes('不计入本人确认已服'), true);
  const save = byText(env.roots['#main'], 'button', '明确保存服药报告');
  env.choose('pb', 'family-a', 'family'); env.app.state.epoch++;
  await save.click(); assert.equal(calls.length, 0);
});

test('an unchanged successful report keeps its source identity when the form is submitted again', async () => {
  const sources = [];
  const env = setup(async (url, options) => { sources.push(JSON.parse(options.body).source_event_id); return success(event()); });
  env.app.medicationReportForm(env.roots['#main'], slot);
  const save = byText(env.roots['#main'], 'button', '明确保存服药报告');
  await save.click(); await save.click();
  assert.equal(sources[0], sources[1]);
  field(env.roots['#main'], '报告内容').value = 'not_taken';
  await save.click();
  assert.notEqual(sources[2], sources[0]);
});

test('patient switch during source-fingerprint preparation sends no old slot report', async () => {
  const calls = [];
  const env = setup(async (...args) => { calls.push(args); return success(event()); });
  env.app.medicationReportForm(env.roots['#main'], slot);
  const pending = byText(env.roots['#main'], 'button', '明确保存服药报告').click();
  env.choose('pb'); env.app.state.epoch++;
  await pending;
  assert.equal(calls.length, 0);
  assert.equal(env.stored.size, 0);
});

test('measurement forms preserve zero, explicit missing, and an unknown raw unit', async () => {
  const writes = [];
  const env = setup(async (url, options) => { writes.push(JSON.parse(options.body)); return success({ quality: { status: 'needs_review', issues: [] } }); });
  env.app.measurementForm(env.roots['#main']);
  field(env.roots['#main'], '实际数值（缺失时不填）').value = '0';
  field(env.roots['#main'], '原单位（睡眠h、步数count、心率beats/min）').value = 'unknown-unit';
  const save = byText(env.roots['#main'], 'button', '保存指标记录');
  await save.click();
  assert.equal(writes[0].payload.value, 0); assert.equal(writes[0].payload.unit, 'unknown-unit');
  check(env.roots['#main'], '本次未采集或数值缺失').checked = true;
  field(env.roots['#main'], '缺失原因').value = 'sensor unavailable';
  await save.click();
  assert.equal(writes[1].payload.value, null); assert.equal(writes[1].payload.missing_reason, 'sensor unavailable');
});

test('unchanged correction time retains exact precision and the current expected revision', async () => {
  const writes = [];
  const env = setup(async (url, options) => {
    if (options.method !== 'GET') writes.push(JSON.parse(options.body));
    return success({ items: [], next_cursor: null });
  });
  const original = event(); env.roots['#main'].append(env.app.eventCard(original));
  field(env.roots['#main'], '更正或撤销原因（必填）').value = 'correct original report';
  await byText(env.roots['#main'], 'button', '保存追加更正').click();
  assert.equal(writes[0].expected_revision, 2);
  assert.equal(writes[0].occurred_at, original.occurred_at);
  assert.equal('source' in writes[0], false); assert.equal('reporter_account_id' in writes[0], false);
});

test('a delayed old record list cannot pollute a new patient page', async () => {
  const response = deferred();
  const env = setup(async () => response.promise);
  const pending = env.app.eventListView('medication'); await tick();
  env.choose('pb'); env.app.state.epoch++; env.roots['#main'].replaceChildren(new Element('p', 'NEW_PATIENT'));
  response.resolve(success({ items: [event({ raw_text: 'STALE_PATIENT_REPORT' })], next_cursor: null }));
  await assert.rejects(pending, error => error.constructor.name === 'ViewChanged');
  assert.equal(env.roots['#main'].textContent, 'NEW_PATIENT');
});

test('a completed old correction cannot put its success notice onto a new patient after rereading', async () => {
  const response = deferred();
  const env = setup(async (url, options) => options.method === 'GET' ? response.promise : success(event()));
  env.roots['#main'].append(env.app.eventCard(event()));
  field(env.roots['#main'], '更正或撤销原因（必填）').value = 'correct original report';
  const pending = byText(env.roots['#main'], 'button', '保存追加更正').click();
  await tick(); await tick();
  env.choose('pb'); env.app.state.epoch++; env.roots['#main'].replaceChildren(new Element('p', 'NEW_PATIENT'));
  response.resolve(success({ items: [], next_cursor: null }));
  await pending;
  assert.equal(env.roots['#main'].textContent, 'NEW_PATIENT');
  assert.equal(env.roots['#notice'].textContent.includes('已追加更正'), false);
});

test('snooze sends only the original task revision and never creates medication evidence', async () => {
  const writes = [];
  const task = { task_id: 'task-a', kind: 'deliver_reminder', owner_module: 'O', status: 'succeeded', attempt_count: 1, max_attempts: 3,
    scheduled_at: '2026-11-17T00:00:00Z', valid_until: '2026-11-17T00:30:00Z', failure_reason: null, meta: { revision: 4, is_simulated: true } };
  const env = setup(async (url, options) => {
    if (options.method !== 'GET') { writes.push({ url, body: JSON.parse(options.body) }); return success(task); }
    return success({ items: [task], next_cursor: null });
  });
  await env.app.taskView();
  await byText(env.roots['#main'], 'button', '明确稍后提醒').click();
  assert.equal(writes.length, 1); assert.equal(writes[0].url.endsWith('/reminder-snoozes'), true);
  assert.deepEqual(writes[0].body, { source_task_id: 'task-a', expected_task_revision: 4, snooze_minutes: 10 });
});

test('ordinary patient cannot render management actions or execute a task by entering the console page', async () => {
  const calls = []; const env = setup(async (...args) => { calls.push(args); return success({}); });
  await env.app.demoView();
  assert.equal(env.roots['#main'].textContent.includes('仅对受控演示管理员开放'), true);
  assert.equal(find(env.roots['#main'], n => n.tagName === 'BUTTON'), null);
  assert.equal(calls.length, 0);
});

test('registered demo administrator can open the console without a transferable management scope', async () => {
  const calls = []; const env = setup(async (...args) => { calls.push(args); return success({}); });
  env.choose('pa', 'demo-admin');
  assert.equal(env.app.state.patient.effective_scopes.includes('demo:manage'), false);
  assert.equal('is_admin' in env.app.state.context.account, false);
  await env.app.demoView();
  assert.ok(byText(env.roots['#main'], 'button', '显式执行此任务一次'));
  assert.ok(byText(env.roots['#main'], 'button', '发送一次模拟事件'));
  assert.equal(calls.length, 0);
});

for (const [status, daysFromNow, expectedExpiredProjection] of [
  ['pending', -7, true], ['pending', 1, false], ['succeeded', -7, false], ['retry_wait', -7, true]
]) {
  test(`${status} task with deadline ${daysFromNow} days from now preserves history and projects expiry only for waiting tasks`, async () => {
    const methods = [], deadline = new Date(Date.now() + daysFromNow * 86400000).toISOString();
    const task = { task_id: 'task-history', kind: 'deliver_reminder', owner_module: 'O', status, attempt_count: status === 'pending' ? 0 : 1, max_attempts: 3,
      scheduled_at: new Date(new Date(deadline).getTime() - 1800000).toISOString(), valid_until: deadline, failure_reason: null, meta: { revision: 2, is_simulated: true } };
    const env = setup(async (url, options) => { methods.push(options.method); return success({ items: [task], next_cursor: null }); });
    await env.app.taskView();
    const text = env.roots['#main'].textContent;
    assert.equal(text.includes('已过有效期'), expectedExpiredProjection);
    assert.equal(text.includes('历史待显式维护'), expectedExpiredProjection);
    assert.equal(task.status, status); assert.equal(task.valid_until, deadline);
    assert.equal(text.includes('有效期至'), true);
    if (status === 'succeeded') assert.equal(text.includes('执行成功'), true);
    assert.deepEqual(methods, ['GET']);
  });
}
