"use strict";

const sharedCategoryLabels = {
  support_question: "支持问题",
  medication_plan: "正式用药安排",
  medication_records: "服药记录",
  profile_summary: "画像摘要"
};
const qualificationLabels = {not_required: "无需专业资质", not_verified: "资质未核验"};

async function socialSupportView() {
  if (!scope("support:read")) {
    main.append(p("请先选择本人或获准查看社会支持的对象。"));
    return;
  }
  const view = captureView();
  const [label, need] = select("本次支持需求", [
    ["", "使用已有明确需求"],
    ["practical", "实际生活协助"],
    ["emotional", "情感陪伴"],
    ["professional", "药学咨询"],
    ["none", "暂不需要支持"]
  ], "");
  const result = el("div", {"aria-live": "polite"});
  const detail = el("section", {"aria-label": "资源详情", "aria-live": "polite", hidden: true, tabIndex: -1});
  const directory = el("div", {});
  const startMatch = readGate(), startDetail = readGate();

  function clearDetail() {
    startDetail();
    detail.replaceChildren();
    detail.hidden = true;
  }

  async function openDetail(id, version) {
    clearDetail();
    const check = startDetail();
    const doc = await api("/support-resources/" + encodeURIComponent(id), "GET", null, view);
    check();
    if (doc.resource_version !== version) {
      throw new Error("资源版本已更新，请刷新目录或重新匹配。");
    }
    const labels = names => names.map(name => sharedCategoryLabels[name]).join("、") || "无";
    detail.replaceChildren(el("h2", {}, doc.name), p(doc.description),
      p(`版本 ${doc.resource_version} · mock/demo`, "muted"),
      p(`${doc.provider.display_name} · ${qualificationLabels[doc.provider.qualification_status]}`),
      p(`潜在的必要共享类别　${labels(doc.required_shared_categories)}`),
      p(`潜在的可选共享类别　${labels(doc.optional_shared_categories)}`));
    detail.hidden = false;
    detail.focus();
  }

  function showMatch(data) {
    result.replaceChildren(el("h2", {}, "匹配结果"));
    const refs = data.source_refs.filter(ref => ref.module === "C" && ref.record_kind === "support_resource");
    const profile = data.source_refs.find(ref => ref.module === "O" && ref.record_kind === "profile");
    if (profile) result.append(p(`O 画像 ${profile.record_id} · 修订 ${profile.version}`, "reference"));
    if (data.need_status === "none") result.append(p("本次暂不需要支持。"));
    if (data.need_status === "insufficient") result.append(p("当前信息不足，无法确定资源。"));
    const actions = [data.primary_action, ...data.secondary_actions].filter(Boolean);
    for (const action of actions) {
      const ref = refs.find(item => item.record_id === action.resource_id);
      result.append(el("div", {class: "item"}, el("strong", {}, action.title), p(action.reason),
        p(`版本 ${ref.version} · mock/demo`, "muted"),
        button("查看候选详情", () => openDetail(ref.record_id, ref.version))));
    }
    if (!actions.length && refs.length) {
      result.append(el("ul", {}, ...refs.map(ref => el("li", {},
        button(`${ref.record_id} · ${ref.version}`, () => openDetail(ref.record_id, ref.version))))));
    }
    if (data.missing_items.length) result.append(issuesView(data.missing_items));
  }

  need.addEventListener("change", () => {
    startMatch();
    clearDetail();
    result.replaceChildren();
  });
  const form = el("section", {}, el("h2", {}, "社会支持"),
    p("这里展示虚构资源和匹配依据。查看目录与匹配均不会提交申请或共享资料。"),
    scope("profile:read") ? button("查看已登记画像", () => navigate("profile", "assessment")) :
      p("当前授权不含画像读取。", "muted"),
    label, button("查看匹配", async () => {
      const check = startMatch();
      clearDetail();
      result.replaceChildren(p("正在匹配…", "muted"));
      try {
        const query = need.value ? "?need=" + encodeURIComponent(need.value) : "";
        const data = await api(patientPath("/support-recommendations") + query, "GET", null, view);
        check();
        showMatch(data);
      } catch (error) {
        check();
        result.replaceChildren();
        throw error;
      }
    }, "primary"), result);
  main.append(form, detail, el("section", {}, el("h2", {}, "可用资源"), directory));

  async function load(cursor = null) {
    const query = cursor ? "?cursor=" + encodeURIComponent(cursor) : "";
    const page = await api("/support-resources" + query, "GET", null, view);
    directory.replaceChildren();
    if (!page.items.length) directory.append(p("当前没有可用的虚构资源。", "empty"));
    for (const doc of page.items) {
      directory.append(el("div", {class: "item"}, el("strong", {}, doc.name),
        p(`版本 ${doc.resource_version} · mock/demo`, "muted"),
        button("查看资源详情", () => openDetail(doc.resource_id, doc.resource_version))));
    }
    if (page.next_cursor) directory.append(button("下一页资源", () => load(page.next_cursor)));
    if (cursor) directory.append(button("返回资源首页", () => load()));
  }
  await load();
}
