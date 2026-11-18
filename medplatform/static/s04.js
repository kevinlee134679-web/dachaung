"use strict";

const SUPPORT_CASES = {
  "demo-patient-a-self": "case-low-mood",
  "demo-patient-b-self": "case-anxiety",
  "demo-family-self": "case-fatigue"
};
const generationState = {
  accepted: "等待生成", running: "生成中", failed: "生成失败",
  outcome_unknown: "结果未知，先核查原消息", cancelled: "生成已取消"
};
const assessmentSource = {
  model_cues: "模型线索", self_report: "本人自评", context_summary: "上下文摘要"
};

function supportReference() {
  return referenceKey("support-session");
}

function supportPath(session, suffix = "") {
  return "/sessions/" + encodeURIComponent(session.session_id) + suffix;
}

async function refreshSupport(view) {
  requireCurrentView(view);
  state.epoch++;
  const updated = captureView();
  await render();
  requireCurrentView(updated);
}

async function openSupportSession(view, invitation = null, caseId = null) {
  const session = await api("/sessions", "POST", {
    patient_id: view.patientId, case_id: caseId,
    entry_source: invitation ? "accepted_invitation" : "user",
    invitation_id: invitation?.invitation_id ?? null
  }, view);
  requireCurrentView(view);
  sessionStorage.setItem(supportReference(), session.session_id);
  await navigate("support");
}

function invitationList(items, evaluatedAt = new Date().toISOString()) {
  const area = el("section", {}, el("h2", {}, "支持邀请"));
  for (const item of items) {
    const expired = Date.parse(item.valid_until) <= Date.parse(evaluatedAt);
    const card = el("article", {class: "support-invitation"}, el("h3", {}, item.title), p(item.description));
    if (item.status === "pending" && expired) card.append(p("已到期 · 历史待维护", "muted"));
    else if (item.status === "pending" && own()) {
      const respond = (choice, view) => api(
        "/invitations/" + encodeURIComponent(item.invitation_id) + "/response", "POST",
        {choice, expected_status: "pending", session_id: null}, view
      );
      card.append(el("div", {class: "actions"}, button("接受并进入对话", async view => {
        await respond("accepted", view);
        await openSupportSession(view, item);
      }), button("拒绝邀请", async view => {
        await respond("declined", view);
        await refreshSupport(view);
      })));
    } else if (item.status === "accepted" && !expired && own()) {
      card.append(button("进入已接受的邀请", view => openSupportSession(view, item)));
    } else {
      card.append(p(({accepted: "已接受", declined: "已拒绝", cancelled: "已取消", expired: "已到期"})[item.status]
                    || "等待本人响应", "muted"));
    }
    area.append(card);
  }
  return area;
}

async function homeSupportInvitations() {
  const data = await api(patientPath("/invitations"));
  const pending = data.items.filter(item => !item.session_id && ["pending", "accepted"].includes(item.status));
  if (pending.length) main.append(invitationList(pending));
}

async function knowledgeView() {
  if (!scope("knowledge:read")) {
    main.append(p("当前对象的知识查看权限未开启。"));
    return;
  }
  const items = await all("/knowledge?kind=medical");
  if (!items.length) main.append(p("目前没有适用的审核药学资料。用药问题请向实际医生或药师核实。"));
  for (const item of items) {
    main.append(el("section", {}, el("h2", {}, item.title), p(item.body), p(item.source_locator, "reference")));
  }
}

async function supportView() {
  if (isDemoAdmin()) {
    main.append(p("演示管理员可在「我的」管理虚构案例及故障场景。"),
                button("打开演示控制台", () => navigate("profile", "demo")));
    return;
  }
  if (!state.patient || !scope("dialogue:read")) {
    main.append(p("请先选择本人或具备专门对话读取授权的对象。"));
    return;
  }
  main.append(el("h2", {}, "AI 情感支持"));
  const view = captureView();
  const sessions = await all("/sessions?patient_id=" + encodeURIComponent(view.patientId));
  const stored = sessionStorage.getItem(supportReference());
  const session = sessions.find(item => item.session_id === stored)
    || sessions.filter(item => item.status === "active").at(-1);
  if (own()) {
    const actions = el("div", {class: "actions"}, button("开始自由对话", v => openSupportSession(v), "primary"));
    const caseId = SUPPORT_CASES[view.patientId];
    if (caseId) actions.append(button("打开虚构案例会话", v => openSupportSession(v, null, caseId)));
    main.append(actions);
  }
  if (session) await supportConversation(session, view);
  else main.append(p("暂无会话。"));
  if (scope("interventions:read")) {
    const invitations = await all(patientPath("/invitations"));
    if (invitations.length) main.append(invitationList(invitations));
  }
  if (sessions.length) {
    const history = el("details", {}, el("summary", {}, "其他会话"));
    for (const item of sessions.toReversed()) {
      if (item.session_id === session?.session_id) continue;
      history.append(button(dateText(item.opened_at) + (item.status === "closed" ? " · 已关闭" : " · 进行中"), async () => {
        sessionStorage.setItem(supportReference(), item.session_id);
        await navigate("support");
      }));
    }
    if (history.childNodes.length > 1) main.append(history);
  }
  if (scope("support:read")) main.append(button("查看社会支持", () => navigate("support", "social")));
  if (own() && scope("feedback:read") && scope("services:read") && typeof supportFeedbackPanel === "function") {
    main.append(supportFeedbackPanel());
  }
}

async function supportConversation(session, view) {
  const mode = scope("interventions:read") ? await api(supportPath(session, "/ui-mode"), "GET", null, view) : null;
  const simplified = (mode?.effective_ui_mode || session.ui_mode) === "simplified";
  const canWrite = own() && session.status === "active";
  const panel = el("section", {class: "panel"});
  const toolbar = el("div", {class: "support-toolbar"}, el("h2", {}, simplified ? "极简对话" : "支持对话"),
                     p("本地模拟 · mock / single_pass", "support-status"));
  const messages = await all(supportPath(session, "/messages"));
  const thread = el("div", {class: "support-thread", "aria-label": "对话历史"});
  for (const message of messages) thread.append(supportMessage(session, message, canWrite));
  if (!messages.length) thread.append(p("可以从你现在最想说的一件事开始。", "muted"));
  const actions = el("div", {class: "actions"});
  if (canWrite && mode) {
    actions.append(button(simplified ? "恢复普通模式" : "使用极简模式", async v => {
      await api(supportPath(session, "/ui-mode"), "PUT", {
        ui_mode: simplified ? "normal" : "simplified", expected_revision: mode.current.revision,
        confirmed: true, source_suggestion_id: null
      }, v);
      await refreshSupport(v);
    }));
  }
  if (scope("plan:read")) actions.append(button("今日用药确认", () => navigate("medication")));
  if (canWrite) actions.append(button("结束会话", async v => {
    await api(supportPath(session, "/close"), "POST", {expected_revision: session.meta.revision}, v);
    await refreshSupport(v);
  }));
  panel.append(toolbar, actions, thread);
  if (canWrite) addSupportComposer(panel, session);
  if (!simplified && scope("assessment:read")) await addSupportAssessment(panel, session, canWrite, view);
  main.append(panel);
}

function supportMessage(session, message, canWrite) {
  const mine = message.role === "user";
  const card = el("article", {class: "support-message " + (mine ? "user" : "assistant")},
                  el("small", {}, mine ? "本人" : "AI 支持助手"), p(message.content));
  if (mine && generationState[message.generation_status]) {
    card.append(p(generationState[message.generation_status], "muted"));
    if (canWrite && message.generation_status === "failed") {
      card.append(button("重试原消息", async view => {
        const data = await api("/messages/" + encodeURIComponent(message.message_id) + "/generation-retries", "POST", {
          generation_id: message.generation_id, expected_turn_count: session.turn_count
        }, view);
        await refreshSupport(view);
        showSupportOutput(data);
      }));
    }
  }
  return card;
}

function addSupportComposer(panel, session) {
  const text = el("textarea", {maxLength: 4000, rows: 3, placeholder: "写下想说的话",
                               "data-support-session": session.session_id});
  const key = referenceKey("support-pending:" + session.session_id);
  const readPending = () => JSON.parse(sessionStorage.getItem(key) || "null");

  function clearPending(pending) {
    if (readPending()?.id === pending.id) sessionStorage.removeItem(key);
  }

  async function recover(view) {
    const pending = readPending();
    if (!pending) return;
    let result;
    try {
      result = await api(supportPath(session, "/messages?client_message_id=" + encodeURIComponent(pending.id)),
                         "GET", null, view);
    } catch (error) {
      if (!pending.rejected || error.status !== 404 || error.code !== "RESOURCE_NOT_FOUND") throw error;
      requireCurrentView(view);
      const draft = text.value;
      clearPending(pending);
      await refreshSupport(view);
      const editor = main.querySelector("textarea[data-support-session]");
      if (editor?.getAttribute("data-support-session") === session.session_id && !editor.value) {
        editor.value = draft;
        notice("会话已更新。请核对最新记录后再次点击发送。");
      }
      return;
    }
    requireCurrentView(view);
    const status = result.items[0].generation_status;
    if (!["accepted", "running"].includes(status)) clearPending(pending);
    await refreshSupport(view);
    notice(generationState[status] || "已核对原消息。");
  }
  if (readPending()) panel.append(button("核查原消息", recover, "support-recover"));
  panel.append(field("你想说的话", text), button("发送", async view => {
    const content = text.value;
    if (!content.trim()) throw new Error("请先填写消息。");
    const hash = await sha(content);
    requireCurrentView(view);
    const old = readPending();
    if (old?.rejected) return recover(view);
    if (old && old.hash !== hash) throw new Error("上一条结果尚未核对。请核查原消息，或使用相同原文重试。");
    const pending = old || {id: crypto.randomUUID(), hash, turn: session.turn_count};
    sessionStorage.setItem(key, JSON.stringify(pending));
    let data;
    try {
      data = await api(supportPath(session, "/messages"), "POST", {
        client_message_id: pending.id, expected_turn_count: pending.turn, content
      }, view);
    } catch (error) {
      if (error instanceof ViewChanged) throw error;
      requireCurrentView(view);
      if (error.status === 409 && error.code === "SESSION_REVISION_CONFLICT" && readPending()?.id === pending.id) {
        sessionStorage.setItem(key, JSON.stringify({...pending, rejected: true}));
      }
      try {
        await recover(view);
      } catch (lookup) {
        if (lookup instanceof ViewChanged) throw lookup;
        if (isCurrentView(view) && !panel.querySelector(".support-recover")) {
          panel.append(button("核查原消息", recover, "support-recover"));
        }
        throw error;
      }
      return;
    }
    clearPending(pending);
    await refreshSupport(view);
    showSupportOutput(data);
  }, "primary"));
}

function showSupportOutput(data) {
  if (!scope("interventions:read")) return;
  const output = data.business_output;
  const details = el("details", {}, el("summary", {}, "本轮来源与沟通说明"),
                     p("实际来源 " + data.generation.mode + " / " + data.generation.actual_pipeline),
                     p("策略 " + output.communication_strategy.join("、")));
  for (const cue of output.difficulty_cues) details.append(p(cue.label + " · " + cue.evidence));
  for (const citation of output.knowledge_citations) {
    const link = "/knowledge/" + encodeURIComponent(citation.knowledge_id) + "/versions/"
      + encodeURIComponent(citation.version) + "?session_id=" + encodeURIComponent(data.generation.session_id);
    details.append(p(citation.quote), button("查看所引资料版本", async view => {
      const doc = await api(link, "GET", null, view);
      details.append(p(doc.title + " · " + doc.review_status), p(doc.body), p(doc.source_locator, "reference"));
    }));
  }
  if (output.suggested_action) details.append(p("沟通建议 · " + output.suggested_action.description));
  for (const issue of data.generation.input_snapshot.missing_items) details.append(p(issue.message, "muted"));
  const panel = main.querySelector(".support-thread")?.parentNode;
  if (panel && !panel.querySelector(".support-toolbar h2")?.textContent.includes("极简")) panel.append(details);
}

async function addSupportAssessment(panel, session, canWrite, view) {
  const data = await all(supportPath(session, "/assessments"));
  requireCurrentView(view);
  const details = el("details", {}, el("summary", {}, "自评与沟通线索"), p("这里记录你的描述及可核对的线索。评分方法尚未接入。", "muted"));
  for (const record of data) {
    details.append(p(assessmentSource[record.kind] + " · " + dateText(record.observed_at), "muted"));
    for (const item of record.self_report_items) details.append(p(item.description));
    for (const cue of record.cues) details.append(p(cue.label + " · " + cue.evidence));
  }
  if (canWrite && scope("assessment:write")) {
    const [label, choice] = select("自评主题", [
      ["concerns", "顾虑"], ["necessity", "必要性感知"], ["burden", "负担"],
      ["routine", "作息"], ["support_need", "支持需求"]
    ], "concerns");
    const text = el("textarea", {maxLength: 2000, rows: 2});
    const id = crypto.randomUUID();
    details.append(label, field("你的描述", text), button("保存自评", async v => {
      await api(supportPath(session, "/self-reports"), "POST", {
        client_report_id: id, items: [{dimension: choice.value, description: text.value, source_message_id: null}]
      }, v);
      await refreshSupport(v);
      notice("已保存自评。");
    }));
  }
  panel.append(details);
}

async function supportConsole() {
  if (!isDemoAdmin()) return;
  const view = captureView();
  const [catalog, config] = await Promise.all([all("/cases"), api("/config/status")]);
  requireCurrentView(view);
  const [cl, chooser] = select("虚构案例", catalog.map(entry => [entry.case_id, entry.title]), catalog[0]?.case_id);
  const [sl, scenario] = select("模拟场景", [
    ["state_event", "状态邀请"], ["periodic_node", "周期节点"], ["llm_timeout", "模型超时"],
    ["empty_response", "空响应"], ["invalid_json", "非法结构"], ["knowledge_empty", "知识不足"],
    ["receipt_late", "晚到回执"]
  ], "state_event");
  const [il, sessionId] = input("限定到本案例会话（可留空）");
  const [rl, runId] = input("场景运行号", crypto.randomUUID());
  const [tl, time] = input("事件时间（北京时间）", localDateTime(), "datetime-local");
  const output = el("div", {"aria-live": "polite"});
  const configVersion = config.version_refs.find(ref => ref.kind === "model_config")?.version;
  const model = "mock-single-pass";
  main.append(el("section", {class: "panel"}, el("h2", {}, "情感支持演示控制台"),
    p(config.llm_mode + " / " + config.requested_pipeline),
    el("div", {class: "actions"}, button("显式检查模拟模型", async v => {
      const result = await api("/config/check-model", "POST", {
        profile_id: model, expected_config_version: configVersion, allow_external_call: false
      }, v);
      output.replaceChildren(p("探测完成 · 网络尝试 " + result.network_attempt_count + " 次"));
    }), button("选择 mock single_pass", async v => {
      await api("/config/model-profile", "PUT", {
        profile_id: model, expected_config_version: configVersion, confirmed: true
      }, v);
      await refreshSupport(v);
      notice("已保存模型配置。");
    })), cl,
    button("读取案例开场草稿", async v => {
      const data = await api("/cases/" + encodeURIComponent(chooser.value), "GET", null, v);
      output.replaceChildren(field("开场草稿（可复制到本人对话输入框）",
                                   el("textarea", {readOnly: true, value: data.opening_draft})));
    }), sl, il, rl, tl,
    button("执行一次模拟场景", async v => {
      const data = await api("/demo/triggers", "POST", {
        case_id: chooser.value, session_id: sessionId.value || null, scenario: scenario.value,
        scenario_run_id: runId.value, occurred_at: inputDateTime(time.value)
      }, v);
      output.replaceChildren(p(data.related_ids.length ? "已保存关联 " + data.related_ids.join("、") : "已登记场景。"));
    }), button("准备新运行号", () => { runId.value = crypto.randomUUID(); }),
    button("确认重置所选案例", async v => {
      const selected = catalog.find(entry => entry.case_id === chooser.value);
      if (!selected || !window.confirm("确认清理「" + selected.title + "」的虚构对话记录？")) return;
      const result = await api("/cases/" + encodeURIComponent(selected.case_id) + "/reset", "POST", {
        case_template_version: selected.template_version, confirmed: true
      }, v);
      output.replaceChildren(p("已重置 " + result.affected_session_ids.length + " 个会话。"));
    }, "danger"), output));
  if (typeof serviceDemoControls === "function") main.append(serviceDemoControls());
}
