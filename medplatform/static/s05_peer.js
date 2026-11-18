"use strict";

const peerAvailability = {available: "可申请", unavailable: "暂不可申请", unknown: "可用性未知"};
const peerReviewStatus = {pending: "待审", visible: "已公开", hidden: "已隐藏"};

function peerPath(group) {
  return "/peer-groups/" + encodeURIComponent(group);
}

function openPeer(group) {
  sessionStorage.setItem(referenceKey("peer-group"), group);
  return navigate("support", "peer");
}

function peerJoinRequest(draft) {
  return {service_draft_id: draft.service_draft_id, draft_revision: draft.draft_revision,
    confirmation_ref_id: draft.confirmation_ref_id, sharing_scope_ref_id: draft.sharing_scope_ref_id};
}

function peerResumeFromDraft(draft) {
  return openPeer(draft.peer_group_id);
}

function peerJoinControls(draft, textArea, view) {
  const [label, confirmed] = checkbox("我本人自愿申请加入此模拟小组");
  return el("div", {}, label, button("提交入组申请", async () => {
    if (!confirmed.checked || textArea.value.trim() !== draft.request_text) {
      throw new Error("请先核对已保存草稿并明确自愿加入。");
    }
    const path = peerPath(draft.peer_group_id) + "/memberships";
    const body = peerJoinRequest(draft);
    let member;
    try {
      member = await serviceWrite(path, "POST", body, view);
    } catch (error) {
      if (error instanceof ViewChanged || (error.status && error.status < 500 && error.code !== "OPERATION_IN_PROGRESS")) {
        throw error;
      }
      const current = await api("/service-drafts/" + encodeURIComponent(draft.service_draft_id), "GET", null, view);
      if (!current.service_id || current.draft_revision !== draft.draft_revision) throw error;
      member = await serviceWrite(path, "POST", body, view);
    }
    requireCurrentView(view);
    await openPeer(member.group_id);
    notice("已登记模拟入组申请。");
  }, "primary"));
}

function peerPostItem(doc) {
  return el("article", {class: "item"},
    p(`${doc.author_alias} · ${peerReviewStatus[doc.moderation_status]}`, "status"),
    p(doc.content), p(dateText(doc.created_at), "muted"));
}

async function peerHomeMembership() {
  const view = captureView();
  const memberships = await all("/peer-memberships/me");
  requireCurrentView(view);
  const current = memberships.find(doc => doc.status !== "left");
  if (current) main.append(button("查看我的同辈小组", () => openPeer(current.group_id)));
}

let resumePeerFeed = null;
window.addEventListener("pagehide", () => resumePeerFeed?.clear());
window.addEventListener("pageshow", event => { if (event.persisted) resumePeerFeed?.resume(); });
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") resumePeerFeed?.clear();
  else resumePeerFeed?.resume();
});

async function peerSupportView() {
  if (!scope("peer:read")) {
    main.append(p("请先获得小组介绍读取权限。"));
    return;
  }
  const view = captureView();
  const area = el("section", {}, el("h2", {}, "匿名同辈支持"),
    p("虚构小组 · 自愿参与 · 短文字经模拟审核后公开。请勿填写姓名、账号、联系方式或诊疗资料。"));
  const detail = el("div", {"aria-live": "polite"});
  main.append(area, detail);
  const [groups, saved] = await Promise.all([all("/peer-groups"), own() ? all("/peer-memberships/me") : []]);
  requireCurrentView(view);
  if (!groups.length) {
    area.append(p("目前没有登记的小组。"));
    return;
  }
  const key = referenceKey("peer-group");
  const selected = sessionStorage.getItem(key) || saved.find(member => member.status !== "left")?.group_id;
  const [label, group] = select("同辈小组", groups.map(doc => [doc.group_id, doc.title]),
    groups.some(doc => doc.group_id === selected) ? selected : groups[0].group_id);
  const begin = readGate();
  area.append(label, button("查看小组", load));
  group.addEventListener("change", () => {
    begin();
    detail.replaceChildren();
  });

  async function load() {
    const check = begin(), id = group.value;
    detail.replaceChildren();
    const doc = await api(peerPath(id), "GET", null, view);
    check();
    sessionStorage.setItem(key, id);
    detail.append(el("h3", {}, doc.title), p(doc.description),
      p(`${peerAvailability[doc.availability]} · ${doc.moderator_label}`, "status"),
      p("小组主题 · " + doc.matching_tags.join("、"), "muted"),
      p(`小组编号 ${id}`, "reference"));
    if (!own()) {
      detail.append(p("当前授权允许查看小组介绍。", "muted"));
      return;
    }
    const memberships = await all("/peer-memberships/me");
    check();
    const reference = memberships.find(member => member.group_id === id && member.status !== "left");
    if (reference) {
      const memberState = reference.status === "pending" ? "等待模拟受理" :
        reference.can_participate ? "已受理" : "当前交流受限";
      detail.append(p(`本人匿名身份 ${reference.alias} · ${memberState} · 修订 ${reference.revision}`, "reference"));
      detail.append(p(`本人成员编号 ${reference.membership_id}`, "reference"));
    } else if (memberships.some(member => member.group_id === id && member.status === "left")) {
      detail.append(p("本人此前已退出此组。", "muted"));
    }
    let service = null;
    if (reference) {
      try {
        service = await api("/services/" + encodeURIComponent(reference.service_id), "GET", null, view);
        check();
        detail.append(p(`入组服务 ${service.service_id} · ${formalServiceStates[service.status]}`, "reference"));
      } catch (error) {
        check();
        if (error.status !== 404 && error.status !== 403) throw error;
      }
    }
    const status = el("div", {"aria-live": "polite"});
    const posts = el("div", {});
    const compose = el("div", {});
    let feedRequest = 0;
    const actions = el("div", {class: "actions"}, button("刷新小组状态", load));
    if (!reference && doc.availability === "available" && scope("services:prepare") && scope("support:read")) {
      actions.append(button("准备本组申请", () => {
        sessionStorage.setItem(referenceKey("peer-prepare-resource"), doc.resource_id);
        return navigate("support", "social");
      }, "primary"));
    }
    if (reference) actions.append(button("退出本组", async () => {
      if (!window.confirm("确认自愿退出此小组？")) return;
      const path = "/memberships/" + encodeURIComponent(reference.membership_id) + "/leave";
      try {
        await serviceWrite(path, "POST", {expected_revision: reference.revision}, view);
        check();
      } catch (error) {
        check();
        await load();
        throw error;
      }
      posts.replaceChildren();
      compose.replaceChildren();
      await load();
      notice("已退出本组。");
    }, "danger"));
    detail.append(actions, status, posts, compose);

    async function loadPosts(cursor = null) {
      check();
      const request = ++feedRequest;
      if (!cursor) {
        posts.replaceChildren();
        compose.replaceChildren();
      }
      try {
        const query = cursor ? "?cursor=" + encodeURIComponent(cursor) : "";
        const page = await api(peerPath(id) + "/posts" + query, "GET", null, view);
        check();
        if (request !== feedRequest || document.visibilityState === "hidden") return;
        status.replaceChildren(p("本人可以在此组交流。", "status"));
        if (!cursor && !page.items.length) posts.append(p("当前没有可见文字。", "muted"));
        if (cursor) posts.lastChild?.remove();
        posts.append(...page.items.map(peerPostItem));
        if (page.next_cursor) posts.append(button("读取更多文字", () => loadPosts(page.next_cursor)));
        if (!cursor && scope("peer:participate")) compose.append(postComposer(id, view, check, loadPosts));
      } catch (error) {
        check();
        if (request !== feedRequest || document.visibilityState === "hidden") return;
        posts.replaceChildren();
        compose.replaceChildren();
        if (error.status !== 403 && error.status !== 404) {
          status.replaceChildren(p("暂无法核验小组交流权限。", "error"));
          return;
        }
        status.replaceChildren(p(reference?.status === "pending" && service?.status === "submitted" ? "正在等待模拟受理，交流尚未开放。" :
          "当前没有有效交流资格。", "muted"));
      }
    }
    resumePeerFeed = {
      clear() {
        if (isCurrentView(view) && posts.isConnected) {
          feedRequest++;
          posts.replaceChildren();
          compose.replaceChildren();
        }
      },
      resume() {
        if (isCurrentView(view) && posts.isConnected) loadPosts().catch(error => {
          if (!(error instanceof ViewChanged)) notice(error.message, true);
        });
      }
    };
    await loadPosts();
  }
  await load();
}

function postComposer(group, view, check, reload) {
  const area = el("textarea", {rows: 3, maxLength: 1000});
  const key = referenceKey("peer-post-submission:" + group);
  const pending = () => JSON.parse(sessionStorage.getItem(key) || "null");
  return el("div", {}, field("匿名短文字", area), button("提交文字待审", async () => {
    const content = area.value.trim();
    if (!content) throw new Error("请填写一段短文字。");
    const fingerprint = await sha(content);
    check();
    const known = pending();
    if (known && known.fingerprint !== fingerprint) throw new Error("原提交尚未核实，请先用原文字重试。");
    const clientId = known?.clientId || crypto.randomUUID();
    sessionStorage.setItem(key, JSON.stringify({fingerprint, clientId}));
    try {
      await api(peerPath(group) + "/posts", "POST", {client_post_id: clientId, content}, view);
      check();
      sessionStorage.removeItem(key);
      await reload();
      notice("文字已提交，公开状态以审核结果为准。");
    } catch (error) {
      if (error instanceof ViewChanged) throw error;
      if (error.status < 500 && !error.pendingRecovery && error.code !== "OPERATION_IN_PROGRESS") {
        if (pending()?.clientId === clientId) sessionStorage.removeItem(key);
      }
      if (error.status === 403 || error.status === 404) await reload();
      throw error;
    }
  }, "primary"));
}

function peerModerationControls() {
  const [label, group] = input("审核小组编号", "", "text", {maxLength: 128});
  const results = el("div", {"aria-live": "polite"});
  const begin = readGate();
  async function load(view, cursor = null) {
    const check = begin(), id = group.value.trim();
    if (!id) throw new Error("请填写已登记的审核小组编号。");
    if (!cursor) results.replaceChildren();
    const query = new URLSearchParams({include_pending: "true"});
    if (cursor) query.set("cursor", cursor);
    const value = await api(peerPath(id) + "/posts?" + query, "GET", null, view);
    check();
    if (cursor) results.lastChild?.remove();
    for (const doc of value.items) {
      const item = peerPostItem(doc);
      const [reasonLabel, reason] = input("模拟审核说明", "", "text", {maxLength: 500});
      const act = decision => async v => {
        check();
        if (!reason.value.trim()) throw new Error("请填写模拟审核依据。");
        await serviceWrite("/peer-posts/" + encodeURIComponent(doc.post_id) + "/moderation", "POST",
          {expected_revision: doc.revision, decision, reason: reason.value.trim()}, v);
        await load(v);
        notice("已保存模拟审核。");
      };
      item.append(reasonLabel);
      if (doc.moderation_status === "pending") item.append(button("允许匿名公开", act("visible"), "primary"));
      item.append(button("隐藏此文字", act("hidden")));
      results.append(item);
    }
    if (!cursor && !value.items.length) results.append(p("该组暂无待审或公开文字。", "muted"));
    if (value.next_cursor) results.append(button("读取下一页审核队列", v => load(v, value.next_cursor)));
  }
  group.addEventListener("input", () => {
    begin();
    results.replaceChildren();
  });
  return el("section", {class: "panel"}, el("h2", {}, "模拟同辈文字审核"),
    p("当前组授权内检查身份隐私和文字安全。"), label, button("读取本组审核队列", v => load(v)), results);
}
