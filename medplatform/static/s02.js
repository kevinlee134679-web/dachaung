"use strict";
const state = {
  context: null,
  patient: null,
  page: "home",
  tab: "overview",
  epoch: 0,
  response: null,
  question: 0,
  definition: null,
  draft: null
};
const main = document.querySelector("#main");
const titles = {
  home: "今天，从一件小事开始",
  medication: "用药管理",
  support: "支持服务",
  rewards: "积分权益",
  profile: "我的"
};
const accounts = [
  ["demo-patient-a", "演示患者甲"],
  ["demo-patient-b", "演示患者乙"],
  ["demo-family", "演示家人（也可管理自己）"],
  ["demo-admin", "演示管理员"]
];
const grantOptions = [
  ["patient:read", "基础资料查看"],
  ["patient:edit", "基础资料编辑"],
  ["questionnaire:read", "问卷读取"],
  ["questionnaire:assist", "协助问卷"],
  ["profile:read", "画像摘要"],
  ["medication:read", "药品资料查看"],
  ["medication:edit", "药品资料编辑"],
  ["plan:read", "正式安排查看"],
  ["reminder:read", "提醒查看"],
  ["reminder:write", "提醒编辑"],
  ["notify:receive", "接收相关通知"],
  ["files:read", "病历文件读取"],
  ["files:write", "病历文件上传"],
  ["drafts:read", "草稿查看"],
  ["drafts:write", "草稿编辑"],
  ["drafts:submit", "提交草稿供患者核对"]
];
const statusLabels = {
  editing: "编辑中",
  pending_confirmation: "等待本人核对",
  confirmed: "已取得正式计划引用",
  returned: "需修改资料",
  active: "有效",
  revoked: "已撤销",
  expired: "已到期"
};
class ViewChanged extends Error {}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "class") node.className = v;
    else if (k in node && !k.startsWith("aria")) node[k] = v;
    else node.setAttribute(k, v);
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}
const p = (text, cls = "") => el("p", {
  class: cls
}, text);

function button(text, fn, cls = "", disabled = false) {
  return el("button", {
    type: "button",
    class: cls,
    disabled,
    onclick: event => act(event.currentTarget, fn)
  }, text);
}

function field(label, input) {
  if (!["INPUT", "SELECT", "TEXTAREA"].includes(input.tagName)) {
    return el("fieldset", {}, el("legend", {}, label), input);
  }
  return el("label", {
    class: "field"
  }, el("span", {}, label), input);
}

function input(label, value = "", type = "text", attrs = {}) {
  const node = el("input", {
    type,
    value,
    ...attrs
  });
  return [field(label, node), node];
}

function select(label, options, value) {
  const node = el("select", {});
  for (const [code, text] of options) node.append(el("option", {
    value: code,
    selected: String(value) === String(code)
  }, text));
  return [field(label, node), node];
}

function checkbox(label, checked = false) {
  const node = el("input", {
    type: "checkbox",
    checked
  });
  return [el("label", {
    class: "check"
  }, node, el("span", {}, label)), node];
}

function notice(text, error = false) {
  const node = document.querySelector("#notice");
  node.textContent = text;
  node.className = error ? "error" : "success";
}
async function act(node, fn) {
  if (node.disabled) return;
  node.disabled = true;
  const epoch = state.epoch;
  try {
    await fn();
  } catch (error) {
    if (!(error instanceof ViewChanged) && epoch === state.epoch) notice(error.message || "操作未完成，请核查原结果后重试。", true);
  } finally {
    node.disabled = false;
  }
}
const scope = code => !!state.patient?.effective_scopes.includes(code);
const own = () => state.patient?.relationship === "self";
const patientPath = suffix => `/patients/${encodeURIComponent(state.patient.patient.patient_id)}${suffix}`;
const referenceKey = type => `reference:${state.context.account.account_id}:${state.patient.patient.patient_id}:${type}`;

function dateText(value) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: state.patient?.patient.timezone || "Asia/Shanghai"
  }).format(new Date(value));
}

function today() {
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(new Date());
}
async function sha(text) {
  const raw = typeof text === "string" ? new TextEncoder().encode(text) : text;
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", raw))].map(x => x.toString(16).padStart(2, "0")).join("");
}
async function api(path, method = "GET", body = null) {
  const epoch = state.epoch,
    headers = {},
    options = {
      method,
      headers,
      credentials: "same-origin",
      cache: "no-store"
    };
  let pending = null;
  if (method !== "GET") {
    let semantic;
    if (body instanceof FormData) {
      options.body = body;
      const file = body.get("file");
      semantic = String(body.get("source_event_id")) + file.name + await sha(await file.arrayBuffer());
    } else {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body ?? {});
      semantic = options.body;
    }
    pending = `pending:${state.context?.account.account_id||"anonymous"}:${method}:${path}:${await sha(semantic)}`;
    let operation = localStorage.getItem(pending);
    if (!operation) {
      operation = crypto.randomUUID();
      localStorage.setItem(pending, operation);
    }
    headers["Idempotency-Key"] = operation;
    if (state.context) headers["X-CSRF-Token"] = state.context.csrf_token;
  }
  const controller = new AbortController();
  options.signal = controller.signal;
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch("/api/v1" + path, options);
    const result = await response.json();
    if (epoch !== state.epoch) throw new ViewChanged();
    if (!response.ok || result.status !== "success") {
      if (pending && response.status < 500 && result.error?.code !== "OPERATION_IN_PROGRESS") localStorage.removeItem(pending);
      if (response.status === 401 && state.context) {
        state.context = null;
        state.patient = null;
        state.response = null;
        state.draft = null;
        identity();
        await render();
      }
      throw new Error(result.error?.message || "操作未完成，请重新检查。");
    }
    if (pending) localStorage.removeItem(pending);
    return result.data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("等待超时，结果尚未核实。请先刷新原资源；重试会沿用同一操作键。");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
async function all(path) {
  let items = [],
    cursor = null;
  do {
    const data = await api(path + (path.includes("?") ? "&" : "?") + "limit=100" + (cursor ? "&cursor=" + encodeURIComponent(cursor) : ""));
    items.push(...data.items);
    cursor = data.next_cursor;
  } while (cursor);
  return items;
}
async function context() {
  state.context = await api("/auth/me");
  state.patient = state.context.patients.find(x => x.patient.patient_id === state.context.current_patient_id) || null;
  identity();
}

function identity() {
  const area = document.querySelector("#identity");
  area.replaceChildren();
  if (!state.context) {
    area.append(p("选择一个虚构演示身份，资料仅保存在本地。"));
    return;
  }
  area.append(p(state.context.account.display_name));
  if (state.context.patients.length) {
    const picker = el("select", {
      "aria-label": "当前管理对象"
    }, el("option", {
      value: ""
    }, "请选择管理对象"));
    for (const item of state.context.patients) picker.append(el("option", {
      value: item.patient.patient_id,
      selected: state.patient?.patient.patient_id === item.patient.patient_id
    }, `${item.patient.display_name} · ${item.relationship==="self"?"本人":"家庭协助"}`));
    picker.addEventListener("change", () => act(picker, async () => {
      if (!picker.value) return;
      state.epoch++;
      state.response = null;
      state.draft = null;
      await api("/auth/current-patient", "PUT", {
        patient_id: picker.value
      });
      await context();
      await render();
      notice("已切换对象，旧表单已清除。");
    }));
    area.append(el("label", {}, "正在管理", picker));
  }
  area.append(button("退出", async () => {
    await api("/auth/logout", "POST", {});
    state.epoch++;
    state.context = null;
    state.patient = null;
    state.response = null;
    state.draft = null;
    identity();
    await render();
    notice("当前会话已退出。");
  }, "quiet"));
}

function loginView() {
  main.append(el("h1", {}, "从自己的安排开始，也可以帮助家人"), p("同一账号可以管理自己和已获授权的家人。演示身份不代表真实认证。"));
  const [label, chooser] = select("选择虚构身份", accounts, "demo-patient-a");
  async function enter(family) {
    await api("/auth/demo-session", "POST", {
      demo_account_id: chooser.value
    });
    await context();
    await navigate(family ? "profile" : "home", family ? "family" : "overview");
    notice("已进入演示，当前对象显示在页面上方。");
  }
  main.append(el("section", {class:"panel"}, label,
    el("div", {class:"actions"}, button("管理自己的用药",()=>enter(false),"primary"),
      button("帮助家人管理用药",()=>enter(true)))),
    p("首次使用需先按运行说明显式初始化数据库及演示身份；启动不会自动建立账号。", "muted"));
}
async function render() {
  const epoch = state.epoch;
  main.replaceChildren();
  if (!state.context) {
    loginView();
    return;
  }
  main.append(el("h1", {}, titles[state.page]));
  if (state.page === "support") {
    main.append(p("情感支持与社会支持将在后续阶段开放。当前尚未连接对话模型或实际服务方。"));
    return;
  }
  if (state.page === "rewards") {
    main.append(p("积分和自愿兑换将在后续阶段开放，当前没有生成余额、流水或兑换记录。"));
    return;
  }
  if (!state.patient) {
    main.append(p("请先在上方选择本人或已获授权的照护对象。"));
    if (state.page === "profile") await familyView();
    return;
  }
  const tabs = state.page === "medication" ? [
    ["overview", "今日安排"],
    ["meds", "药品资料"],
    ["files", "病历资料"],
    ["drafts", "资料核对"],
    ["reminders", "提醒设置"],
    ["knowledge", "药学知识"]
  ] : state.page === "profile" ? [
    ["overview", "个人资料"],
    ["questionnaire", "八题问卷"],
    ["assessment", "画像结果"],
    ["family", "家庭授权"]
  ] : [];
  if (tabs.length) {
    const nav = el("div", {
      class: "subnav",
      "aria-label": "当前页面功能"
    });
    for (const [code, label] of tabs) nav.append(button(label, async () => {
      state.tab = code;
      await render();
    }, state.tab === code ? "primary" : ""));
    main.append(nav);
  }
  try {
    if (state.page === "home") await homeView();
    else if (state.page === "medication") await ({
      overview: scheduleView,
      meds: medicationView,
      files: fileView,
      drafts: draftView,
      reminders: reminderView,
      knowledge: async()=>main.append(p("药学资料将复用同一份经过适用审核的知识来源。当前尚未接入B2资料，不能提供个体化药学指引；涉及用药疑问，请咨询实际医生或药师。"))
    } [state.tab] || scheduleView)();
    else await ({
      overview: patientView,
      questionnaire: questionnaireView,
      assessment: profileView,
      family: familyView
    } [state.tab] || patientView)();
  } catch (error) {
    if (epoch === state.epoch && !(error instanceof ViewChanged)) main.append(p(error.message, "error"));
  }
}
async function navigate(page, tab = "overview") {
  notice("");
  state.epoch++;
  state.page = page;
  state.tab = tab;
  state.draft = null;
  for (const b of document.querySelectorAll("nav button")) {
    if (b.dataset.page === page) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  await render();
}
async function homeView() {
  main.append(p(`当前对象：${state.patient.patient.display_name}。这里先整理你的回答、资料与安排，不评价是否足够自律。`), el("div", {
    class: "actions"
  }, button("填写八题问卷", () => navigate("profile", "questionnaire"), "primary", !scope("questionnaire:assist")), button("核对用药资料", () => navigate("medication", "drafts"), "", !scope("drafts:read")), button("设置提醒", () => navigate("medication", "reminders"), "", !scope("reminder:read"))), p("CAS、患者分类方法尚未适配。提醒当前只保存偏好，不会实际发送；用药确认与统计将在后续阶段开放。", "muted"));
  if (scope("plan:read")) await scheduleView();
}
async function patientView() {
  if (!scope("patient:read")) {
    main.append(p("当前未获基础资料查看权限。"));
    return;
  }
  const patient = await api(patientPath(""));
  const box = el("section", {}),
    [nl, name] = input("显示名称", patient.display_name),
    [zl, zone] = input("显示时区（IANA标识）", patient.timezone);
  box.append(nl, zl, p("显示时区只影响展示，不平移已经确认的计划。正式计划按北京时间核对。", "muted"), button("保存基础资料", async () => {
    await api(patientPath(""), "PATCH", {
      expected_revision: patient.meta.revision,
      display_name: name.value,
      timezone: zone.value
    });
    await context();
    await render();
    notice("基础资料已保存。");
  }, "primary", !scope("patient:edit")));
  main.append(box);
}
async function scheduleView() {
  if (!scope("plan:read")) {
    main.append(p("当前未获正式安排查看权限。"));
    return;
  }
  const [dl, day] = input("安排日期（北京时间）", today(), "date"), box = el("section", {}), list = el("div", {});
  async function load() {
    list.replaceChildren(p("正在读取安排…"));
    if (!day.value) return;
    const start = day.value + "T00:00:00+08:00",
      end = new Date(new Date(start).getTime() + 86400000).toISOString();
    const data = await api(patientPath("/dose-slots") + `?window_start=${encodeURIComponent(start)}&window_end=${encodeURIComponent(end)}`);
    list.replaceChildren();
    if (!data.items.length) list.append(p("这一天没有已物化的正式安排。未确认草稿不会出现在这里。", "empty"));
    const plans = await all(patientPath("/plans"));
    for (const slot of data.items) {
      const plan = plans.find(x => x.plan_id === slot.plan_id && x.plan_version === slot.plan_version),
        entry = plan?.entries.find(x => x.plan_entry_id === slot.plan_entry_id);
      list.append(el("div", {
        class: "item"
      }, el("strong", {}, entry?.medication_name_snapshot || "计划药品"), p(`${dateText(slot.scheduled_at)} · ${slot.status==="active"?"正式安排":"已被后续版本替代"}`), p(entry ? `原资料：${entry.dose_value} ${entry.dose_unit}` : "请查看计划原资料", "muted")));
    }
  }
  box.append(el("h2", {}, "已确认的安排"), dl, button("查看安排", load), list, p("此处展示计划时间，不推断已经服药、未服或漏服。", "muted"));
  main.append(box);
  await load();
}
async function medicationView() {
  if (!scope("medication:read")) {
    main.append(p("当前未获药品资料查看权限。"));
    return;
  }
  const meds = await all(patientPath("/medications")),
    box = el("section", {}),
    editor = el("div", {});

  function edit(med = null) {
    editor.replaceChildren(el("h2", {}, med ? "纠正药品资料" : "添加药品资料"));
    const [nl, name] = input("药品名称（按原资料核对）", med?.name || ""), notes = el("textarea", {
      value: med?.notes || ""
    });
    editor.append(nl, field("资料备注（可空）", notes), p("名称和备注不改变处方剂量或频次；正式安排需要另行提交草稿并核对。", "muted"), button("保存药品资料", async () => {
      const body = {
        name: name.value,
        notes: notes.value || null
      };
      if (med) body.expected_revision = med.meta.revision;
      await api(med ? `/medications/${med.medication_id}` : patientPath("/medications"), med ? "PATCH" : "POST", body);
      await render();
      notice("药品资料已保存。");
    }, "primary", !scope("medication:edit")));
  }
  if (scope("medication:edit")) edit();
  box.append(editor, el("h2", {}, "已有药品"));
  if (!meds.length) box.append(p("还没有药品资料。", "empty"));
  for (const med of meds) box.append(el("div", {
    class: "item"
  }, el("strong", {}, med.name), p(med.notes || "没有备注", "muted"), button("编辑资料", () => edit(med), "", !scope("medication:edit"))));
  main.append(box);
}
async function fileView() {
  const box = el("section", {});
  main.append(box);
  if (scope("files:write")) {
    const chooser = el("input", {
      type: "file",
      accept: ".pdf,.png,.jpg,.jpeg",
      "aria-label": "选择虚构病历文件"
    });
    box.append(el("h2", {}, "保存原始资料"), p("支持PDF、PNG、JPEG，最多10MiB。保存不代表已识别医嘱或确认计划。"), field("选择文件", chooser), button("上传资料", async () => {
      const file = chooser.files[0];
      if (!file) throw new Error("请先选择文件。");
      const hash = await sha(await file.arrayBuffer()),
        ref = `upload:${referenceKey("file")}:${hash}:${file.name}`;
      let source = localStorage.getItem(ref);
      if (!source) {
        source = crypto.randomUUID();
        localStorage.setItem(ref, source);
      }
      const form = new FormData();
      form.append("file", file);
      form.append("source_event_id", source);
      await api(patientPath("/files"), "POST", form);
      localStorage.removeItem(ref);
      await render();
      notice("原始资料已保存，尚未识别或确认计划。");
    }, "primary"));
  }
  if (!scope("files:read")) {
    box.append(p("当前未获原始病历读取权限。"));
    return;
  }
  const files = await all(patientPath("/files"));
  box.append(el("h2", {}, "已保存资料"));
  if (!files.length) box.append(p("还没有上传资料。", "empty"));
  for (const file of files) box.append(el("div", {
    class: "item"
  }, el("strong", {}, file.original_name), p(`${Math.ceil(file.size_bytes/1024)} KB · ${dateText(file.meta.created_at)} · 原文件已保存`, "muted"), button("下载核对原件", async () => {
    const data = await api(`/files/${file.file_id}/content`),
      bytes = Uint8Array.from(atob(data.content_base64), c => c.charCodeAt(0)),
      url = URL.createObjectURL(new Blob([bytes], {
        type: data.media_type
      }));
    el("a", {
      href: url,
      download: file.original_name
    }).click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  })));
}

function answerDefault(q) {
  return q === "Q1" ? {
    primary: null,
    additional: []
  } : q === "Q2" ? {
    selected: [],
    top_ranked: [],
    other_text: null
  } : q === "Q3" ? {
    choice: null
  } : q === "Q4" ? {
    selected: [],
    top_concerns: [],
    intensity: null
  } : q === "Q5" ? {
    selected: [],
    frequency: null
  } : q === "Q6" ? {
    confidence_level: null
  } : q === "Q7" ? {
    selected: []
  } : {
    selected: [],
    ranked: []
  };
}

function copyValue(value) {
  return JSON.parse(JSON.stringify(value));
}
async function questionnaireView() {
  if (!scope("questionnaire:assist")) {
    main.append(p("当前未获问卷作答权限。"));
    return;
  }
  state.definition = await api("/questionnaires/initial");
  const ref = localStorage.getItem(referenceKey("questionnaire"));
  if (!state.response && ref) {
    try {
      state.response = await api(`/questionnaire-responses/${ref}`);
      if (state.response.status === "draft") {
        const pending = Object.values(state.response.answers).findIndex(a => a.state === "not_answered");
        state.question = pending < 0 ? 7 : pending;
      }
    } catch {
      localStorage.removeItem(referenceKey("questionnaire"));
    }
  }
  if (!state.response) {
    main.append(el("section", {
      class: "panel"
    }, p(state.definition.purpose), p(own() ? "请根据自己的情况作答。" : "你正在协助患者作答。不了解其主观感受时，请选择不清楚。"), button("开始八题问卷", async () => {
      state.response = await api(patientPath("/questionnaire-responses"), "POST", {
        questionnaire_version: state.definition.version
      });
      localStorage.setItem(referenceKey("questionnaire"), state.response.response_id);
      state.question = 0;
      await render();
    }, "primary")));
    return;
  }
  const response = state.response;
  if (response.status === "submitted") {
    main.append(p("本次回答已经提交，原回答会保留。"), el("div", {
      class: "actions"
    }, button("查看画像结果", () => navigate("profile", "assessment"), "primary"), button("重新填写或更正", async () => {
      state.response = await api(patientPath("/questionnaire-responses"), "POST", {
        questionnaire_version: state.definition.version,
        supersedes_response_id: response.response_id
      });
      localStorage.setItem(referenceKey("questionnaire"), state.response.response_id);
      state.question = 0;
      await render();
    })));
    return;
  }
  const theme = state.definition.themes[state.question],
    q = theme.question_id,
    old = response.answers[q];
  let value = copyValue(old.value || answerDefault(q)),
    answerState = old.state;
  const box = el("section", {}),
    form = el("div", {}),
    progress = el("div", {
      class: "progress"
    }, el("div", {}));
  progress.firstChild.style.width = `${state.question/8*100}%`;
  box.append(p(`第 ${state.question+1} 题，共 8 题`, "steps"), progress, el("h2", {}, theme.prompt));
  const states = el("div", {
    class: "row"
  });
  for (const [code, label] of [
      ["answered", "选择或填写"],
      ["unknown", "不清楚 / 无法判断"],
      ["not_applicable", "不适用"]
    ]) states.append(el("label", {
    class: "check"
  }, el("input", {
    type: "radio",
    name: "answer-state",
    value: code,
    checked: answerState === code,
    onchange: () => {
      answerState = code;
      draw();
    }
  }), label));
  box.append(states, form);

  function draw() {
    form.replaceChildren();
    if (answerState !== "answered") {
      form.append(p(answerState === "not_answered" ? "请选择回答方式；未答题可以先保存进度。" : "本题将保留所选状态，不会填成零。", "muted"));
      return;
    }
    const single = ["Q1", "Q3", "Q6"].includes(q),
      selectedKey = q === "Q1" ? "primary" : q === "Q3" ? "choice" : q === "Q6" ? "confidence_level" : "selected",
      choices = el("div", {
        class: "choices"
      });
    for (const option of theme.options) {
      const checked = single ? String(value[selectedKey]) === option.code : value.selected.includes(option.code),
        node = el("input", {
          type: single ? "radio" : "checkbox",
          name: "answer-option",
          value: option.code,
          checked,
          onchange: () => {
            if (single) {
              value[selectedKey] = q === "Q6" ? Number(node.value) : node.value;
              draw();
            } else {
              if (node.checked) value.selected = option.code === "none" ? ["none"] : [...value.selected.filter(x => x !== "none"), option.code];
              else value.selected = value.selected.filter(x => x !== option.code);
              for (const rank of ["top_ranked", "top_concerns", "ranked"])
                if (value[rank]) value[rank] = value[rank].filter(x => value.selected.includes(x));
              draw();
            }
          }
        });
      choices.append(el("label", {
        class: "check"
      }, node, option.label));
    }
    form.append(choices);
    if (q === "Q1") {
      value.additional = value.additional.filter(x => x !== value.primary);
      const extras = el("fieldset", {}, el("legend", {}, "还有其他情况吗？（可选）"));
      for (const option of theme.options.filter(x => x.code !== value.primary)) {
        const [label, node] = checkbox(option.label, value.additional.includes(option.code));
        node.addEventListener("change", () => {
          value.additional = node.checked ? [...value.additional, option.code] : value.additional.filter(x => x !== option.code);
        });
        extras.append(label);
      }
      form.append(extras);
    }
    const rankKey = {
      Q2: "top_ranked",
      Q4: "top_concerns",
      Q8: "ranked"
    } [q];
    if (rankKey) {
      const max = q === "Q4" ? 2 : 3,
        labels = Object.fromEntries(theme.options.map(x => [x.code, x.label]));
      form.append(p(`可选：标出最重要的${max}项，可拖动或用按钮调整顺序。`, "muted"));
      for (const item of value.selected.filter(x => x !== "none" && !value[rankKey].includes(x))) form.append(button("加入优先项：" + labels[item], () => {
        if (value[rankKey].length < max) {
          value[rankKey].push(item);
          draw();
        } else throw new Error(`最多选择${max}项优先内容。`);
      }));
      let dragged = null;
      for (const [i, item] of value[rankKey].entries()) {
        const move = delta => {
          const j = i + delta;
          if (j >= 0 && j < value[rankKey].length) {
            [value[rankKey][j], value[rankKey][i]] = [value[rankKey][i], value[rankKey][j]];
            draw();
          }
        };
        form.append(el("div", {
          class: "rank-item",
          draggable: true,
          ondragstart: () => {
            dragged = item;
          },
          ondragover: e => e.preventDefault(),
          ondrop: e => {
            e.preventDefault();
            if (dragged) {
              value[rankKey] = value[rankKey].filter(x => x !== dragged);
              value[rankKey].splice(i, 0, dragged);
              draw();
            }
          }
        }, `${i+1}. ${labels[item]}`, el("div", {
          class: "row"
        }, button("上移", () => move(-1), "", !i), button("下移", () => move(1), "", i === value[rankKey].length - 1), button("移除", () => {
          value[rankKey] = value[rankKey].filter(x => x !== item);
          draw();
        }))));
      }
    }
    if (q === "Q2" && value.selected.includes("other")) {
      const [label, node] = input("其他原因（简短即可）", value.other_text || "");
      node.addEventListener("input", () => {
        value.other_text = node.value || null;
      });
      form.append(label);
    } else if (q === "Q2") value.other_text = null;
    if (q === "Q4") {
      const [label, node] = select("担忧程度（可不补充，仅描述）", [
        ["", "不补充"], ...[0, 1, 2, 3, 4].map(n => [String(n), String(n)])
      ], value.intensity ?? "");
      node.addEventListener("change", () => {
        value.intensity = node.value === "" ? null : Number(node.value);
      });
      form.append(label);
    }
    if (q === "Q5") {
      const [label, node] = select("发生频率（可不补充）", [
        ["", "不补充"],
        ["never", "从不"],
        ["occasionally", "偶尔"],
        ["often", "经常"]
      ], value.frequency || "");
      node.addEventListener("change", () => {
        value.frequency = node.value || null;
      });
      form.append(label);
    }
  }
  async function saveAnswer() {
    const answers = Object.fromEntries(Object.entries(response.answers).map(([id, a]) => [id, {
      state: a.state,
      value: a.value
    }]));
    answers[q] = {
      state: answerState,
      value: answerState === "answered" ? value : null
    };
    state.response = await api(`/questionnaire-responses/${response.response_id}/answers`, "PUT", {
      expected_revision: response.meta.revision,
      answers
    });
  }
  draw();
  box.append(el("div", {
    class: "actions"
  }, button("上一题", async () => {
    await saveAnswer();
    state.question--;
    await render();
  }, "", state.question === 0), button("保存进度", async () => {
    await saveAnswer();
    await render();
    notice("进度已保存，稍后可继续。");
  }), button(state.question === 7 ? "保存最后一题" : "保存并下一题", async () => {
    await saveAnswer();
    if (state.question < 7) state.question++;
    await render();
  }, "primary")));
  if (state.question === 7) {
    const [label, confirm] = checkbox("我确认提交本次回答（不清楚与不适用会如实保留）");
    box.append(label, button("提交问卷", async () => {
      if (!confirm.checked) throw new Error("请先明确确认提交。");
      await saveAnswer();
      state.response = await api(`/questionnaire-responses/${response.response_id}/submit`, "POST", {
        expected_revision: state.response.meta.revision,
        confirmed: true
      });
      await render();
      notice("回答已提交。可以主动生成描述性画像。");
    }, "primary"));
  }
  main.append(box);
}
async function profileView() {
  if (!scope("profile:read")) {
    main.append(p("当前未获画像查看权限。"));
    return;
  }
  const box = el("section", {});
  main.append(box);
  let profile = null;
  try {
    profile = await api(patientPath("/profiles/current"));
  } catch (error) {
    box.append(p(error.message, "muted"));
  }
  const responseId = localStorage.getItem(referenceKey("questionnaire"));
  if (own() && responseId) box.append(button("根据已提交回答生成描述性结果", async () => {
    await api(patientPath("/profiles"), "POST", {
      response_id: responseId
    });
    await render();
    notice("已保存独立画像结果；没有生成CAS或分类预测。");
  }, "primary"));
  if (!profile) {
    box.append(button("前往八题问卷", () => navigate("profile", "questionnaire")));
    return;
  }
  box.append(el("h2", {}, "你的回答与关注重点"), p(`生成于 ${dateText(profile.generated_at)}`, "muted"), p("CAS：尚未适配，当前没有预测值。"), p(profile.cas.reason, "muted"), p("主要分类：暂不判型；分类方法尚未适配，不用标签替代你的真实情况。"));
  for (const factor of profile.factors) box.append(el("div", {
    class: "item"
  }, el("strong", {}, factor.label), p(factor.source_value)));
  for (const reason of profile.missing_items) box.append(p(reason, "muted"));
}
async function familyView() {
  const box = el("section", {});
  main.append(box);
  const [cl, code] = input("患者提供的限时绑定码");
  box.append(el("h2", {}, "帮助家人"), p("绑定只建立关系，不会自动取得健康资料权限。患者需要另行明确授权。"), cl, button("兑换绑定码", async () => {
    await api("/family-bindings/redeem", "POST", {
      binding_code: code.value
    });
    await context();
    await render();
    notice("家庭关系已建立，请由患者选择具体授权范围。");
  }, "primary"));
  if (!state.patient) return;
  if (own()) {
    const output = el("p", {
      class: "warning"
    });
    box.append(el("h2", {}, "邀请家人"), button("生成一次性绑定码", async () => {
      const result = await api(patientPath("/family-binding-codes"), "POST", {});
      output.textContent = `${result.binding_code}（截止 ${dateText(result.expires_at)}，仅一次使用）`;
    }), output);
  }
  const bindings = await all(patientPath("/family-bindings")),
    grants = await all(patientPath("/grants"));
  box.append(el("h2", {}, "家庭关系与授权"));
  if (!bindings.length) box.append(p("当前没有家庭关系。", "empty"));
  for (const binding of bindings) {
    const item = el("div", {
      class: "item"
    }, el("strong", {}, accounts.find(x => x[0] === binding.family_account_id)?.[1] || "已关联家人"), p(`关系：${statusLabels[binding.status]}`));
    const related = grants.filter(g => g.binding_id === binding.binding_id),
      latest = related.at(-1);
    item.append(p(latest ? `授权：${statusLabels[latest.status]}，${latest.scopes.map(s=>grantOptions.find(x=>x[0]===s)?.[1]||s).join("、")||"没有健康权限"}` : "尚未授予健康资料权限", "muted"));
    if (own() && binding.status === "active") {
      const settings = el("details", {}, el("summary", {}, "编辑精确授权范围")),
        checks = [];
      for (const [scopeCode, label] of grantOptions) {
        const [node, control] = checkbox(label, latest?.status === "active" && latest.scopes.includes(scopeCode));
        checks.push([scopeCode, control]);
        settings.append(node);
      }
      settings.append(p("家人不能发布正式计划或主动生成患者画像。授权范围不会自动随功能增加。", "muted"), button("明确确认并保存授权", async () => {
        const shown = new Set(grantOptions.map(x => x[0])),
          keep = latest?.status === "active" ? latest.scopes.filter(x => !shown.has(x)) : [];
        await api(`/family-bindings/${binding.binding_id}/grant`, "PUT", {
          expected_revision: latest?.meta.revision || 0,
          scopes: [...keep, ...checks.filter(x => x[1].checked).map(x => x[0])],
          valid_until: null,
          confirmed: true
        });
        await context();
        await render();
        notice("授权范围已保存。");
      }, "primary"));
      item.append(settings);
      if (latest?.status === "active") item.append(button("撤销这条授权", async () => {
        await api(`/grants/${latest.grant_id}/revoke`, "POST", {
          expected_revision: latest.meta.revision,
          reason: "患者在家庭管理页面主动撤销"
        });
        await context();
        await render();
        notice("授权已撤销，关系仍保留。");
      }, "danger"));
    }
    if (binding.status === "active") item.append(button(own() ? "解除这条家庭关系" : "退出这条家庭关系", async () => {
      await api(`/family-bindings/${binding.binding_id}/revoke`, "POST", {
        expected_revision: binding.meta.revision,
        reason: "当前账号在家庭页面主动解除关系"
      });
      await context();
      await render();
      notice("关系已解除，原授权不再可用。");
    }, "danger"));
    box.append(item);
  }
}
async function draftView() {
  if (!scope("drafts:read")) {
    main.append(p("当前未获草稿查看权限。"));
    return;
  }
  const drafts = await all(patientPath("/drafts")),
    meds = scope("medication:read") ? await all(patientPath("/medications")) : [],
    files = scope("files:read") ? await all(patientPath("/files")) : [],
    box = el("section", {}),
    editor = el("div", {});
  main.append(box);
  box.append(p("人工录成草稿，核对后提交，再由患者本人确认正式计划。文件保存、草稿提交和正式确认是不同结果。"));
  if (!meds.length) {
    box.append(button("先添加药品资料", () => navigate("medication", "meds"), "primary"));
    return;
  }

  function edit(draft = null) {
    state.draft = draft;
    editor.replaceChildren(el("h2", {}, draft ? "修改资料草稿" : "新建资料草稿"));
    let rows = copyValue(draft?.entries || []);
    const fileChecks = [];
    if (files.length) {
      const fileSet = el("fieldset", {}, el("legend", {}, "来源文件（纯手工可以不选）"));
      for (const file of files) {
        const [label, node] = checkbox(file.original_name, draft?.source_file_ids.includes(file.file_id));
        fileSet.append(label);
        fileChecks.push([file.file_id, node]);
      }
      editor.append(fileSet);
    }
    const rowArea = el("div", {});
    let readers = [];

    function draw() {
      rowArea.replaceChildren();
      readers = [];
      rows.forEach((row, index) => {
        const area = el("fieldset", {}, el("legend", {}, `药品条目 ${index+1}`)),
          grid = el("div", {
            class: "grid"
          }),
          fields = {};

        function add(name, label, type = "text", options = null) {
          const pair = options ? select(label, options, row[name] ?? "") : input(label, row[name] ?? "", type);
          fields[name] = pair[1];
          grid.append(pair[0]);
        }
        add("medication_id", "药品资料", "text", meds.map(m => [m.medication_id, m.name]));
        add("dose_value", "每次剂量（原资料数值）");
        add("dose_unit", "剂量单位（原资料）");
        add("start_date", "开始日期", "date");
        add("end_date", "结束日期（未知可空）", "date");
        const [kl, kind] = select("固定频次", [
          ["daily", "每天"],
          ["weekly", "每周指定日期"]
        ], row.schedule?.kind || "daily"), [tl, times] = input("每天时刻（HH:mm，多个用逗号分隔）", row.schedule?.times.join(",") || "");
        grid.append(kl, tl);
        const weekdays = el("div", {
            class: "row"
          }),
          weekdayInputs = [];
        for (let n = 1; n <= 7; n++) {
          const [label, node] = checkbox(["一", "二", "三", "四", "五", "六", "日"][n - 1], row.schedule?.weekdays.includes(n));
          weekdays.append(label);
          weekdayInputs.push([n, node]);
        }
        grid.append(field("每周日期（每天安排不勾选）", weekdays));
        add("meal_requirement", "餐前、餐后等要求（未知可空）");
        add("medical_notes", "特殊医嘱原文（未知可空）");
        add("strict_timing", "是否明确严格时间要求", "text", [
          ["", "未知"],
          ["true", "是"],
          ["false", "原资料明确无严格时间要求"]
        ]);
        fields.strict_timing.value = row.strict_timing === null ? "" : String(row.strict_timing);
        add("min_interval_minutes", "原医嘱最小间隔（分钟，未知可空）", "number");
        area.append(grid);
        rowArea.append(area);
        readers.push(() => ({
          draft_entry_id: row.draft_entry_id,
          medication_id: fields.medication_id.value,
          dose_value: fields.dose_value.value || null,
          dose_unit: fields.dose_unit.value || null,
          start_date: fields.start_date.value || null,
          end_date: fields.end_date.value || null,
          schedule: times.value ? {
            kind: kind.value,
            times: times.value.split(/[,，]/).map(x => x.trim()).filter(Boolean),
            weekdays: kind.value === "daily" ? [] : weekdayInputs.filter(x => x[1].checked).map(x => x[0])
          } : null,
          meal_requirement: fields.meal_requirement.value || null,
          medical_notes: fields.medical_notes.value || null,
          strict_timing: fields.strict_timing.value === "" ? null : fields.strict_timing.value === "true",
          min_interval_minutes: fields.min_interval_minutes.value ? Number(fields.min_interval_minutes.value) : null,
          source_file_ids: row.source_file_ids || []
        }));
        area.append(button("移除此条目", () => {
          rows = readers.map(read => read());
          rows.splice(index, 1);
          draw();
        }, "quiet", rows.length === 1));
      });
    }

    function addRow() {
      rows = readers.map(read => read());
      rows.push({
        draft_entry_id: crypto.randomUUID(),
        medication_id: meds[0].medication_id,
        dose_value: null,
        dose_unit: null,
        start_date: null,
        end_date: null,
        schedule: null,
        meal_requirement: null,
        medical_notes: null,
        strict_timing: null,
        min_interval_minutes: null,
        source_file_ids: []
      });
      draw();
    }
    editor.append(rowArea);
    if (!rows.length) addRow();
    else draw();
    editor.append(el("div", {
      class: "actions"
    }, button("再加一种药品", addRow), button("保存草稿", async () => {
      const body = {
        source_file_ids: fileChecks.filter(x => x[1].checked).map(x => x[0]),
        entries: readers.map(read => read())
      };
      if (draft) body.expected_revision = draft.meta.revision;
      await api(draft ? `/drafts/${draft.draft_id}` : patientPath("/drafts"), draft ? "PUT" : "POST", body);
      state.draft = null;
      await render();
      notice("草稿已保存，尚未成为正式计划。");
    }, "primary", !scope("drafts:write"))));
  }
  if (scope("drafts:write")) {
    box.append(button("新建人工资料草稿", () => edit()));
    if (state.draft && ["editing", "returned"].includes(state.draft.status)) edit(state.draft);
  }
  box.append(editor, el("h2", {}, "草稿与核对进度"));
  if (!drafts.length) box.append(p("还没有资料草稿。", "empty"));
  const plans = scope("plan:read") ? await all(patientPath("/plans")) : [];
  for (const draft of drafts) {
    const item = el("div", {
      class: "item"
    }, el("strong", {}, `${statusLabels[draft.status]} · ${draft.entries.length} 个条目`), p(`内容修订 ${draft.content_revision} · ${dateText(draft.meta.updated_at)}`, "muted"));
    for (const entry of draft.entries) item.append(p(`${meds.find(m=>m.medication_id===entry.medication_id)?.name||"药品资料"}：${entry.dose_value??"剂量未录入"} ${entry.dose_unit??"单位未录入"}；${entry.schedule?.times.join("、")||"时间待核对"}`));
    if (draft.return_reason) item.append(p(draft.return_reason, "warning"));
    if (["editing", "returned"].includes(draft.status)) item.append(button("修改草稿", () => edit(draft), "", !scope("drafts:write")), button("提交本修订供本人核对", async () => {
      await api(`/drafts/${draft.draft_id}/submit`, "POST", {
        expected_revision: draft.meta.revision,
        content_revision: draft.content_revision
      });
      await render();
      notice("已提交此内容修订，等待患者本人核对。");
    }, "", !scope("drafts:submit")));
    if (draft.status === "pending_confirmation" && own()) {
      const area = el("details", {}, el("summary", {}, "核对并发布正式计划")),
        [tl, effective] = input("生效时间（北京时间，当前或未来）", "", "datetime-local"),
        unique = [...new Map(plans.map(plan => [plan.plan_id, plan])).values()],
        [pl, target] = select("新计划或更新已有计划", [
          ["", "建立新计划"], ...unique.map(plan => [plan.plan_id, `更新计划 · 第${plan.plan_version}版 · ${dateText(plan.effective_from)}`])
        ], ""),
        [yl, yes] = checkbox("我已核对原资料与此修订；这不是医院或药师审核，医嘱变更需先咨询专业人员。");
      area.append(tl, pl, yl, button("明确确认并发布", async () => {
        if (!yes.checked || !effective.value) throw new Error("请填写生效时间并明确确认资料。");
        const previous = plans.filter(x => x.plan_id === target.value).sort((a, b) => b.plan_version - a.plan_version)[0];
        await api(patientPath("/plan-confirmations"), "POST", {
          draft_id: draft.draft_id,
          draft_revision: draft.content_revision,
          existing_plan_id: target.value || null,
          expected_plan_version: previous?.plan_version || null,
          effective_from: new Date(effective.value + ":00+08:00").toISOString(),
          confirmed: true
        });
        await render();
        notice("正式计划、草稿引用和时段已共同保存。");
      }, "primary"));
      item.append(area);
    }
    if (draft.formal_plan) item.append(p(`正式计划第 ${draft.formal_plan.plan_version} 版已保存；可在“今日安排”中查看。`, "success"));
    box.append(item);
  }
}
async function reminderView() {
  if (!scope("reminder:read")) {
    main.append(p("当前未获提醒设置查看权限。"));
    return;
  }
  let current = null;
  try {
    current = await api(patientPath("/reminder-preferences"));
  } catch (error) {
    if (!error.message.includes("尚未保存")) throw error;
  }
  const settings = current || {
      enabled: false,
      channels: ["in_app"],
      sound_enabled: false,
      vibration_enabled: false,
      routine_mode: "regular",
      anchors: [],
      privacy_enabled: false,
      custom_text: null,
      privacy_windows: [],
      repeat_interval_minutes: null,
      max_repeats: 0,
      snooze_minutes: null,
      notify_family: false
    },
    box = el("section", {});
  main.append(box);
  box.append(p("本阶段只保存提醒偏好，不会发送通知。实际提醒会在后续阶段按正式计划、当前授权与医学约束执行，不保证关闭网页后送达。", "warning"));
  const [enl, enabled] = checkbox("启用应用内提醒偏好", settings.enabled), [prl, privacy] = checkbox("隐私提醒（不显示药品或疾病）", settings.privacy_enabled), [fal, family] = checkbox("允许已获接收授权的家人接收相关通知", settings.notify_family), [rol, routine] = select("生活作息", [
    ["regular", "常规"],
    ["night_shift", "夜班"],
    ["rotating_shift", "轮班"],
    ["travel", "外出或差旅"],
    ["custom", "自定义"]
  ], settings.routine_mode), [txl, text] = input("提醒文字（隐私模式仅中性文案）", settings.custom_text || ""), [inl, interval] = input("重复间隔（30—120分钟，不重复留空）", settings.repeat_interval_minutes ?? "", "number", {
    min: 30,
    max: 120
  }), [rel, repeats] = input("最多重复次数（0—2）", settings.max_repeats, "number", {
    min: 0,
    max: 2
  }), [snl, snooze] = input("偏好的稍后时长（5—120分钟，可空）", settings.snooze_minutes ?? "", "number", {
    min: 5,
    max: 120
  });
  box.append(enl, rol, prl, txl, field("通知方式", p("应用内提醒。系统通知、声音及振动尚未接入。", "muted")), el("div", {
    class: "grid"
  }, inl, rel, snl), fal);
  const anchorBox = el("div", {}),
    anchors = [];

  function anchorRow(a = {
    event: "wake",
    label: null,
    local_time: "",
    offset_minutes: 0
  }) {
    const row = el("fieldset", {}, el("legend", {}, "生活事件锚点")),
      [evl, event] = select("事件", [
        ["wake", "起床"],
        ["breakfast", "早餐"],
        ["bedtime", "睡前"],
        ["custom", "自定义"]
      ], a.event),
      [lal, label] = input("自定义事件名称", a.label || ""),
      [til, time] = input("用户主动设置的时刻", a.local_time, "time"),
      [ofl, offset] = input("偏移分钟（-60至60，只用于通知偏好）", a.offset_minutes, "number", {
        min: -60,
        max: 60
      }),
      entry = {
        row,
        read: () => ({
          event: event.value,
          label: label.value || null,
          local_time: time.value,
          offset_minutes: Number(offset.value)
        })
      };
    anchors.push(entry);
    row.append(evl, lal, til, ofl, button("移除此锚点", () => {
      anchors.splice(anchors.indexOf(entry), 1);
      row.remove();
    }));
    anchorBox.append(row);
  }
  for (const a of settings.anchors) anchorRow(a);
  box.append(el("h2", {}, "生活事件锚点"), p("不具备实时作息感知，只保存主动设置的事件。医学约束未知时，后续执行不会据此偏移原医嘱。", "muted"), anchorBox, button("添加生活事件锚点", () => anchorRow()));
  const windowBox = el("div", {}),
    windows = [];

  function windowRow(w = {
    start: "",
    end: ""
  }) {
    const row = el("div", {
        class: "grid"
      }),
      [sl, s] = input("隐私时段开始", w.start, "time"),
      [endLabel, e] = input("隐私时段结束", w.end, "time"),
      entry = {
        read: () => ({
          start: s.value,
          end: e.value
        })
      };
    windows.push(entry);
    row.append(sl, endLabel, button("移除此隐私时段", () => {
      windows.splice(windows.indexOf(entry), 1);
      row.remove();
    }));
    windowBox.append(row);
  }
  for (const w of settings.privacy_windows) windowRow(w);
  box.append(el("h2", {}, "隐私时段"), p("每段为同日时间，跨午夜请分成两段。", "muted"), windowBox, button("添加隐私时段", () => windowRow()), button("保存提醒偏好", async () => {
    await api(patientPath("/reminder-preferences"), "PUT", {
      expected_revision: current?.meta.revision || 0,
      settings: {
        enabled: enabled.checked,
        channels: ["in_app"],
        sound_enabled: false,
        vibration_enabled: false,
        routine_mode: routine.value,
        anchors: anchors.map(x => x.read()),
        privacy_enabled: privacy.checked,
        custom_text: text.value || null,
        privacy_windows: windows.map(x => x.read()),
        repeat_interval_minutes: interval.value ? Number(interval.value) : null,
        max_repeats: Number(repeats.value),
        snooze_minutes: snooze.value ? Number(snooze.value) : null,
        notify_family: family.checked
      }
    });
    await render();
    notice("提醒偏好已保存，尚未执行或发送。");
  }, "primary", !scope("reminder:write")));
}
async function checkHealth() {
  const output = document.querySelector("#health"),
    b = document.querySelector("#refresh");
  b.disabled = true;
  try {
    const response = await fetch("/api/v1/health", {
        cache: "no-store"
      }),
      result = await response.json();
    output.textContent = response.ok && result.status === "success" ? "基础存储已就绪；功能以各页面实际状态为准。" : "基础服务尚未就绪，请查看初始化或迁移说明。";
  } catch {
    output.textContent = "无法连接本地服务，请确认已启动后重新检查。";
  } finally {
    b.disabled = false;
  }
}
for (const b of document.querySelectorAll("nav button")) b.addEventListener("click", () => act(b, () => navigate(b.dataset.page)));
document.querySelector("#refresh").addEventListener("click", checkHealth);
(async () => {
  await checkHealth();
  try {
    await context();
  } catch {
    state.context = null;
    identity();
  }
  await render();
})();
