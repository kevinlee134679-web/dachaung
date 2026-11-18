"use strict";

const pointLabels = {
  daily_record: "每日有效手动记录",
  five_day_block: "连续五个合格日",
  weekly_review: "每周管理回顾",
  peer_participation: "经审核可见的同辈参与"
};
const pointSourceLabels = {event: "A 服药情况报告", management_review: "C 本人管理回顾", peer_post: "C 本人同辈参与"};

function pointsRange(fields) {
  const {window_start, window_end} = fields();
  return {window_start, window_end};
}

function localReviewWeek(timezone, now = new Date()) {
  const today = new Intl.DateTimeFormat("sv-SE", {timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit"}).format(now);
  const start = new Date(today + "T00:00:00Z");
  start.setUTCDate(start.getUTCDate() - (start.getUTCDay() + 6) % 7);
  return start.toISOString().slice(0, 10);
}

async function reviewForCurrentWeek(path, week, view) {
  // This window covers all time zones' local week start. C validates the actual week.
  const monday = new Date(week + "T00:00:00Z").getTime();
  const window = {window_start: new Date(monday - 86400000).toISOString(),
                  window_end: new Date(monday + 8 * 86400000).toISOString(), limit: 10};
  const page = await api(path + "/management-reviews?" + rangeQuery(window), "GET", null, view);
  return page.items.find(item => item.week_start === week);
}

async function managementReviewPanel(path, timezone, view) {
  const panel = el("section", {class: "panel"}, el("h2", {}, "每周管理回顾"));
  const week = localReviewWeek(timezone);
  const result = el("div", {"aria-live": "polite"});
  const reflection = el("textarea", {maxLength: 2000, rows: 3});
  const [confirmLabel, confirmed] = checkbox("我已完成本周管理回顾");
  const form = el("div", {}, field("回顾内容（可留空）", reflection), confirmLabel);
  function show(review) {
    form.hidden = true;
    result.replaceChildren(p("已记录本周回顾 · " + dateText(review.completed_at)),
      review.reflection ? p(review.reflection) : null);
  }
  form.append(button("确认完成本周回顾", async v => {
    if (!confirmed.checked) throw new Error("请本人明确确认已完成本周回顾。");
    if (!window.confirm("确认记录本周管理回顾？")) return;
    const draft = {week_start: week, reflection: reflection.value.trim() || null, confirmed_completed: true};
    const replayId = "points-review:" + v.accountId + ":" + v.patientId + ":" + await sha(JSON.stringify(draft));
    requireCurrentView(v);
    let submission = sessionStorage.getItem(replayId);
    if (!submission) {
      submission = crypto.randomUUID();
      sessionStorage.setItem(replayId, submission);
    }
    try {
      const saved = await api(path + "/management-reviews", "POST", {client_review_id: submission, ...draft}, v);
      sessionStorage.removeItem(replayId);
      show(saved);
      notice("已保存回顾。积分余额会在核验入账后更新。");
    } catch (error) {
      if (error instanceof ViewChanged) throw error;
      const saved = await reviewForCurrentWeek(path, week, v);
      if (!saved) throw error;
      sessionStorage.removeItem(replayId);
      show(saved);
    }
  }, "primary", false, view));
  panel.append(p("当周起始日 " + week + " · 演示"), form, result);
  const saved = await reviewForCurrentWeek(path, week, view);
  if (saved) show(saved);
  return panel;
}

function pointsLedgerRow(item) {
  const sources = item.source_refs.length
    ? el("ul", {}, ...item.source_refs.map(ref => el("li", {}, (pointSourceLabels[ref.record_kind] || ref.module)
        + " · 版本 " + ref.version + " · " + dateText(ref.recorded_at),
        el("div", {class: "muted"}, ref.record_id))))
    : p("当前权限下来源详情不可用。", "muted");
  return el("li", {}, el("strong", {}, "+" + item.delta + " · " + pointLabels[item.rule_code]),
    p(dateText(item.created_at) + " · 入账后 " + item.balance_after + " 积分 · " + item.rules_version, "muted"),
    el("details", {}, el("summary", {}, "来源与版本"), sources));
}

async function pointsView() {
  const view = captureView();
  const rules = await api("/points/rules", "GET", null, view);
  const rulePanel = el("details", {}, el("summary", {}, "积分规则 · " + rules.rules_version),
    el("ul", {}, ...rules.rules.map(rule => el("li", {}, pointLabels[rule.rule_code] + " +" + rule.points + " · "
      + rule.eligibility_description))),
    p("漏服、医嘱暂停或退出同辈支持不会扣除已有积分。必要专业支持不设积分门槛。"));
  const canRead = view.patientId && scope("points:read");
  const balance = p("正在读取当前余额…");
  const section = el("section", {class: "panel"}, el("h2", {}, "演示积分"), canRead ? balance : null, rulePanel,
    p("积分兑换将在后续开放。", "muted"));
  main.append(section);
  if (!canRead) {
    section.append(p("当前身份没有该患者的积分读取权限。"));
    return;
  }
  const path = "/patients/" + encodeURIComponent(view.patientId);
  const history = el("div", {"aria-live": "polite"});
  const beginRead = readGate();
  const getWindow = rangeControls(section);
  async function loadLedger(v, window, cursor = null, list = null) {
    const current = beginRead();
    try {
      const [account, page] = await Promise.all([
        api(path + "/points", "GET", null, v),
        api(path + "/points-ledger?" + rangeQuery({...window, cursor, limit: 20}), "GET", null, v)
      ]);
      current();
      balance.textContent = "可用积分 " + account.balance;
      list ||= el("ol", {class: "list"});
      list.append(...page.items.map(pointsLedgerRow));
      history.replaceChildren(list.childElementCount ? list : p("这段时间暂无积分流水。"));
      if (page.next_cursor) history.append(button("查看更多流水",
        v => loadLedger(v, window, page.next_cursor, list)));
    } catch (error) {
      current();
      balance.textContent = "余额暂不可显示";
      history.replaceChildren(p(error.message, "error"));
    }
  }
  section.append(button("刷新积分余额和历史", v => loadLedger(v, pointsRange(getWindow))), history);
  await loadLedger(view, pointsRange(getWindow));
  requireCurrentView(view);
  if (own()) {
    const panel = await managementReviewPanel(path, state.patient.patient.timezone, view);
    requireCurrentView(view);
    main.append(panel);
  }
}

function pointsConsole() {
  const section = el("section", {class: "panel"}, el("h2", {}, "演示积分核验"),
    p("选择患者和核验时段。系统仅按已启用规则核验实际来源。"));
  const [label, patient] = input("核奖患者编号");
  const output = el("div", {"aria-live": "polite"});
  section.append(label);
  const getWindow = rangeControls(section);
  section.append(button("核验并登记正向积分", async v => {
    const id = patient.value.trim();
    if (!id) throw new Error("请填写要核验的虚构患者编号。");
    const window = pointsRange(getWindow);
    const {rules_version} = await api("/points/rules", "GET", null, v);
    const result = await api("/internal/points/reconcile", "POST", {patient_id: id, ...window, rules_version}, v);
    output.replaceChildren(p("新增奖励 " + result.new_entries.length + " 笔 · 当前余额 " + result.account.balance),
      p("已核验过的业务 " + result.skipped_keys.length + " 项", "muted"),
      result.new_entries.length ? el("ul", {}, ...result.new_entries.map(entry =>
        el("li", {}, pointLabels[entry.rule_code] + " +" + entry.delta))) : null,
      result.source_issues.length ? issuesView(result.source_issues) : null);
  }, "primary"), output);
  return section;
}
