"use strict";
const pages = {
  home: ["欢迎来到用药支持平台", "平台基础服务已建立。用药记录、支持对话与服务申请将在后续阶段开放。"],
  medication: ["用药管理", "这里将提供药品、资料与计划核对、今日安排和提醒。本阶段尚未开放这些功能。"],
  support: ["支持服务", "这里将提供 AI 情感支持和社会支持。当前尚未连接对话模型或实际服务方。"],
  rewards: ["积分权益", "这里将提供积分、规则和自愿兑换。当前没有生成账户、余额或兑换记录。"],
  profile: ["我的", "这里将提供身份、画像与家庭授权等功能。账号业务将在后续阶段接入。"]
};
for (const button of document.querySelectorAll("nav button")) {
  button.addEventListener("click", () => {
    const [title, description] = pages[button.dataset.page];
    document.querySelector("#page-title").textContent = title;
    document.querySelector("#page-description").textContent = description;
    for (const item of document.querySelectorAll("nav button")) item.removeAttribute("aria-current");
    button.setAttribute("aria-current", "page");
  });
}
async function checkHealth() {
  const button = document.querySelector("#refresh");
  const output = document.querySelector("#health");
  button.disabled = true;
  output.textContent = "正在检查…";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 7000);
  try {
    const response = await fetch("/api/v1/health", {signal: controller.signal, cache: "no-store"});
    const result = await response.json();
    if (!response.ok || result.status !== "success") {
      output.textContent = "基础服务尚未就绪，请查看启动说明或稍后重新检查。";
    } else {
      output.textContent = "基础服务已就绪。后续功能尚未开放。";
    }
  } catch {
    output.textContent = "暂时无法连接基础服务，请确认本地服务已启动后重新检查。";
  } finally {
    clearTimeout(timer);
    button.disabled = false;
  }
}
document.querySelector("#refresh").addEventListener("click", checkHealth);
checkHealth();
