// Pure frontend logic tests using Node built-ins; no browser/build dependency.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const { webcrypto } = require('node:crypto');

class Element {
  constructor(tag, text = '') {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.events = {};
    this.attributes = {};
    this.value = '';
    this.type = '';
    this.checked = false;
    this.disabled = false;
    this.className = '';
    this.style = {};
    this.files = [];
    this._text = text;
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = []; this._text = ''; this.append(...nodes); }
  addEventListener(name, action) { this.events[name] = action; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; }
  querySelector(selector) {
    if (selector.startsWith('.')) return find(this, node => node.className.split(' ').includes(selector.slice(1)));
    const [, tag, attr] = /^(\w+)\[([\w-]+)\]$/.exec(selector);
    return find(this, node => node.tagName === tag.toUpperCase() && node.getAttribute(attr) !== null);
  }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(''); }
  set textContent(text) { this._text = text; this.children = []; }
  get firstChild() { return this.children[0]; }
  get childNodes() { return this.children; }
  click() { return this.events.click?.({ currentTarget: this }); }
  change() { return this.events.change?.({ currentTarget: this }); }
  input() { return this.events.input?.({ currentTarget: this }); }
}
class Form {
  constructor() { this.fields = new Map(); }
  append(name, value) { this.fields.set(name, value); }
  get(name) { return this.fields.get(name); }
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function success(data) { return { ok: true, status: 200, json: async () => ({ status: 'success', data, error: null }) }; }
function failure(status, code, message) { return { ok: false, status, json: async () => ({ status: 'error', data: null, error: { code, message } }) }; }
function find(node, predicate) {
  if (predicate(node)) return node;
  for (const child of node.children) { const result = find(child, predicate); if (result) return result; }
  return null;
}
function byText(root, tag, text) {
  const node = find(root, n => n.tagName === tag.toUpperCase() && n.textContent === text);
  assert.ok(node, `${tag} ${text} not found`);
  return node;
}
function fieldControl(root, label) {
  const node = find(root, n => n.tagName === 'LABEL' && n.children[0]?.textContent === label);
  assert.ok(node, `field ${label} not found`);
  return node.children[1];
}
function setup(fetch, crypto = webcrypto) {
  const roots = Object.fromEntries(['#main', '#identity', '#notice', '#health', '#refresh'].map(k => [k, new Element('div')]));
  const stored = new Map(), savedSession = new Map();
  const storage = values => ({ getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)), removeItem: key => values.delete(key) });
  const context = vm.createContext({ Node: Element, FormData: Form, TextEncoder, Uint8Array, ArrayBuffer,
    AbortController, setTimeout, clearTimeout, URL, Blob, Intl, crypto, fetch,
    localStorage: storage(stored), sessionStorage: storage(savedSession),
    document: { createElement: tag => new Element(tag), createTextNode: text => new Element('#text', String(text)),
      querySelector: selector => roots[selector], querySelectorAll: () => [] } });
  const source = fs.readFileSync(path.join(__dirname, '..', 'medplatform', 'static', 's02.js'), 'utf8');
  const support = fs.readFileSync(path.join(__dirname, '..', 'medplatform', 'static', 's04.js'), 'utf8');
  const cutoff = source.lastIndexOf('for (const b of document.querySelectorAll');
  assert.ok(cutoff > 0);
  vm.runInContext(source.slice(0, cutoff), context);
  vm.runInContext(support + '\nglobalThis.frontend = {state,api,button,render,fileView,questionnaireView,familyView,supportMessage,invitationList};', context);
  const app = context.frontend;
  function choose(patient = 'pa', account = 'account-a') {
    const access = { patient: { patient_id: patient, display_name: patient, timezone: 'Asia/Shanghai' }, relationship: 'self',
      effective_scopes: ['files:write', 'files:read', 'medication:read', 'medication:edit', 'questionnaire:assist', 'knowledge:read'] };
    app.state.context = { account: { account_id: account, display_name: account }, current_patient_id: patient, patients: [access], csrf_token: 'csrf-' + account };
    app.state.patient = access;
  }
  choose();
  return { app, roots, stored, savedSession, choose };
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('async fingerprint preparation never sends with a changed account/patient', async () => {
  const digest = deferred(), calls = [];
  const env = setup(async (...args) => { calls.push(args); return success({}); },
    { randomUUID: () => 'operation-id', subtle: { digest: () => digest.promise } });
  const pending = env.app.api('/patients/pa/medications', 'POST', { name: 'fictional A' });
  env.choose('pb', 'account-b'); env.app.state.epoch++;
  digest.resolve(new Uint8Array(32).buffer);
  await assert.rejects(pending, error => error.constructor.name === 'ViewChanged');
  assert.equal(calls.length, 0);
});

test('file preparation retains the initiating patient and cancels after patient switch', async () => {
  const bytes = deferred(), posts = [];
  const env = setup(async (url, options) => {
    if (options.method === 'GET') return success({ items: [], next_cursor: null });
    posts.push(url); return success({ file_id: 'saved' });
  });
  await env.app.fileView();
  const chooser = find(env.roots['#main'], n => n.type === 'file');
  chooser.files = [{ name: 'fictional-A.pdf', arrayBuffer: () => bytes.promise }];
  const pending = byText(env.roots['#main'], 'button', '上传资料').click();
  env.choose('pb'); env.app.state.epoch++;
  bytes.resolve(new Uint8Array([1, 2, 3]).buffer);
  await pending;
  assert.deepEqual(posts, []);
});

test('a stale form control cannot start another action after view change', async () => {
  let effects = 0;
  const env = setup(async () => success({}));
  const oldButton = env.app.button('save', async () => { effects++; });
  env.app.state.epoch++;
  await oldButton.click();
  assert.equal(effects, 0);
});

test('subpage change invalidates a delayed old medication list', async () => {
  const response = deferred();
  const knowledgeRequests = [];
  const env = setup(async url => {
    if (url.includes('/medications')) return response.promise;
    if (url.startsWith('/api/v1/knowledge')) knowledgeRequests.push(url);
    return success({items: [], next_cursor: null});
  });
  env.app.state.page = 'medication'; env.app.state.tab = 'meds';
  const pending = env.app.render();
  await tick();
  await byText(env.roots['#main'], 'button', '药学知识').click();
  response.resolve(success({ items: [{ medication_id: 'old-med', name: 'STALE_MEDICATION', notes: null }], next_cursor: null }));
  await pending;
  assert.equal(env.roots['#main'].textContent.includes('STALE_MEDICATION'), false);
  assert.deepEqual(knowledgeRequests, ['/api/v1/knowledge?kind=medical&limit=100']);
  byText(env.roots['#main'], 'p', '目前没有适用的审核药学资料。用药问题请向实际医生或药师核实。');
});

test('support reply renders model markup as literal text', () => {
  const env = setup(async () => success({}));
  const markup = '<img src="x" onerror="evil()">';
  const card = env.app.supportMessage({}, {role: 'assistant', content: markup}, false);
  assert.equal(card.textContent.includes(markup), true);
  assert.equal(find(card, node => node.tagName === 'IMG'), null);
});

test('an expired pending support invitation has no acceptance control', () => {
  const env = setup(async () => success({}));
  const section = env.app.invitationList([{
    status: 'pending', invitation_id: 'test', title: '支持邀请', description: '可自行选择',
    valid_until: '2026-11-17T12:00:00Z',
  }], '2026-11-17T12:00:00Z');
  assert.equal(section.textContent.includes('已到期'), true);
  assert.equal(find(section, node => node.tagName === 'BUTTON'), null);
});

async function openComposer(onRequest) {
  const session = {session_id: 'support-s', turn_count: 2, status: 'active', ui_mode: 'normal', meta: {revision: 1}};
  const events = [];
  const env = setup(async (url, options) => {
    events.push([options.method, url]);
    if (url === '/api/v1/sessions?patient_id=pa&limit=100') return success({items: [session], next_cursor: null});
    if (url === '/api/v1/sessions/support-s/messages?limit=100') return success({items: [], next_cursor: null});
    return onRequest(url, options, session);
  });
  env.app.state.page = 'support';
  env.app.state.patient.effective_scopes.push('dialogue:read');
  await env.app.render();
  const main = env.roots['#main'];
  return { ...env, events, editor: () => fieldControl(main, '你想说的话'),
    click: label => byText(main, 'button', label).click() };
}

test('rejected support turn with absent original refreshes the session and waits for explicit resend', async () => {
  const posts = [];
  const env = await openComposer(async (url, options, session) => {
    if (options.method === 'GET') {
      assert.equal(url, '/api/v1/sessions/support-s/messages?client_message_id=' + posts[0].body.client_message_id);
      return failure(404, 'RESOURCE_NOT_FOUND');
    }
    posts.push({body: JSON.parse(options.body), key: options.headers['Idempotency-Key']});
    if (posts.length === 1) {
      session.turn_count = 3;
      return failure(409, 'SESSION_REVISION_CONFLICT');
    }
    assert.equal(posts.at(-1).body.expected_turn_count, session.turn_count);
    session.turn_count++;
    return success({});
  });
  env.editor().value = '留在页面内的草稿';
  const originalEditor = env.editor();
  await env.click('发送');
  assert.equal(posts.length, 1);
  assert.equal(env.events.filter(([, url]) => url.startsWith('/api/v1/sessions?')).length, 2);
  assert.notEqual(env.editor(), originalEditor);
  assert.equal(env.editor().value, '留在页面内的草稿');
  assert.match(env.roots['#notice'].textContent, /再次点击发送/);
  assert.equal(env.savedSession.size, 0);
  assert.equal(env.stored.size, 0);
  await env.click('发送');
  assert.deepEqual(posts.map(p => p.body.expected_turn_count), [2, 3]);
  assert.equal(posts[1].body.content, posts[0].body.content);
  assert.notEqual(posts[1].body.client_message_id, posts[0].body.client_message_id);
  assert.notEqual(posts[1].key, posts[0].key);
});

test('lookup of an in-flight support submission preserves its ID and never starts another generation', async () => {
  let posted, count = 0, generationStatus = 'running';
  const env = await openComposer(async (url, options, session) => {
    if (options.method === 'POST') {
      count++;
      posted = JSON.parse(options.body);
      session.turn_count = 3;
      return failure(409, 'OPERATION_IN_PROGRESS');
    }
    assert.equal(url, '/api/v1/sessions/support-s/messages?client_message_id=' + posted.client_message_id);
    return success({items: [{generation_status: generationStatus}]});
  });
  env.editor().value = '发送中的消息';
  await env.click('发送');
  assert.equal(JSON.parse([...env.savedSession.values()][0]).id, posted.client_message_id);
  assert.equal(env.stored.size, 1);
  generationStatus = 'completed';
  await env.click('核查原消息');
  assert.equal(count, 1);
  assert.equal(env.savedSession.size, 0);
  assert.equal(env.roots['#notice'].textContent, '已核对原消息。');
});

test('support timeout and absent lookup retain the original turn and both idempotency identifiers', async () => {
  const posts = [];
  const env = await openComposer(async (url, options) => {
    if (options.method === 'GET') {
      assert.equal(url, '/api/v1/sessions/support-s/messages?client_message_id=' + JSON.parse(posts[0].body).client_message_id);
      return failure(404, 'RESOURCE_NOT_FOUND');
    }
    posts.push({body: options.body, key: options.headers['Idempotency-Key']});
    if (posts.length === 1) throw Object.assign(new Error('test abort'), {name: 'AbortError'});
    return success({});
  });
  env.editor().value = '结果尚待核对的消息';
  await env.click('发送');
  assert.match(env.roots['#notice'].textContent, /等待超时/);
  assert.equal(JSON.parse([...env.savedSession.values()][0]).id, JSON.parse(posts[0].body).client_message_id);
  await env.click('发送');
  assert.equal(posts.length, 2);
  assert.deepEqual(posts[1], posts[0]);
  assert.equal(env.savedSession.size, 0);
});

test('transient questionnaire restore failure preserves its saved reference', async () => {
  const env = setup(async url => url.includes('/questionnaires/initial')
    ? success({ purpose: 'fictional questionnaire', version: 'initial-v0.1', themes: [] })
    : failure(503, 'DEPENDENCY_NOT_READY', 'temporary storage failure'));
  const reference = 'reference:account-a:pa:questionnaire'; env.stored.set(reference, 'response-a');
  await assert.rejects(env.app.questionnaireView(), /temporary storage failure/);
  assert.equal(env.stored.get(reference), 'response-a');
});

test('old questionnaire restore cannot delete the newly selected patient reference', async () => {
  const response = deferred();
  const env = setup(async url => url.includes('/questionnaires/initial')
    ? success({ purpose: 'old questionnaire', version: 'initial-v0.1', themes: [] }) : response.promise);
  const a = 'reference:account-a:pa:questionnaire', b = 'reference:account-a:pb:questionnaire';
  env.stored.set(a, 'response-a'); env.stored.set(b, 'response-b');
  const pending = env.app.questionnaireView(); await tick();
  env.choose('pb'); env.app.state.epoch++;
  response.resolve(success({ response_id: 'response-a', status: 'draft', answers: {} }));
  await assert.rejects(pending, error => error.constructor.name === 'ViewChanged');
  assert.equal(env.stored.get(a), 'response-a'); assert.equal(env.stored.get(b), 'response-b');
});

test('unknown write result retains its original idempotency key for retry', async () => {
  const keys = []; let attempts = 0;
  const env = setup(async (url, options) => {
    keys.push(options.headers['Idempotency-Key']);
    if (!attempts++) throw new TypeError('connection interrupted');
    return success({ medication_id: 'original-result' });
  });
  await assert.rejects(env.app.api('/patients/pa/medications', 'POST', { name: 'same intent' }));
  await env.app.api('/patients/pa/medications', 'POST', { name: 'same intent' });
  assert.equal(keys[0], keys[1]);
  assert.equal(env.stored.size, 0);
});

async function expiredOperation(code) {
  const keys = []; let attempts = 0;
  const env = setup(async (url, options) => {
    keys.push(options.headers['Idempotency-Key']);
    return ++attempts < 3 ? failure(409, code, 'expired receipt') : success({ medication_id: 'explicit-new-result' });
  });
  const save = env.app.button('save', () => env.app.api('/patients/pa/medications', 'POST', { name: 'same intent' }));
  await save.click();
  const pendingKey = [...env.stored.keys()].find(key => key.startsWith('pending:'));
  assert.ok(pendingKey);
  return { ...env, keys, save, pendingKey };
}

for (const code of ['IDEMPOTENCY_EXPIRED', 'SENSITIVE_RECEIPT_EXPIRED']) {
  test(`${code} keeps the original key until explicit recovery and does not resend on recovery`, async () => {
    const env = await expiredOperation(code);
    const firstKey = env.keys[0];
    await env.save.click();
    assert.deepEqual(env.keys, [firstKey, firstKey]);
    env.stored.set('pending:another-operation', 'unrelated-key');
    const recovery = byText(env.roots['#notice'], 'button', '已核对原结果，准备新操作');
    await recovery.click();
    assert.equal(env.keys.length, 2);
    assert.equal(env.stored.has(env.pendingKey), false);
    assert.equal(env.stored.get('pending:another-operation'), 'unrelated-key');
    await env.save.click();
    assert.equal(env.keys.length, 3);
    assert.notEqual(env.keys[2], firstKey);
  });
}

test('expired-operation recovery cannot clear the key after patient/context change', async () => {
  const env = await expiredOperation('IDEMPOTENCY_EXPIRED');
  const recovery = byText(env.roots['#notice'], 'button', '已核对原结果，准备新操作');
  const original = env.stored.get(env.pendingKey);
  env.choose('pb'); env.app.state.epoch++;
  await recovery.click();
  assert.equal(env.stored.get(env.pendingKey), original);
  assert.equal(env.keys.length, 1);
});

test('expired-operation recovery cannot clear a replacement operation at the captured key', async () => {
  const env = await expiredOperation('SENSITIVE_RECEIPT_EXPIRED');
  const recovery = byText(env.roots['#notice'], 'button', '已核对原结果，准备新操作');
  env.stored.set(env.pendingKey, 'replacement-operation');
  await recovery.click();
  assert.equal(env.stored.get(env.pendingKey), 'replacement-operation');
  assert.equal(env.keys.length, 1);
});

async function grantEnvironment() {
  const writes = [];
  const grant = { grant_id: 'grant-a', binding_id: 'binding-a', status: 'active', valid_until: '2030-12-01T02:03:45.123456+00:00',
    scopes: ['patient:read'], meta: { revision: 2 } };
  const env = setup(async (url, options) => {
    if (options.method !== 'GET') { writes.push(JSON.parse(options.body)); return success(grant); }
    if (url.includes('/family-bindings')) return success({ items: [{ binding_id: 'binding-a', family_account_id: 'demo-family', status: 'active' }], next_cursor: null });
    if (url.includes('/grants')) return success({ items: [grant], next_cursor: null });
    if (url.endsWith('/auth/me')) return success(env.app.state.context);
    return success({});
  });
  env.app.state.page = 'profile'; env.app.state.tab = 'family';
  await env.app.familyView();
  return { ...env, writes, grant };
}
test('editing grant scopes keeps its exact current expiration by default', async () => {
  const env = await grantEnvironment();
  const deadline = fieldControl(env.roots['#main'], '授权截止时间（北京时间，留空表示无预设截止）');
  assert.equal(deadline.value, '2030-12-01T10:03');
  const scopeLabel = find(env.roots['#main'], n => n.tagName === 'LABEL' && n.children[1]?.textContent === '基础资料编辑');
  scopeLabel.children[0].checked = true;
  await byText(env.roots['#main'], 'button', '明确确认并保存授权').click();
  assert.equal(env.writes[0].scopes.includes('patient:edit'), true);
  assert.equal(env.writes[0].valid_until, env.grant.valid_until);
});
test('grant expiration is removed only by an explicit clear', async () => {
  const env = await grantEnvironment();
  const deadline = fieldControl(env.roots['#main'], '授权截止时间（北京时间，留空表示无预设截止）');
  deadline.value = ''; await deadline.input();
  await byText(env.roots['#main'], 'button', '明确确认并保存授权').click();
  assert.equal(env.writes[0].valid_until, null);
});
test('an explicit grant expiration change is sent with its timezone', async () => {
  const env = await grantEnvironment();
  const deadline = fieldControl(env.roots['#main'], '授权截止时间（北京时间，留空表示无预设截止）');
  deadline.value = '2031-01-02T15:16'; await deadline.input();
  await byText(env.roots['#main'], 'button', '明确确认并保存授权').click();
  assert.equal(env.writes[0].valid_until, '2031-01-02T07:16:00.000Z');
});
