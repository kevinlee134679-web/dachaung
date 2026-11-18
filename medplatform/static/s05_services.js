"use strict";

const formalServiceStates = {
  submitted: "已提交", in_progress: "模拟处理中", completed: "模拟完成",
  cancelled: "已取消", failed: "处理失败"
};

function openServiceRecord(id) {
  sessionStorage.setItem(referenceKey("formal-service"), id);
  return navigate("profile", "formal-services");
}

function clearKnownServiceSubmission(draft) {
  const path = patientPath("/services");
  const pending = pendingServiceWrite(path, "POST");
  if (pending?.draftId === draft.service_draft_id && pending.revision === draft.draft_revision) {
    localStorage.removeItem(serviceWriteKey(path, "POST"));
  }
}

function serviceSubmissionControls(draft, textArea, view, openDraft) {
  const [label, explicit] = checkbox("我明确按本草稿申请模拟服务");
  const path = patientPath("/services");
  const reference = "/service-drafts/" + encodeURIComponent(draft.service_draft_id);
  return el("div", {}, label, button("提交正式服务", async () => {
    if (!explicit.checked) throw new Error("请先明确确认提交正式服务。");
    if (textArea.value.trim() !== draft.request_text) throw new Error("请先保存修改并重新确认本次内容。");
    try {
      const value = await serviceWrite(path, "POST", {
        service_draft_id: draft.service_draft_id, draft_revision: draft.draft_revision,
        confirmation_ref_id: draft.confirmation_ref_id, sharing_scope_ref_id: draft.sharing_scope_ref_id
      }, view);
      requireCurrentView(view);
      await openServiceRecord(value.service_id);
      notice("已登记正式服务。");
    } catch (error) {
      if (error instanceof ViewChanged) throw error;
      let result;
      try {
        result = await api(reference, "GET", null, view);
      } catch (lookup) {
        if (lookup instanceof ViewChanged || lookup.status === 403 || lookup.status === 404) throw lookup;
        throw error;
      }
      requireCurrentView(view);
      if (result.service_id) {
        clearKnownServiceSubmission(result);
        await openServiceRecord(result.service_id);
        notice("从原草稿核实了已提交的服务。");
      } else {
        if (error.code === "SERVICE_CONFIRMATION_REQUIRED") await openDraft(draft.service_draft_id, textArea.value);
        throw error;
      }
    }
  }, "primary"));
}

function dispatchDescription(task, attempt) {
  if (attempt?.execution_status === "outcome_unknown") return "原派发结果未知，请核对原任务及后续回执。";
  if (task.status === "succeeded" && attempt?.delivery_status === "submitted") return "模拟派发已登记，服务状态请见上方。";
  const labels = {pending: "等待模拟派发", retry_wait: "模拟派发明确失败，等待安全重试",
    running: "模拟派发待核实", cancelled: "原派发已停止", expired: "派发授权已过期", failed: "模拟派发失败"};
  return labels[task.status] || labelFor(task.status);
}

async function serviceRecordsView() {
  if (!scope("services:read")) return;
  const view = captureView(), begin = readGate();
  const detail = el("div", {"aria-live": "polite"});
  const history = el("div", {});
  const [label, filter] = select("按服务状态查看", [["", "全部"], ...Object.entries(formalServiceStates)]);
  const remembered = referenceKey("formal-service");
  const base = patientPath("/services");
  main.append(el("section", {class: "panel"}, el("h2", {}, "正式服务记录"), p("本地虚构演示", "muted"),
    label, history, detail));
  const loadList = readGate();

  async function list(cursor = null) {
    const check = loadList();
    const query = new URLSearchParams({limit: "20"});
    if (filter.value) query.set("status", filter.value);
    if (cursor) query.set("cursor", cursor);
    const page = await api(base + "?" + query, "GET", null, view);
    check();
    if (!cursor) history.replaceChildren();
    else history.lastChild?.remove();
    if (!page.items.length && !cursor) history.append(p("暂无此范围内的正式服务。"));
    for (const doc of page.items) {
      history.append(button(`${doc.service_name} · ${formalServiceStates[doc.status]}`, () => load(doc.service_id)));
    }
    if (page.next_cursor) history.append(button("读取下一页", () => list(page.next_cursor)));
  }

  async function load(id, unsavedReason = "") {
    const check = begin();
    const path = "/services/" + encodeURIComponent(id);
    detail.replaceChildren();
    const value = await api(path, "GET", null, view);
    check();
    sessionStorage.setItem(remembered, id);
    detail.append(el("h3", {}, value.service_name),
      p(`服务编号 ${id}`, "reference"), p(`服务状态 ${formalServiceStates[value.status]}`, "status"),
      p(`目录版本 ${value.resource_version} · ${value.provider.display_name} · mock/demo`, "muted"));
    if (own()) detail.append(p(value.request_text));
    const times = [["提交", value.submitted_at], ["模拟接收", value.started_at],
      ["模拟完成", value.completed_at], ["取消", value.cancelled_at], ["失败", value.failed_at]];
    detail.append(el("ul", {}, times.filter(([, date]) => date).map(([name, date]) =>
      el("li", {}, `${name} ${dateText(date)}`))));
    for (const message of [value.failure_reason, value.cancellation_reason, value.result_summary]) {
      if (message) detail.append(p(message));
    }
    if (value.provider_response) detail.append(p("模拟答复 · " + value.provider_response.text));
    detail.append(button("刷新服务状态", async () => { await list(); await load(id); }));
    if (own() && ["submitted", "in_progress"].includes(value.status)) {
      const [reasonLabel, reason] = input("取消原因", unsavedReason, "text", {maxLength: 500});
      const [confirmLabel, explicit] = checkbox("我明确取消本次服务");
      detail.append(reasonLabel, confirmLabel, button("取消正式服务", async () => {
        if (!explicit.checked || !reason.value.trim()) throw new Error("请填写原因并明确确认取消。");
        try {
          await serviceWrite(path + "/cancel", "POST",
            {expected_revision: value.meta.revision, reason: reason.value.trim()}, view);
          check();
          await list();
          await load(id);
        } catch (error) {
          check();
          if (error.status === 409 || !error.status || error.status >= 500) await load(id, reason.value);
          throw error;
        }
      }, "danger"));
    }
    if (value.dispatch_task_id && scope("tasks:read")) {
      const taskPath = "/tasks/" + encodeURIComponent(value.dispatch_task_id);
      try {
        const [task, attempts] = await Promise.all([api(taskPath, "GET", null, view),
          api(taskPath + "/executions", "GET", null, view)]);
        check();
        const status = dispatchDescription(task, attempts.items.at(-1));
        const reconciled = attempts.items.at(-1)?.execution_status === "outcome_unknown" && value.started_at;
        detail.append(el("h3", {}, "模拟派发"),
          p(`派发任务 ${value.dispatch_task_id}`, "reference"),
          p(reconciled ? "原派发结果曾未知，后续模拟回执已登记接收。" : status),
          ...attempts.items.map(attempt => p(`尝试 ${attempt.attempt} · ${labelFor(attempt.execution_status)}`, "muted")));
      } catch (error) {
        check();
        if (error.status !== 403 && error.status !== 404) detail.append(p("原派发状态暂不可核查，请刷新。", "error"));
      }
    }
  }

  filter.addEventListener("change", () => list().catch(error => {
    if (!(error instanceof ViewChanged)) notice(error.message, true);
  }));
  await list();
  const selected = sessionStorage.getItem(remembered);
  if (selected) await load(selected);
}

function serviceDemoControls() {
  const [taskLabel, task] = input("正式服务派发任务编号", "", "text", {maxLength: 128});
  const [serviceLabel, service] = input("正式服务编号", "", "text", {maxLength: 128});
  const [revisionLabel, revision] = input("当前服务修订", "1", "number", {min: 1});
  const [targetLabel, target] = select("模拟状态变化", Object.entries(formalServiceStates).slice(1));
  const [reasonLabel, reason] = input("模拟原因或结果", "", "text", {maxLength: 500});
  const output = el("div", {"aria-live": "polite"});
  return el("section", {class: "panel"}, el("h2", {}, "社会支持演示控制台"), p("仅用于本地虚构服务。"),
    taskLabel, button("执行一次模拟派发", async view => {
      const path = "/tasks/" + encodeURIComponent(task.value.trim());
      const current = await api(path, "GET", null, view);
      if (current.kind !== "dispatch_service") throw new Error("此处只执行正式服务的模拟派发。");
      if (["pending", "retry_wait"].includes(current.status)) {
        try {
          await api(path + "/run", "POST", {expected_revision: current.meta.revision}, view);
        } catch (error) {
          if (error instanceof ViewChanged || error.status === 403 || error.status === 404) throw error;
        }
      }
      const [latest, attempts] = await Promise.all([api(path, "GET", null, view), api(path + "/executions", "GET", null, view)]);
      output.replaceChildren(p(dispatchDescription(latest, attempts.items.at(-1))));
    }),
    serviceLabel, revisionLabel, targetLabel, reasonLabel, button("记录模拟状态变化", async view => {
      if (!service.value.trim() || !revision.valueAsNumber || !reason.value.trim()) throw new Error("请填写编号、修订和原因。");
      const value = await serviceWrite("/demo/services/" + encodeURIComponent(service.value.trim()) + "/transitions", "POST",
        {expected_revision: revision.valueAsNumber, target_status: target.value, reason: reason.value.trim()}, view);
      revision.value = value.meta.revision;
      output.replaceChildren(p(`服务状态 ${formalServiceStates[value.status]} · 修订 ${value.meta.revision}`));
    }), output);
}
