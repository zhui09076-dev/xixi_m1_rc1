(() => {
  "use strict";

  const app = document.getElementById("app");
  const rail = document.getElementById("rail");
  const library = document.getElementById("app-library");
  const mainPanel = document.getElementById("main-panel");
  const panelContent = document.getElementById("panel-content");
  const composer = document.getElementById("composer");
  const composerInput = document.getElementById("composer-input");
  const composerSend = document.getElementById("composer-send");
  const quietIndicator = document.getElementById("quiet-indicator");
  const permission = document.getElementById("permission");
  const toast = document.getElementById("toast");
  const statusMain = document.querySelector(".status-main");
  const statusDot = document.querySelector(".status-dot");

  const icon = (name) => `<img class="icon" src="assets/icons/${name}.svg" alt=""/>`;

  const templates = {
    chat: `
      <div class="panel-header">
        <div class="panel-heading">
          <div class="panel-title">对话</div>
          <div class="panel-subtitle">本地模型 · 可随时打断</div>
        </div>
        <button class="icon-button" data-action="minimize-panel">${icon("minimize")}</button>
        <button class="icon-button" data-action="close-panel">${icon("close")}</button>
      </div>
      <div class="panel-body">
        <div class="chat-scroll">
          <div class="message system">今天 01:15 · 本地会话</div>
          <div class="message">Soul RC1已经整理完，但还要等真实容器和模型联调。</div>
          <div class="message user">继续下一个任务。</div>
          <div class="message">好。现在只做正式UI，不再围着灵魂补说明。</div>
          <div class="message user">界面别做成普通后台。</div>
          <div class="message">嗯。平时几乎不出现，只有需要时才打开小面板。</div>
        </div>
        <div class="chat-inline-actions">
          <button class="text-button" data-action="simulate-stream">模拟生成</button>
          <button class="text-button danger" data-action="interrupt">${icon("stop")} 中断</button>
        </div>
      </div>`,
    project: `
      <div class="panel-header">
        <div class="panel-heading">
          <div class="panel-title">项目</div>
          <div class="panel-subtitle">只显示当前需要关注的内容</div>
        </div>
        <button class="icon-button" data-action="close-panel">${icon("close")}</button>
      </div>
      <div class="panel-body project-content">
        <div class="project-hero">
          <div class="tiny muted">当前项目</div>
          <div class="project-name">西西桌面伴侣</div>
          <div class="small secondary" style="margin-top:7px">灵魂候选版完成 · UI RC1制作中</div>
          <div class="project-progress"><span></span></div>
        </div>
        <div class="section-label">已确认决定</div>
        <div class="info-card"><strong>分工</strong><p>KM负责容器；内容侧负责灵魂、身体和UI。</p></div>
        <div class="info-card"><strong>桌面形态</strong><p>人物与公寓构成桌面；普通应用可以覆盖西西。</p></div>
        <div class="section-label">当前阻塞</div>
        <div class="info-card"><strong>身体资产</strong><p>需在干净对话生成身份一致的全身母版。</p></div>
        <div class="section-label">下一步</div>
        <div class="info-card"><strong>完成UI状态与多分辨率验证</strong><p>再根据容器真实接口做最终接入格式。</p></div>
      </div>`,
    note: `
      <div class="panel-header">
        <div class="panel-heading">
          <div class="panel-title">快速记录</div>
          <div class="panel-subtitle">原文不会被摘要覆盖</div>
        </div>
        <button class="icon-button" data-action="close-panel">${icon("close")}</button>
      </div>
      <div class="panel-body">
        <textarea class="note-area" id="note-area">当前会话不再生成身体图片；身体资产放到干净对话处理。这里继续完成正式UI内容。</textarea>
        <div class="note-footer">
          <span class="tiny muted" style="flex:1">保存为项目原始记录</span>
          <button class="text-button" data-action="save-note">保存</button>
        </div>
      </div>`,
    todo: `
      <div class="panel-header">
        <div class="panel-heading">
          <div class="panel-title">待办</div>
          <div class="panel-subtitle">一个重任务 + 一个轻任务</div>
        </div>
        <button class="icon-button" data-action="close-panel">${icon("close")}</button>
      </div>
      <div class="panel-body todo-list">
        <div class="todo-item"><span class="todo-check"></span><div class="todo-text">完成UI四种状态与三种屏幕比例<div class="todo-tag">主要任务</div></div></div>
        <div class="todo-item done"><span class="todo-check"></span><div class="todo-text">Soul RC1结构与静态测试</div></div>
        <div class="todo-item"><span class="todo-check"></span><div class="todo-text">在本机Ollama运行真实行为回归<div class="todo-tag">等待容器</div></div></div>
        <div class="todo-item"><span class="todo-check"></span><div class="todo-text">新对话生成正式身体身份母版</div></div>
      </div>`,
    model: `
      <div class="panel-header">
        <div class="panel-heading">
          <div class="panel-title">模型</div>
          <div class="panel-subtitle">模型是工具，不是西西身份</div>
        </div>
        <button class="icon-button" data-action="close-panel">${icon("close")}</button>
      </div>
      <div class="panel-body">
        <div class="model-card">
          <div class="model-status-line"><span class="status-dot"></span><span class="small">Ollama · 已连接</span></div>
          <div class="model-name">richardyoung/qwen3.6-27b-abliterated:latest</div>
          <div class="model-metrics">
            <div class="metric"><b>65K</b><span>当前上下文</span></div>
            <div class="metric"><b>24 GB</b><span>显存上限</span></div>
            <div class="metric"><b>本地</b><span>数据路径</span></div>
            <div class="metric"><b>按需</b><span>加载方式</span></div>
          </div>
        </div>
        <div style="padding:0 14px 14px;display:flex;gap:8px">
          <button class="text-button">卸载模型</button>
          <button class="text-button primary">切换模型</button>
        </div>
      </div>`,
    settings: `
      <div class="panel-header">
        <div class="panel-heading">
          <div class="panel-title">设置</div>
          <div class="panel-subtitle">只保留日常真正会用到的选项</div>
        </div>
        <button class="icon-button" data-action="close-panel">${icon("close")}</button>
      </div>
      <div class="panel-body settings-list">
        <div class="setting-row"><div class="setting-copy"><div class="setting-name">中度主动</div><div class="setting-desc">提醒阻塞，但不频繁刷存在感</div></div><div class="switch on"></div></div>
        <div class="setting-row"><div class="setting-copy"><div class="setting-name">安静模式</div><div class="setting-desc">只保留必要提醒</div></div><div class="switch"></div></div>
        <div class="setting-row"><div class="setting-copy"><div class="setting-name">自然语言记忆控制</div><div class="setting-desc">支持记住、纠正、不记和删除</div></div><div class="switch on"></div></div>
        <div class="setting-row"><div class="setting-copy"><div class="setting-name">开机恢复</div><div class="setting-desc">恢复上次稳定状态</div></div><div class="switch on"></div></div>
        <div class="setting-row"><div class="setting-copy"><div class="setting-name">权限管理</div><div class="setting-desc">查看和撤销目录、网络与账号权限</div></div><button class="text-button" data-action="show-permission">查看</button></div>
      </div>`
  };

  let activePanel = null;
  let mode = "quiet";

  function setStatus(label, color) {
    statusMain.textContent = `西西 · ${label}`;
    statusDot.style.background = color || "var(--success)";
  }

  function showToast(text) {
    toast.textContent = text;
    toast.classList.add("is-visible");
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => toast.classList.remove("is-visible"), 1600);
  }

  function closeLibrary() {
    library.classList.remove("is-open");
    rail.classList.remove("is-expanded");
  }

  function toggleLibrary() {
    const open = !library.classList.contains("is-open");
    library.classList.toggle("is-open", open);
    rail.classList.toggle("is-expanded", open);
  }

  function openPanel(name) {
    closeLibrary();
    activePanel = name;
    panelContent.innerHTML = templates[name];
    mainPanel.classList.add("is-open");
    document.querySelectorAll("[data-panel]").forEach(el => {
      el.classList.toggle("is-active", el.dataset.panel === name);
    });
    composer.classList.toggle("is-hidden", name !== "chat");
    quietIndicator.classList.remove("is-visible");
    if (name === "chat") setStatus("交流中", "var(--accent-cool)");
    else if (name === "project" || name === "note" || name === "todo") setStatus("工作中", "var(--accent-warm)");
    else setStatus("清醒", "var(--success)");
  }

  function closePanel() {
    activePanel = null;
    mainPanel.classList.remove("is-open");
    document.querySelectorAll("[data-panel]").forEach(el => el.classList.remove("is-active"));
    if (mode === "quiet") {
      composer.classList.add("is-hidden");
      quietIndicator.classList.add("is-visible");
      setStatus("安静陪伴", "var(--success)");
    } else {
      composer.classList.remove("is-hidden");
      setStatus("清醒", "var(--success)");
    }
  }

  function setMode(next) {
    mode = next;
    app.dataset.mode = next;
    permission.classList.remove("is-open");
    if (next === "quiet") {
      closePanel();
      composer.classList.add("is-hidden");
      quietIndicator.classList.add("is-visible");
      setStatus("安静陪伴", "var(--success)");
    } else if (next === "chat") {
      openPanel("chat");
    } else if (next === "work") {
      openPanel("project");
    } else if (next === "permission") {
      closePanel();
      composer.classList.add("is-hidden");
      quietIndicator.classList.remove("is-visible");
      permission.classList.add("is-open");
      setStatus("等待确认", "var(--warning)");
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action],[data-panel]");
    if (!button) return;

    if (button.dataset.panel) {
      openPanel(button.dataset.panel);
      return;
    }

    const action = button.dataset.action;
    if (action === "toggle-library") toggleLibrary();
    if (action === "close-library") closeLibrary();
    if (action === "close-panel" || action === "minimize-panel") closePanel();
    if (action === "save-note") showToast("原始记录已保存");
    if (action === "show-permission") setMode("permission");
    if (action === "deny-permission") { permission.classList.remove("is-open"); setMode("quiet"); showToast("已取消"); }
    if (action === "allow-once") { permission.classList.remove("is-open"); setMode("work"); showToast("仅本次授权"); }
    if (action === "allow-scope") { permission.classList.remove("is-open"); setMode("work"); showToast("此范围已授权"); }
    if (action === "interrupt") {
      setStatus("已停止", "var(--danger)");
      showToast("生成已中断");
    }
    if (action === "simulate-stream") {
      setStatus("生成中", "var(--accent-cool)");
      showToast("正在生成，可随时中断");
    }
  });

  document.querySelectorAll(".switch").forEach(sw => {
    sw.addEventListener("click", () => sw.classList.toggle("on"));
  });

  composerSend.addEventListener("click", () => {
    const text = composerInput.value.trim();
    if (!text) return;
    composerInput.value = "";
    if (activePanel !== "chat") openPanel("chat");
    const scroll = document.querySelector(".chat-scroll");
    if (scroll) {
      const msg = document.createElement("div");
      msg.className = "message user";
      msg.textContent = text;
      scroll.appendChild(msg);
      scroll.scrollTop = scroll.scrollHeight;
    }
    setStatus("生成中", "var(--accent-cool)");
    showToast("消息已发送");
  });

  composerInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      composerSend.click();
    }
  });

  const params = new URLSearchParams(location.search);
  setMode(params.get("mode") || "quiet");
})();
