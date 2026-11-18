"use strict";

const rewardAvailability = {available: "可兑换", unavailable: "暂不可用", unknown: "条件待核查"};
const fulfillmentStatus = {
  pending: "等待模拟履约", in_progress: "模拟履约处理中", completed: "已确认模拟交付",
  failed: "已确认未交付", cancelled: "已确认取消且未交付", outcome_unknown: "交付结果未知，请先核查原订单"
};

function rewardFeedback(detail, view) {
  const [label, participation] = select("评价参与", [["provided", "自愿填写"], ["declined", "不参加"], ["unable", "暂无法填写"]]);
  const experience = el("textarea", {rows: 2, maxLength: 2000});
  const result = p("");
  return el("details", {}, el("summary", {}, "自愿评价本次权益"), label, field("权益体验（可留空）", experience),
    button("保存权益体验", async v => {
      const body = {participation: participation.value,
                    experience: participation.value === "provided" ? experience.value.trim() || null : null,
                    service_feedback_id: null};
      await submitRewardFeedback(detail, body, v);
      result.textContent = "体验已保存。";
    }, "", false, view), result);
}

async function submitRewardFeedback(detail, body, view) {
  const key = "reward-feedback:" + view.accountId + ":" + detail + ":" + await sha(JSON.stringify(body));
  requireCurrentView(view);
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return api(detail + "/feedback", "POST", {client_feedback_id: id, ...body}, view);
}

function saveRewardText(artifact) {
  const url = URL.createObjectURL(new Blob([artifact.text], {type: "text/plain;charset=utf-8"}));
  el("a", {href: url, download: "模拟管理资料.txt"}).click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function rewardOrderRow(order, view) {
  const detail = "/redemptions/" + encodeURIComponent(order.redemption_id);
  const result = el("div", {"aria-live": "polite"});
  const row = el("li", {}, el("strong", {}, order.reward_name),
    p("兑换编号 " + order.redemption_id, "muted"),
    p((order.points_status === "refunded" ? "已全额退回 " : "原兑换扣减 ") + order.points_spent + " 积分"),
    button("查看交付结果", async v => {
      const [current, delivery] = await Promise.all([api(detail, "GET", null, v), api(detail + "/fulfillment", "GET", null, v)]);
      result.replaceChildren(p(fulfillmentStatus[delivery.status]), delivery.failure_reason ? p(delivery.failure_reason) : null,
        p(current.points_status === "refunded" ? "全额退分流水 " + current.refund_ledger_id : "原扣减流水 " + current.debit_ledger_id, "muted"),
        delivery.task_id ? p("原履约任务编号 " + delivery.task_id, "muted") : null,
        delivery.artifact ? el("pre", {}, delivery.artifact.text) : null,
        delivery.artifact ? button("保存模拟管理文本", () => saveRewardText(delivery.artifact)) : null,
        delivery.service_id ? button("查看关联的模拟服务", () => openServiceRecord(delivery.service_id)) : null,
        own() && ["completed", "failed"].includes(current.status) ? rewardFeedback(detail, v) : null);
    }, "", false, view), result);
  return row;
}

async function prepareRewardService(reward, output, path, view, checkout) {
  const resources = await all("/support-resources?channel=rewards");
  const resource = resources.find(item => item.resource_id === reward.resource_id);
  if (!resource) throw new Error("该权益的模拟人员资源暂不可用。");
  const question = el("textarea", {rows: 2, maxLength: 2000});
  const [label, consent] = checkbox("我核对了问题，并同意只共享本次支持问题");
  output.replaceChildren(p("模拟接收方 " + resource.provider.display_name), field("本次希望陪伴讨论的问题", question), label,
    button("保存并确认陪伴草稿", async v => {
      if (!question.value.trim() || !consent.checked) throw new Error("请本人填写并核对共享范围。");
      const draft = await serviceWrite(path + "/service-drafts", "POST", {
        resource_id: resource.resource_id, resource_version: resource.resource_version, request_text: question.value.trim()
      }, v);
      const saved = await serviceWrite(path + "/service-confirmations", "POST", {
        service_draft_id: draft.service_draft_id, draft_revision: draft.draft_revision,
        shared_categories: resource.required_shared_categories, confirmed: true
      }, v);
      output.replaceChildren(p("已确认共享本次支持问题。"), checkout({
        service_draft_id: draft.service_draft_id, draft_revision: draft.draft_revision,
        confirmation_ref_id: saved.confirmation_ref_id, sharing_scope_ref_id: saved.sharing_scope.sharing_scope_ref_id
      }));
    }, "", false, view));
}

async function redemptionPanel(path, view) {
  const section = el("section", {class: "panel"}, el("h2", {}, "额外权益与兑换记录"));
  const status = el("div", {"aria-live": "polite"});
  const pendingKey = "reward-pending:" + view.accountId + ":" + view.patientId;
  const post = path + "/redemptions";
  const orders = await all(post);
  requireCurrentView(view);
  const history = el("ol", {class: "list"}, ...[...orders].reverse().map(order => rewardOrderRow(order, view)));
  section.append(el("h3", {}, "兑换记录"), orders.length ? history : p("暂无兑换记录。", "muted"),
    button("刷新权益和订单", () => navigate("rewards")), status);

  async function send(body, v) {
    localStorage.setItem(pendingKey, JSON.stringify(body));
    try {
      const order = await api(post, "POST", body, v);
      localStorage.removeItem(pendingKey);
      await navigate("rewards");
      notice("已核实本次兑换。订单编号 " + order.redemption_id);
    } catch (error) {
      if (error instanceof ViewChanged) throw error;
      const rejected = error.status >= 400 && error.status < 500
        && !["OPERATION_IN_PROGRESS", "IDEMPOTENCY_EXPIRED"].includes(error.code);
      if (rejected) localStorage.removeItem(pendingKey);
      else status.replaceChildren(p("原提交结果待核查。先核对订单记录，重试会使用原兑换条件。"),
        button("用原条件核查兑换", v => send(body, v)));
      throw error;
    }
  }
  if (own() && localStorage.getItem(pendingKey)) {
    const original = JSON.parse(localStorage.getItem(pendingKey));
    status.append(p("存在待核查的兑换操作。"), button("用原条件核查兑换", v => send(original, v)));
  }

  const directory = el("div", {}, el("h3", {}, "虚构权益目录"));
  try {
    const rewards = await all("/rewards");
    requireCurrentView(view);
    const account = own() ? await api(path + "/points", "GET", null, view) : null;
    for (const reward of [...rewards].sort((a, b) => a.points_cost - b.points_cost)) {
      const output = el("div", {"aria-live": "polite"});
      const checkout = (service = {}) => button("确认兑换 " + reward.points_cost + " 积分", async v => {
        if (localStorage.getItem(pendingKey)) throw new Error("请先核查原兑换。");
        if (!window.confirm("确认使用 " + reward.points_cost + " 积分兑换「" + reward.name + "」？")) return;
        await send({reward_id: reward.reward_id, reward_version: reward.reward_version,
                    expected_account_revision: account.meta.revision, confirmed: true, ...service}, v);
      }, "primary", false, view);
      const canBuy = account && reward.availability === "available" && account.balance >= reward.points_cost;
      directory.append(el("details", {}, el("summary", {}, reward.name + " · " + reward.points_cost + " 积分"),
        p(reward.description), p(rewardAvailability[reward.availability] + " · 版本 " + reward.reward_version, "muted"),
        account && reward.availability === "available" && !canBuy ? p("当前余额不足。") : null,
        canBuy && reward.kind === "digital_content" ? checkout() : null,
        canBuy && reward.kind === "service_appointment" ? button("准备陪伴服务草稿", v => prepareRewardService(reward, output, path, v, checkout)) : null,
        output));
    }
  } catch (error) {
    requireCurrentView(view);
    directory.append(p(error.message, "error"));
  }
  section.prepend(directory);
  return section;
}

function rewardDemoControls() {
  const [label, task] = input("兑换履约任务编号");
  const result = p("");
  return el("section", {class: "panel"}, el("h2", {}, "兑换模拟履约"), label,
    button("显式运行兑换履约任务", async v => {
      const path = "/tasks/" + encodeURIComponent(task.value.trim());
      const current = await api(path, "GET", null, v);
      if (current.kind !== "fulfill_reward") throw new Error("此处只执行已登记的兑换履约任务。");
      const execution = await api(path + "/run", "POST", {expected_revision: current.meta.revision}, v);
      result.textContent = "原任务执行状态 " + labelFor(execution.execution_status) + "。交付事实请在原订单中核对。";
    }), result);
}
