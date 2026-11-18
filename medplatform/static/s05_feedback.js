"use strict";

const feedbackDimensions = [
  ["support_needs", "支持需求变化"],
  ["support_acceptance", "支持接受程度"],
  ["intervention_effectiveness", "干预效果（本人描述）"]
];
const participationLabels = {provided: "已自愿填写", declined: "明确不参与", unable: "无法填写"};
const feedbackFields = ["participation", ...feedbackDimensions.map(([name]) => name), "willing_to_continue", "missing_reason"];
const feedbackBody = (entry, revision) => Object.assign({expected_feedback_revision: revision},
  Object.fromEntries(feedbackFields.map(name => [name, entry[name]])));

function serviceFeedbackHistory(service, view) {
  const entries = el("div", {"aria-live": "polite"});
  const editor = el("div", {});
  const display = el("div", {}, el("h3", {}, "本人三维反馈"), entries, editor);
  const path = "/services/" + encodeURIComponent(service.service_id) + "/feedback";
  const pendingKey = referenceKey("feedback-submission:" + service.service_id);
  const begin = readGate();
  const eligible = ["completed", "cancelled", "failed"].includes(service.status);
  const pending = () => JSON.parse(sessionStorage.getItem(pendingKey) || "null");
  let current;

  function show(doc) {
    const details = el("details", {open: doc === current},
      el("summary", {}, `反馈修订 ${doc.feedback_revision} · ${participationLabels[doc.participation]}`),
      p(`来源 C · ${dateText(doc.recorded_at)}`, "muted"),
      p(`反馈编号 ${doc.feedback_id}`, "reference"));
    if (doc.supersedes_feedback_id) details.append(p(`更正自 ${doc.supersedes_feedback_id}`, "muted"));
    if (!own()) return details;
    if (doc.participation === "provided") {
      for (const [name, label] of feedbackDimensions) details.append(p(`${label} · ${doc[name] ?? "未填写"}`));
    }
    const willingness = doc.willing_to_continue === null ? "未知" : doc.willing_to_continue ? "愿意" : "不愿意";
    details.append(p("是否愿意继续 · " + willingness));
    if (doc.missing_reason) details.append(p("未填写说明 · " + doc.missing_reason));
    return details;
  }

  async function reconcile(known, history, check) {
    if (!known) return null;
    const candidate = history.find(doc => doc.feedback_revision === known.revision + 1);
    if (!candidate || await sha(JSON.stringify(feedbackBody(candidate, known.revision))) !== known.fingerprint) return null;
    check();
    if (pending()?.clientId === known.clientId) sessionStorage.removeItem(pendingKey);
    return candidate;
  }

  async function load(typed, conflict = false) {
    const check = begin(), history = [];
    try {
      let cursor = null;
      do {
        const query = new URLSearchParams({limit: "100"});
        if (cursor) query.set("cursor", cursor);
        const page = await api(path + "?" + query, "GET", null, view);
        check();
        history.push(...page.items);
        cursor = page.next_cursor;
      } while (cursor);
    } catch (error) {
      check();
      entries.replaceChildren(p("反馈历史暂不可读取。", "error"));
      editor.replaceChildren();
      if (error.status !== 403 && error.status !== 404) entries.append(button("重新读取反馈", () => load(typed, conflict)));
      return;
    }
    const recovered = own() ? await reconcile(pending(), history, check) : null;
    check();
    current = history.at(-1);
    entries.replaceChildren(...history.toReversed().map(show));
    editor.replaceChildren();
    if (!current) entries.append(p(eligible ? "尚未提交反馈。" : "当前服务状态尚不具备反馈资格。", "muted"));
    if (!own()) {
      entries.append(p("当前可查看获准反馈记录及修订，描述由本人查看。", "muted"));
      return;
    }
    if (recovered) notice("已从历史核实原反馈。");
    if (conflict) entries.append(p("另一份反馈已提交。请核对最新修订，原输入仍在下方。", "error"));
    if (eligible && scope("service-feedback:write")) {
      if (typed && !recovered) edit(typed);
      else editor.append(button(current ? "更正当前反馈" : "填写自愿反馈", () => edit(current)));
    }
  }

  function edit(initial) {
    const revision = current?.feedback_revision || 0;
    const [pLabel, choice] = select("反馈参与情况", Object.entries(participationLabels), initial?.participation || "provided");
    const controls = feedbackDimensions.map(([key, label]) => ({
      key, label, area: el("textarea", {rows: 2, maxLength: 2000, value: initial?.[key] ?? ""})
    }));
    const descriptions = el("div", {}, ...controls.map(({label, area}) => field(label, area)));
    const [wLabel, willingness] = select("是否愿意继续",
      [["", "未知"], ["yes", "愿意"], ["no", "不愿意"]],
      initial?.willing_to_continue == null ? "" : initial.willing_to_continue ? "yes" : "no");
    const [mLabel, reason] = input("未填写说明", initial?.missing_reason || "", "text", {maxLength: 500});
    const toggle = () => { descriptions.hidden = choice.value !== "provided"; };
    choice.addEventListener("change", toggle);
    toggle();
    editor.replaceChildren(p(`基于反馈修订 ${revision}`, "muted"), pLabel, descriptions, wLabel, mLabel,
      p("自愿描述本次体验。未知或不适用的内容可留空，并填写说明。", "muted"),
      button("提交本人反馈", async () => {
        const data = {participation: choice.value, ...Object.fromEntries(controls.map(({key, area}) =>
          [key, choice.value === "provided" ? area.value.trim() || null : null])),
          willing_to_continue: willingness.value ? willingness.value === "yes" : null,
          missing_reason: reason.value.trim() || null};
        if (data.participation !== "provided" && !data.missing_reason) throw new Error("请填写无法参与或不参与的原因。");
        const body = feedbackBody(data, revision), hash = await sha(JSON.stringify(body));
        requireCurrentView(view);
        const known = pending();
        if (known && known.fingerprint !== hash) throw new Error("原提交尚待核实，请以原值重试或重新读取反馈历史。");
        const clientId = known?.clientId || crypto.randomUUID();
        sessionStorage.setItem(pendingKey, JSON.stringify({clientId, revision, fingerprint: hash}));
        try {
          await api(path, "POST", {...body, client_feedback_id: clientId}, view);
          if (pending()?.clientId === clientId) sessionStorage.removeItem(pendingKey);
          await load();
          notice("本人反馈已保存。");
        } catch (error) {
          if (error instanceof ViewChanged) throw error;
          if (error.status < 500 && !error.pendingRecovery && error.code !== "OPERATION_IN_PROGRESS") {
            if (pending()?.clientId === clientId) sessionStorage.removeItem(pendingKey);
          }
          if (error.code === "FEEDBACK_REVISION_CONFLICT" || !error.status ||
              error.status >= 500 || error.pendingRecovery || error.code === "OPERATION_IN_PROGRESS") {
            await load(data, error.code === "FEEDBACK_REVISION_CONFLICT");
            if (current?.feedback_revision === revision + 1 &&
                await sha(JSON.stringify(feedbackBody(current, revision))) === hash) return;
          }
          throw error;
        }
      }, "primary"));
  }
  return {node: display, load};
}

function cFeedbackProjection(source) {
  const section = el("div", {}, p(`C 社会支持反馈 · ${labelFor(source.availability)}`, "status"));
  if (source.reason) section.append(p(source.reason, "muted"));
  for (const record of source.records || []) {
    const item = el("div", {class: "item"},
      p(`服务状态 ${formalServiceStates[record.service_status]} · 来源修订 ${record.source_version}`),
      p(`${dateText(record.recorded_at)} · ${record.is_simulated ? "模拟" : "已登记"}`, "muted"));
    for (const [name, label] of feedbackDimensions) {
      if (record[name] !== null) item.append(p(`${label} · ${record[name]}`));
    }
    if (scope("services:read")) item.append(button("查看该服务及反馈历史", () => openServiceRecord(record.record_id)));
    section.append(item);
  }
  return section;
}

function supportFeedbackPanel() {
  const output = el("div", {"aria-live": "polite"}), begin = readGate();
  const panel = el("details", {}, el("summary", {}, "社会支持反馈来源"));
  const range = rangeControls(panel);
  panel.append(button("读取本人社会支持反馈", async view => {
    const check = begin();
    const {window_start, window_end} = range();
    try {
      const data = await api(patientPath("/support-feedback") + "?" +
        rangeQuery({window_start, window_end, limit: 100}), "GET", null, view);
      check();
      output.replaceChildren(cFeedbackProjection(data));
      if (data.records.length === 100) output.append(p("如需查看其他记录，请缩小日期范围。", "muted"));
    } catch (error) {
      check();
      output.replaceChildren(p(error.message, "error"));
    }
  }), output);
  return panel;
}
