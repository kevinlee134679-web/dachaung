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
  focus() {}
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
  const stored = new Map(), savedSession = new Map(), navButtons = [];
  const storage = values => ({ getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)), removeItem: key => values.delete(key) });
  const context = vm.createContext({ Node: Element, FormData: Form, TextEncoder, Uint8Array, ArrayBuffer,
    AbortController, setTimeout, clearTimeout, URL, Blob, Intl, crypto, fetch,
    localStorage: storage(stored), sessionStorage: storage(savedSession),
    document: { createElement: tag => new Element(tag), createTextNode: text => new Element('#text', String(text)),
      querySelector: selector => roots[selector], querySelectorAll: selector => selector === 'nav button' ? navButtons : [] } });
  const source = fs.readFileSync(path.join(__dirname, '..', 'medplatform', 'static', 's02.js'), 'utf8');
  const support = fs.readFileSync(path.join(__dirname, '..', 'medplatform', 'static', 's04.js'), 'utf8');
  const social = fs.readFileSync(path.join(__dirname, '..', 'medplatform', 'static', 's05.js'), 'utf8');
  const drafts = fs.readFileSync(path.join(__dirname, '..', 'medplatform', 'static', 's05_drafts.js'), 'utf8');
  const cutoff = source.lastIndexOf('for (const b of document.querySelectorAll');
  assert.ok(cutoff > 0);
  vm.runInContext(source.slice(0, cutoff), context);
  vm.runInContext(support + '\nglobalThis.frontend = {state,api,button,identity,navigate,render,fileView,questionnaireView,familyView,supportMessage,invitationList,homeSupportOverview};', context);
  vm.runInContext(social, context);
  vm.runInContext(drafts + '\nObject.assign(globalThis.frontend, {restoreServicePage});', context);
  const app = context.frontend;
  function choose(patient = 'pa', account = 'account-a') {
    const access = { patient: { patient_id: patient, display_name: patient, timezone: 'Asia/Shanghai' }, relationship: 'self',
      effective_scopes: ['files:write', 'files:read', 'medication:read', 'medication:edit', 'questionnaire:assist', 'knowledge:read'] };
    app.state.context = { account: { account_id: account, display_name: account }, current_patient_id: patient, patients: [access], csrf_token: 'csrf-' + account };
    app.state.patient = access;
  }
  choose();
  return { app, roots, stored, savedSession, choose, navButtons };
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

test('header logout follows its session through navigation and clears the current page on success', async () => {
  for (const account of ['demo-patient-a', 'demo-family', 'demo-admin']) {
    const sent = deferred(), response = deferred(), requests = [];
    const env = setup(async (url, options) => {
      requests.push([url, options.method, options.headers['X-CSRF-Token']]);
      sent.resolve();
      return response.promise;
    });
    env.choose('pa', account);
    if (account === 'demo-admin') {
      env.app.state.context.patients = [];
      env.app.state.patient = null;
    }
    env.app.identity();
    const logout = byText(env.roots['#identity'], 'button', '退出');
    await env.app.navigate('rewards');
    const pending = logout.click();
    await Promise.race([sent.promise, pending]);
    assert.deepEqual(requests, [['/api/v1/auth/logout', 'POST', 'csrf-' + account]]);
    await env.app.navigate('rewards');
    response.resolve(success({outcome: 'logged_out'}));
    await pending;
    assert.equal(env.app.state.context, null);
    assert.equal(env.app.state.patient, null);
    byText(env.roots['#main'], 'button', '管理自己的用药');
    assert.equal(env.roots['#notice'].textContent, '当前会话已退出。');
  }
});

test('a retained logout control cannot log out a replacement session on the same account', async () => {
  const requests = [];
  const env = setup(async url => { requests.push(url); return success({}); });
  env.app.identity();
  const oldLogout = byText(env.roots['#identity'], 'button', '退出');
  env.app.state.context.csrf_token = 'replacement-session-csrf';
  env.app.identity();
  await oldLogout.click();
  assert.deepEqual(requests, []);
  assert.equal(env.app.state.context.csrf_token, 'replacement-session-csrf');
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
    if (options.method !== 'GET') {
      const body = JSON.parse(options.body);
      writes.push(body);
      grant.scopes = body.scopes;
      return success(grant);
    }
    if (url.includes('/family-bindings')) return success({ items: [{ binding_id: 'binding-a', family_account_id: 'demo-family', status: 'active' }], next_cursor: null });
    if (url.includes('/grants')) return success({ items: [grant], next_cursor: null });
    if (url.endsWith('/auth/me')) return success(env.app.state.context);
    return success({});
  });
  env.app.state.page = 'profile'; env.app.state.tab = 'family';
  await env.app.familyView();
  return { ...env, writes, grant };
}
test('patient can explicitly grant and remove dialogue reading and see the saved scope', async () => {
  const env = await grantEnvironment();
  const main = env.roots['#main'];
  const label = '支持对话历史（只读）';
  const dialogueCheck = () => {
    const field = find(main, node => node.tagName === 'LABEL' && node.children[1]?.textContent === label);
    assert.ok(field);
    return field.children[0];
  };
  assert.equal(dialogueCheck().checked, false);
  dialogueCheck().checked = true;
  await byText(main, 'button', '明确确认并保存授权').click();
  assert.deepEqual(env.writes[0].scopes, ['patient:read', 'dialogue:read']);
  assert.equal(env.writes[0].confirmed, true);
  assert.equal(dialogueCheck().checked, true);
  byText(main, 'p', '授权：有效，基础资料查看、支持对话历史（只读）');
  dialogueCheck().checked = false;
  await byText(main, 'button', '明确确认并保存授权').click();
  assert.deepEqual(env.writes[1].scopes, ['patient:read']);
  assert.equal(dialogueCheck().checked, false);
  byText(main, 'p', '授权：有效，基础资料查看');
});

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

const catalogResource = {
  resource_id: 'demo-resource', resource_version: 'demo-v2', name: '药学咨询资源（模拟）',
  description: '演示资源介绍', provider: {display_name: '虚构主体（模拟）', qualification_status: 'not_verified'},
  required_shared_categories: ['support_question'], optional_shared_categories: ['medication_plan']
};
const recommendation = {
  need_status: 'needed', primary_action: {resource_id: 'demo-resource', title: catalogResource.name, reason: '符合本次需求。'},
  secondary_actions: [], missing_items: [],
  source_refs: [
    {module: 'O', record_kind: 'profile', record_id: 'o-profile-a', version: '1'},
    {module: 'C', record_kind: 'support_resource', record_id: 'demo-resource', version: 'demo-v2'}
  ]
};

test('S05 catalog and matching show exact source versions and browse only with GET', async () => {
  const gets = [];
  const env = setup(async (url, options) => {
    gets.push([url, options.method, options.headers['Idempotency-Key']]);
    if (url.endsWith('need=professional')) return success(recommendation);
    if (url.endsWith('/demo-resource')) return success(catalogResource);
    return success({items: [catalogResource], next_cursor: null});
  });
  env.app.state.patient.effective_scopes.push('support:read', 'profile:read');
  await env.app.navigate('support', 'social');
  const main = env.roots['#main'];
  byText(main, 'button', '查看已登记画像');
  const need = fieldControl(main, '本次支持需求');
  need.value = 'professional';
  await byText(main, 'button', '查看匹配').click();
  assert.match(main.textContent, /O 画像 o-profile-a · 修订 1/);
  assert.match(main.textContent, /符合本次需求。版本 demo-v2 · mock\/demo/);
  await byText(main, 'button', '查看候选详情').click();
  assert.match(main.textContent, /资质未核验/);
  assert.match(main.textContent, /潜在的必要共享类别　支持问题/);
  assert.deepEqual(gets, [
    ['/api/v1/support-resources', 'GET', undefined],
    ['/api/v1/patients/pa/support-recommendations?need=professional', 'GET', undefined],
    ['/api/v1/support-resources/demo-resource', 'GET', undefined]
  ]);
});

test('S05 ignores a delayed matching result after the selected need or patient changes', async () => {
  const response = deferred();
  const env = setup(async url => url.includes('support-recommendations') ? response.promise :
    success({items: [], next_cursor: null}));
  env.app.state.patient.effective_scopes.push('support:read');
  await env.app.navigate('support', 'social');
  const main = env.roots['#main'];
  const need = fieldControl(main, '本次支持需求');
  const pending = byText(main, 'button', '查看匹配').click();
  need.value = 'none';
  need.change();
  response.resolve(success(recommendation));
  await pending;
  assert.doesNotMatch(main.textContent, /o-profile-a|匹配结果/);
  const button = byText(main, 'button', '查看匹配');
  env.choose('pb');
  await env.app.navigate('support', 'social');
  await button.click();
  assert.doesNotMatch(main.textContent, /o-profile-a|本次支持需求/);
  assert.match(main.textContent, /获准查看社会支持/);
});

test('S05 stale resource version is reported and never labeled as the prior match', async () => {
  const env = setup(async url => {
    if (url.includes('support-recommendations')) return success(recommendation);
    if (url.endsWith('/demo-resource')) return success({...catalogResource, resource_version: 'demo-v3'});
    return success({items: [catalogResource], next_cursor: null});
  });
  env.app.state.patient.effective_scopes.push('support:read');
  await env.app.navigate('support', 'social');
  const main = env.roots['#main'];
  await byText(main, 'button', '查看匹配').click();
  await byText(main, 'button', '查看候选详情').click();
  assert.match(env.roots['#notice'].textContent, /版本已更新/);
  assert.doesNotMatch(main.textContent, /演示资源介绍|demo-v3/);
});

test('S05 patient can explicitly grant and remove support:read independently of profile:read', async () => {
  const env = await grantEnvironment();
  const main = env.roots['#main'];
  const supportCheck = () => find(main, n => n.tagName === 'LABEL' && n.children[1]?.textContent === '社会支持目录和候选（只读）').children[0];
  assert.equal(supportCheck().checked, false);
  supportCheck().checked = true;
  await byText(main, 'button', '明确确认并保存授权').click();
  assert.deepEqual(env.writes[0].scopes, ['patient:read', 'support:read']);
  assert.equal(supportCheck().checked, true);
  supportCheck().checked = false;
  await byText(main, 'button', '明确确认并保存授权').click();
  assert.deepEqual(env.writes[1].scopes, ['patient:read']);
});

function draftPage({family = false, conflict = false, lost = false} = {}) {
  const calls = [];
  const resource = {...catalogResource, service_kind: 'pharmacist_consultation'};
  let draft = {
    service_draft_id: 'draft-a', patient_id: 'pa', draft_revision: 1, ...resource,
    request_text: '原问题', status: 'preparing', confirmation_ref_id: null, meta: {revision: 1}
  };
  let consent = {
    confirmation_ref_id: 'confirm-a', resource_version: resource.resource_version, status: 'active',
    confirmed_at: '2026-11-18T00:00:00Z', valid_until: '2026-11-19T00:00:00Z', meta: {revision: 1},
    sharing_scope: {
      recipient_id: 'mock-subject', purpose_code: 'pharmacist_consultation', data_categories: ['support_question']
    }
  };
  const env = setup(async (url, options) => {
    const body = options.body ? JSON.parse(options.body) : null;
    calls.push({url, method: options.method, body, key: options.headers['Idempotency-Key']});
    if (url.endsWith('/demo-resource')) return success(resource);
    if (url.endsWith('/support-resources')) return success({items: [resource], next_cursor: null});
    if (url.endsWith('/service-drafts')) {
      if (lost) { lost = false; throw new Error('网络断开'); }
      draft = {...draft, ...body};
      return success(draft);
    }
    if (url.endsWith('/service-drafts/draft-a') && options.method === 'PUT') {
      if (conflict) {
        conflict = false;
        draft = {...draft, request_text: '服务器较新内容', draft_revision: 2, meta: {revision: 2}};
        return failure(409, 'SERVICE_DRAFT_REVISION_CONFLICT', '草稿已更新');
      }
      draft = {...draft, ...body.content, draft_revision: draft.draft_revision + 1, meta: {revision: draft.meta.revision + 1}};
      return success(draft);
    }
    if (url.endsWith('/service-drafts/draft-a')) return success(draft);
    if (url.endsWith('/service-confirmations')) {
      consent = {...consent, sharing_scope: {...consent.sharing_scope, data_categories: body.shared_categories}};
      draft = {...draft, confirmation_ref_id: 'confirm-a'};
      return success(consent);
    }
    if (url.endsWith('/service-confirmations/confirm-a/revoke')) {
      consent = {...consent, status: 'revoked', meta: {revision: 2}};
      draft = {...draft, confirmation_ref_id: null};
      return success(consent);
    }
    if (url.endsWith('/service-confirmations/confirm-a')) return success(consent);
    throw new Error('Unexpected request ' + url);
  });
  env.app.state.patient.relationship = family ? 'family' : 'self';
  env.app.state.patient.effective_scopes.push('support:read', 'services:prepare');
  return {...env, calls};
}

async function prepareDraft(env) {
  await env.app.navigate('support', 'social');
  const main = env.roots['#main'];
  await byText(main, 'button', '查看资源详情').click();
  await byText(main, 'button', '准备服务问题').click();
  return main;
}

function checkboxFor(main, label) {
  return byText(main, 'label', label).children[0];
}

test('S05 family prepares a manual draft and restores it without confirmation or revoke controls', async () => {
  const env = draftPage({family: true}), main = await prepareDraft(env);
  fieldControl(main, '本次服务问题').value = '家属据实代录';
  await byText(main, 'button', '保存草稿').click();
  assert.match(main.textContent, /草稿编号 draft-a/);
  assert.doesNotMatch(main.textContent, /明确确认共享范围|撤销共享授权/);
  assert.deepEqual(env.calls.find(c => c.method === 'POST').body,
    {resource_id: 'demo-resource', resource_version: 'demo-v2', request_text: '家属据实代录'});
  env.app.state.page = 'home'; env.app.state.tab = 'overview';
  assert.equal(await env.app.restoreServicePage(), true);
  assert.equal(fieldControl(main, '本次服务问题').value, '家属据实代录');
});

test('S05 stale draft edit reloads revisions while preserving the unsaved text', async () => {
  const env = draftPage({conflict: true}), main = await prepareDraft(env);
  fieldControl(main, '本次服务问题').value = '首次录入';
  await byText(main, 'button', '保存草稿').click();
  fieldControl(main, '本次服务问题').value = '此项修改应保留';
  await byText(main, 'button', '保存草稿修改').click();
  assert.equal(fieldControl(main, '本次服务问题').value, '此项修改应保留');
  assert.match(main.textContent, /内容修订 2/);
  await byText(main, 'button', '保存草稿修改').click();
  const writes = env.calls.filter(c => c.method === 'PUT');
  assert.deepEqual(writes.map(c=>c.body.expected_revision), [1, 2]);
  assert.equal(writes[1].body.content.request_text, '此项修改应保留');
});

test('S05 explicit patient confirmation submits only checked options and retains revoked history', async () => {
  const env = draftPage(), main = await prepareDraft(env);
  fieldControl(main, '本次服务问题').value = '本人核对的演示问题';
  await byText(main, 'button', '保存草稿').click();
  assert.equal(checkboxFor(main, '正式用药安排').checked, false);
  await byText(main, 'button', '明确确认共享范围').click();
  assert.equal(env.calls.some(c=>c.url.endsWith('/service-confirmations')), false);
  checkboxFor(main, '正式用药安排').checked = true;
  checkboxFor(main, '我已核对本次问题、接收主体和共享范围').checked = true;
  await byText(main, 'button', '明确确认共享范围').click();
  const issued = env.calls.find(c => c.url.endsWith('/service-confirmations'));
  assert.deepEqual(issued.body.shared_categories, ['medication_plan', 'support_question']);
  assert.equal(issued.body.draft_revision, 1);
  await byText(main, 'button', '查看确认及历史').click();
  fieldControl(main, '撤销原因').value = '只限演示';
  checkboxFor(main, '明确撤销此共享范围').checked = true;
  await byText(main, 'button', '撤销共享授权').click();
  assert.match(main.textContent, /共享确认：已撤销/);
  assert.doesNotMatch(main.textContent, /撤销共享授权/);
  await byText(main, 'button', 'confirm-a').click();
  assert.match(main.textContent, /共享确认：已撤销/);
});

test('S05 unknown draft write uses the original key and blocks a changed request', async () => {
  const env = draftPage({lost: true}), main = await prepareDraft(env);
  const text = fieldControl(main, '本次服务问题');
  const send = byText(main, 'button', '保存草稿');
  text.value = '原提交正文';
  await send.click();
  text.value = '另一个正文';
  await send.click();
  const posted = () => env.calls.filter(c => c.method === 'POST');
  assert.equal(posted().length, 1);
  assert.match(env.roots['#notice'].textContent, /上一次提交结果尚未核实/);
  text.value = '原提交正文';
  await send.click();
  assert.equal(posted().length, 2);
  assert.equal(posted()[0].key, posted()[1].key);
  assert.match(main.textContent, /草稿编号 draft-a/);
  assert.ok([...env.stored.values()].every(value => !value.includes('原提交正文')));
});

test('S07 home reads authoritative support and service status without writes or markup execution', async () => {
  const calls=[];
  const env=setup(async (url,options)=>{
    calls.push([url,options.method]);
    if(url.includes('support-recommendations')) return success({need_status:'identified',primary_action:{title:'<img src=x onerror=evil()>',reason:'明确需求'},secondary_actions:[]});
    return success({items:[{service_id:'service-a',service_name:'虚构服务',status:'in_progress'}],next_cursor:null});
  });
  env.app.state.patient.effective_scopes.push('support:read','services:read');
  await env.app.homeSupportOverview();
  assert.match(env.roots['#main'].textContent,/虚构服务 · 模拟处理中/);
  assert.match(env.roots['#main'].textContent,/<img src=x onerror=evil\(\)>/);
  assert.equal(find(env.roots['#main'],n=>n.tagName==='IMG'),null);
  assert.ok(calls.every(([,method])=>method==='GET'));
});

test('S07 home does not request support facts without their exact scopes', async () => {
  const calls=[];
  const env=setup(async url=>{calls.push(url);return success({});});
  await env.app.homeSupportOverview();
  assert.deepEqual(calls,[]);
});

test('S07 home discards delayed service content after switching patient', async () => {
  const response=deferred(),calls=[];
  const env=setup(async url=>{calls.push(url);return response.promise;});
  env.app.state.patient.effective_scopes.push('services:read');
  const pending=env.app.homeSupportOverview();
  env.choose('pb');env.app.state.epoch++;env.roots['#main'].replaceChildren();
  response.resolve(success({items:[{service_id:'old',service_name:'PRIVATE_OLD_PATIENT',status:'completed'}],next_cursor:null}));
  await assert.rejects(pending,error=>error.constructor.name==='ViewChanged');
  assert.doesNotMatch(env.roots['#main'].textContent,/PRIVATE_OLD_PATIENT/);
  assert.deepEqual(calls,['/api/v1/patients/pa/services?limit=3&order=desc']);
});

test('S07 navigation cannot interrupt a pending patient switch and retain the previous own controls', async () => {
  const sent=deferred(), reply=deferred();
  let changed=false;
  const env=setup(async (url,options)=>{
    if(url.endsWith('/auth/current-patient')){sent.resolve();const result=await reply.promise;changed=true;return result;}
    if(url.endsWith('/auth/me')){
      assert.equal(changed,true);
      const access={patient:{patient_id:'pb',display_name:'family target',timezone:'Asia/Shanghai'},relationship:'family',effective_scopes:[]};
      return success({...env.app.state.context,current_patient_id:'pb',patients:[access]});
    }
    return success({items:[],next_cursor:null});
  });
  env.app.state.page='profile';
  const nav=new Element('button');nav.dataset={page:'support'};env.navButtons.push(nav);
  env.app.identity();
  const picker=find(env.roots['#identity'],n=>n.tagName==='SELECT');picker.value='pb';
  const pending=picker.change();await sent.promise;
  assert.equal(nav.disabled,true);
  const epoch=env.app.state.epoch;
  await env.app.navigate('support');
  const afterNavigation=env.app.state.epoch;
  reply.resolve(success({outcome:'selected'}));await pending;
  assert.equal(afterNavigation,epoch,'navigation must not invalidate the switch response');
  assert.equal(env.app.state.patient.patient.patient_id,'pb');
  assert.equal(env.app.state.patient.relationship,'family');
  assert.equal(nav.disabled,false);
  assert.doesNotMatch(env.roots['#main'].textContent,/开始自由对话|打开虚构案例会话/);
  await env.app.navigate('support');
  assert.equal(env.app.state.page,'support','navigation resumes after switch');
});

test('S07 rejected patient switch releases navigation and preserves the last authorized context', async () => {
  const env=setup(async ()=>failure(403,'FORBIDDEN','无该对象权限'));
  env.app.state.page='profile';
  const nav=new Element('button');nav.dataset={page:'support'};env.navButtons.push(nav);
  env.app.identity();
  const picker=find(env.roots['#identity'],n=>n.tagName==='SELECT');picker.value='pb';
  await picker.change();
  assert.equal(env.app.state.switchingPatient,false);
  assert.equal(nav.disabled,false);
  assert.equal(env.app.state.patient.patient.patient_id,'pa');
  await env.app.navigate('support');
  assert.equal(env.app.state.page,'support');
});
