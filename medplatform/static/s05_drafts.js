"use strict";

const servicePurposes = {
  community_assistance: "社区协助",
  emotional_companionship: "情感陪伴",
  pharmacist_consultation: "药学咨询"
};

function rememberServicePage() {
  if (!state.patient) return;
  const key = referenceKey("service-page");
  if (state.page === "support" && state.tab === "social" && scope("services:prepare") && scope("support:read")) {
    sessionStorage.setItem(key, "drafts");
  } else if (state.page === "profile" && state.tab === "service-consents" && own()) {
    sessionStorage.setItem(key, "consents");
  } else if (state.page === "profile" && state.tab === "formal-services" && scope("services:read")) {
    sessionStorage.setItem(key, "formal-services");
  } else {
    sessionStorage.removeItem(key);
  }
}

async function restoreServicePage() {
  if (!state.patient) return false;
  const page = sessionStorage.getItem(referenceKey("service-page"));
  if (page === "drafts" && scope("services:prepare") && scope("support:read")) {
    await navigate("support", "social");
    return true;
  }
  if (page === "consents" && own()) {
    await navigate("profile", "service-consents");
    return true;
  }
  if (page === "formal-services" && scope("services:read")) {
    await navigate("profile", "formal-services");
    return true;
  }
  return false;
}

function serviceWriteKey(path, method) {
  const {accountId, patientId} = captureView();
  return `reference:${accountId}:${patientId || "console"}:service-write:${method}:${path}`;
}

function pendingServiceWrite(path, method) {
  return JSON.parse(localStorage.getItem(serviceWriteKey(path, method)) || "null");
}

async function serviceWrite(path, method, body, view) {
  const hash = await sha(JSON.stringify(body));
  const contentHash = body.content ? await sha(JSON.stringify(body.content)) : null;
  const selectionHash = body.shared_categories ? await sha(JSON.stringify(body.shared_categories)) : null;
  requireCurrentView(view);
  const key = serviceWriteKey(path, method);
  const unsettled = pendingServiceWrite(path, method);
  if (unsettled && unsettled.hash !== hash) {
    throw new Error("上一次提交结果尚未核实。请用原值重试，或报出原草稿或确认编号核查。");
  }
  localStorage.setItem(key, JSON.stringify({
    hash, contentHash, selectionHash, revision: body.expected_revision ?? body.draft_revision ?? null,
    draftId: body.service_draft_id ?? null
  }));
  try {
    const result = await api(path, method, body, view);
    localStorage.removeItem(key);
    return result;
  } catch (error) {
    if (error.status < 500 && !error.pendingRecovery && error.code !== "OPERATION_IN_PROGRESS") {
      localStorage.removeItem(key);
    }
    throw error;
  }
}

async function reconcileServiceDraft(draft, view) {
  const draftPath = "/service-drafts/" + encodeURIComponent(draft.service_draft_id);
  const edit = pendingServiceWrite(draftPath, "PUT");
  if (edit && draft.meta.revision > edit.revision) {
    const {resource_id, resource_version, request_text} = draft;
    const current = await sha(JSON.stringify({resource_id, resource_version, request_text}));
    requireCurrentView(view);
    if (edit.contentHash === current && pendingServiceWrite(draftPath, "PUT")?.hash === edit.hash) {
      localStorage.removeItem(serviceWriteKey(draftPath, "PUT"));
    }
  }
  if (!own() || !draft.confirmation_ref_id) return;
  const path = patientPath("/service-confirmations"), confirm = pendingServiceWrite(path, "POST");
  if (confirm?.draftId !== draft.service_draft_id || confirm.revision !== draft.draft_revision) return;
  const value = await api("/service-confirmations/" + encodeURIComponent(draft.confirmation_ref_id), "GET", null, view);
  const categories = await sha(JSON.stringify([...value.sharing_scope.data_categories].sort()));
  requireCurrentView(view);
  if (confirm.selectionHash === categories && pendingServiceWrite(path, "POST")?.hash === confirm.hash) {
    localStorage.removeItem(serviceWriteKey(path, "POST"));
  }
}

function rememberServiceConsent(identifier) {
  const key = referenceKey("service-consent-history");
  const refs = (localStorage.getItem(key) || "").split(",").filter(Boolean);
  if (!refs.includes(identifier)) localStorage.setItem(key, [identifier, ...refs].join(","));
}

function serviceConsentText(consent) {
  const sharing = consent.sharing_scope;
  return el("div", {class: "item"},
    p(`共享确认：${statusLabels[consent.status]} · 目录版本 ${consent.resource_version}`, "status"),
    p(`接收主体 ${sharing.recipient_id}（模拟） · 用途 ${servicePurposes[sharing.purpose_code] || sharing.purpose_code}`),
    p(sharing.data_categories.map(category => sharedCategoryLabels[category]).join("、")),
    p(`确认于 ${dateText(consent.confirmed_at)}，截止于 ${dateText(consent.valid_until)}`, "muted"),
    p(`确认编号 ${consent.confirmation_ref_id}`, "reference"));
}

function serviceDraftPreparation(view) {
  const editor = el("div", {"aria-live": "polite"});
  const [label, reference] = input("草稿编号", localStorage.getItem(referenceKey("service-draft")) || "",
    "text", {maxLength: 128});
  const begin = readGate();
  const node = el("section", {}, el("h2", {}, "服务草稿"),
    p(own() ? "选择资源准备问题，或输入已有草稿编号。" : "可代录获准患者的问题。共享范围由患者本人确认。"),
    label, button("读取草稿", () => open(reference.value.trim())), editor);

  async function open(id, unsaved) {
    if (!id) throw new Error("请填写草稿编号。");
    const check = begin();
    try {
      const draft = await api("/service-drafts/" + encodeURIComponent(id), "GET", null, view);
      check();
      if (draft.patient_id !== view.patientId) throw new Error("请先切换到草稿所属的患者。");
      localStorage.setItem(referenceKey("service-draft"), id);
      reference.value = id;
      await reconcileServiceDraft(draft, view);
      check();
      let resource = null;
      try {
        resource = await api("/support-resources/" + encodeURIComponent(draft.resource_id), "GET", null, view);
      } catch (error) {
        if (error.status !== 404) throw error;
      }
      check();
      draw(draft, resource, unsaved);
    } catch (error) {
      check();
      if (error.status === 403 || error.status === 404) editor.replaceChildren();
      throw error;
    }
  }

  function draw(draft, resource, unsaved) {
    const check = begin();
    if (draft?.status === "submitted") {
      editor.replaceChildren(el("h3", {}, "已提交正式服务"),
        p(`草稿编号 ${draft.service_draft_id} · 内容修订 ${draft.draft_revision}`, "reference"),
        p(`服务编号 ${draft.service_id}`, "reference"));
      if (scope("services:read")) editor.append(button("查看正式服务", () => openServiceRecord(draft.service_id)));
      if (own()) clearKnownServiceSubmission(draft);
      return;
    }
    const textArea = el("textarea", {maxLength: 2000, rows: 4, value: unsaved ?? draft?.request_text ?? ""});
    const changedVersion = !!draft && !!resource && resource.resource_version !== draft.resource_version;
    const [upgradeLabel, upgrade] = checkbox("采用上面显示的当前目录版本");
    const consent = el("div", {"aria-live": "polite"});
    const saved = draft ? p(`已保存草稿 · 内容修订 ${draft.draft_revision} · 目录版本 ${draft.resource_version}`) : null;
    editor.replaceChildren(...[el("h3", {}, resource?.name || "原目录版本"),
      resource ? p(`目录版本 ${resource.resource_version} · mock/demo`, "muted") : p("原资源现已停用。草稿仍可查阅。"),
      saved, draft ? p(`草稿编号 ${draft.service_draft_id}`, "reference") : null,
      changedVersion ? upgradeLabel : null, field("本次服务问题", textArea),
      resource ? button(draft ? "保存草稿修改" : "保存草稿", async () => {
        if (!textArea.value.trim()) throw new Error("请填写本次服务问题。");
        if (changedVersion && !upgrade.checked) throw new Error("保存前请核对并选用当前目录版本。");
        const path = draft ? "/service-drafts/" + encodeURIComponent(draft.service_draft_id) : patientPath("/service-drafts");
        const content = {
          resource_id: resource.resource_id, resource_version: resource.resource_version, request_text: textArea.value.trim()
        };
        const body = draft ? {expected_revision: draft.meta.revision, content} : content;
        const typed = textArea.value;
        try {
          const result = await serviceWrite(path, draft ? "PUT" : "POST", body, view);
          check();
          await open(result.service_draft_id);
          notice("草稿已保存。");
        } catch (error) {
          check();
          if (draft && error.code === "SERVICE_DRAFT_REVISION_CONFLICT") await open(draft.service_draft_id, typed);
          throw error;
        }
      }, "primary") : null, consent].filter(Boolean));

    if (!draft) {
      textArea.focus();
      return;
    }
    if (!own()) return;
    if (draft.confirmation_ref_id) {
      rememberServiceConsent(draft.confirmation_ref_id);
      consent.append(p("此修订已有共享确认。"), button("查看确认及历史", () => navigate("profile", "service-consents")));
      consent.append(serviceSubmissionControls(draft, textArea, view, open));
      return;
    }
    if (!resource || changedVersion) return;
    const [explicitLabel, explicit] = checkbox("我已核对本次问题、接收主体和共享范围");
    const optional = resource.optional_shared_categories.map(category => [category, ...checkbox(sharedCategoryLabels[category])]);
    const required = resource.required_shared_categories;
    consent.append(el("h3", {}, "本人确认共享范围"),
      p(`接收主体 ${resource.provider.display_name} · 用途 ${servicePurposes[resource.service_kind]}`),
      p(`必要类别 ${required.map(category => sharedCategoryLabels[category]).join("、") || "无"}`),
      p("有效期为首次确认后 24 小时。相同范围的有效同意沿用原截止时间。", "muted"),
      ...(optional.length ? [el("fieldset", {}, el("legend", {}, "可选共享类别"), optional.map(([, item]) => item))] : []),
      explicitLabel, button("明确确认共享范围", async () => {
        if (textArea.value.trim() !== draft.request_text) throw new Error("请先保存本次修改，再核对新草稿。");
        if (!explicit.checked) throw new Error("请先勾选本人核对。");
        const body = {
          service_draft_id: draft.service_draft_id, draft_revision: draft.draft_revision,
          shared_categories: [...required, ...optional.filter(([, , control]) => control.checked).map(([category]) => category)].sort(),
          confirmed: true
        };
        try {
          const value = await serviceWrite(patientPath("/service-confirmations"), "POST", body, view);
          check();
          rememberServiceConsent(value.confirmation_ref_id);
          consent.replaceChildren(serviceConsentText(value), p("草稿仍处于准备阶段。"),
            button("查看确认及历史", () => navigate("profile", "service-consents")));
          if (value.status === "active") {
            consent.append(serviceSubmissionControls({...draft, confirmation_ref_id: value.confirmation_ref_id,
              sharing_scope_ref_id: value.sharing_scope.sharing_scope_ref_id}, textArea, view, open));
          }
          notice(value.status === "active" ? "已记录本次共享确认。" : "已核对原提交，当前共享范围已失效。");
        } catch (error) {
          check();
          if (error.code === "SHARING_CONFIRMATION_REQUIRED" && !error.pendingRecovery) {
            const latest = await api("/service-drafts/" + encodeURIComponent(draft.service_draft_id), "GET", null, view);
            check();
            if (latest.meta.revision !== draft.meta.revision) await open(draft.service_draft_id, textArea.value);
          }
          throw error;
        }
      }, "primary"));
  }

  return {
    node,
    prepare(resource) { draw(null, resource); },
    async restore() {
      if (reference.value) {
        try {
          await open(reference.value);
        } catch (error) {
          if (error instanceof ViewChanged) throw error;
          editor.replaceChildren(p(error.message, "error"));
        }
      }
    }
  };
}

function serviceConsentView() {
  if (!own()) return;
  const view = captureView(), begin = readGate();
  const history = el("div", {class: "actions"});
  const current = el("div", {"aria-live": "polite"});
  const [label, reference] = input("确认编号", "", "text", {maxLength: 128});
  const refs = (localStorage.getItem(referenceKey("service-consent-history")) || "").split(",").filter(Boolean);
  function addReference(id) {
    history.append(button(id, () => { reference.value = id; return load(id); }));
  }
  for (const id of refs) addReference(id);
  main.append(el("section", {}, el("h2", {}, "服务授权"),
    p("可查看本浏览器记录的共享确认，或输入已知确认编号。"), history, label,
    button("读取确认", () => load(reference.value.trim())), current));

  function show(value, unsavedReason = "") {
    current.replaceChildren(serviceConsentText(value));
    if (value.status === "revoked") return;
    const [reasonLabel, reason] = input("撤销原因", unsavedReason, "text", {maxLength: 500});
    const [explicitLabel, explicit] = checkbox("明确撤销此共享范围");
    current.append(reasonLabel, explicitLabel, button("撤销共享授权", async () => {
      if (!explicit.checked || !reason.value.trim()) throw new Error("请填写原因并明确勾选撤销。");
      const check = begin();
      try {
        const result = await serviceWrite("/service-confirmations/" + encodeURIComponent(value.confirmation_ref_id) + "/revoke",
          "POST", {expected_revision: value.meta.revision, reason: reason.value.trim()}, view);
        check();
        show(result);
        notice("共享范围已撤销。");
      } catch (error) {
        check();
        if (error.code === "CONFIRMATION_REVISION_CONFLICT") {
          await load(value.confirmation_ref_id, reason.value);
        }
        throw error;
      }
    }, "danger"));
  }

  async function load(id, unsavedReason) {
    if (!id) throw new Error("请填写确认编号。");
    const check = begin();
    current.replaceChildren();
    const result = await api("/service-confirmations/" + encodeURIComponent(id), "GET", null, view);
    check();
    if (!refs.includes(id)) {
      refs.push(id);
      addReference(id);
    }
    rememberServiceConsent(id);
    localStorage.setItem(referenceKey("service-consent"), id);
    if (result.status === "revoked") {
      localStorage.removeItem(serviceWriteKey("/service-confirmations/" + encodeURIComponent(id) + "/revoke", "POST"));
    }
    show(result, unsavedReason);
  }
  const last = localStorage.getItem(referenceKey("service-consent")) || refs[0];
  if (last) {
    reference.value = last;
    return load(last);
  }
}
