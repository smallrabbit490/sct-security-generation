/* 离线工作台：题面一律通过 textContent 呈现，材料中的 HTML/脚本不执行。 */
(function () {
  "use strict";
  const C = window.ReviewCore;
  const data = JSON.parse(document.getElementById("review-data").textContent);
  const tasks = data.tasks, ids = tasks.map(t => t.review_id);
  const byId = new Map(tasks.map(t => [t.review_id, t]));
  const $ = id => document.getElementById(id);
  const storageKey = `sct-human-review-v1:${data.dataset_hash}`;
  let state = {version: 1, dataset_hash: data.dataset_hash, current: ids[0], annotator: "", language: "both", rows: {}};
  let tab = "public", filter = "all", selection = "", timer, toastTimer, pendingImport, storageOK = true;
  let errorStage = null;
  function node(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function warnStorage(message) {
    storageOK = false;
    $("storage-warning").textContent = message;
    $("storage-warning").hidden = false;
    $("save-status").textContent = "请导出备份";
  }
  function recover(raw) {
    if (!raw || raw.version !== 1 || raw.dataset_hash !== data.dataset_hash || !raw.rows || typeof raw.rows !== "object") throw new Error("备份版本或题包哈希不匹配");
    const cleaned = {};
    for (const [id, value] of Object.entries(raw.rows)) {
      if (!byId.has(id) || !value || typeof value !== "object") throw new Error("备份中存在无效任务");
      const r = C.blank(id);
      for (const f of C.FIELDS.slice(1)) {
        if (value[f] !== undefined && typeof value[f] !== "string") throw new Error(`${id}：字段类型无效`);
        r[f] = value[f] || "";
      }
      for (const [f, choices] of Object.entries(C.OPTIONS)) if (r[f] && !choices.includes(r[f])) throw new Error(`${id}：选项无效`);
      r._revealed = Boolean(value._revealed);
      r._completed = Boolean(value._completed) && r._revealed && C.validate(r, byId.get(id).model).length === 0;
      if (value._independent && typeof value._independent === "object") r._independent = value._independent;
      if (value._updated_at) r._updated_at = String(value._updated_at);
      cleaned[id] = r;
    }
    return {version: 1, dataset_hash: data.dataset_hash, current: byId.has(raw.current) ? raw.current : ids[0], annotator: String(raw.annotator || ""), language: ["both", "zh", "en"].includes(raw.language) ? raw.language : "both", rows: cleaned};
  }
  try {
    const saved = localStorage.getItem(storageKey);
    if (saved) state = recover(JSON.parse(saved));
    localStorage.setItem(`${storageKey}:test`, "1");
    localStorage.removeItem(`${storageKey}:test`);
  } catch (err) { warnStorage(`浏览器自动保存不可用或旧进度无法读取：${err.message}。请先下载 JSON 备份，当前页面仍可标注和导出。`); }
  function currentTask() { return byId.get(state.current); }
  function rowFor(id) { return state.rows[id] || C.blank(id); }
  function currentRow() { return rowFor(state.current); }
  function saveNow() {
    clearTimeout(timer);
    // 旧进度读取失败时不覆盖原始存储，避免把不可读但可恢复的数据写成空白。
    if (!storageOK) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(state));
      if (storageOK) $("save-status").textContent = "已自动保存到本机";
    } catch (err) { warnStorage(`浏览器保存失败：${err.message}。请下载 JSON 备份，避免关闭后丢失。`); }
  }
  function scheduleSave() {
    $("save-status").textContent = storageOK ? "正在保存…" : "请导出备份";
    clearTimeout(timer);
    timer = setTimeout(saveNow, 180);
  }
  function toast(text) {
    $("toast").textContent = text; $("toast").hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4200);
  }
  function putRow(row) { state.rows[row.review_id] = row; row._updated_at = new Date().toISOString(); }
  function mutate(field, value) {
    const r = {...currentRow(), [field]: value, _completed: false};
    if (field === "annotator") state.annotator = value;
    else if (!r.annotator) r.annotator = state.annotator;
    if (field === "human_verdict") {
      r.human_defect_type = value === "有缺陷" ? r.human_defect_type : "";
      r.type_consistency = "";
    }
    if (field === "human_defect_type") r.type_consistency = "";
    if (field === "human_test_integrity" && ["不完整或语法错误", "未提供"].includes(value)) r.human_test_quality = "无法判定";
    putRow(r); scheduleSave(); updateConditional(); renderQueue();
    if (errorStage) renderErrors(errorStage);
  }
  function addOptions(id, key) {
    const select = $(id); select.append(node("option", "", "请选择")); select.firstChild.value = "";
    for (const value of C.OPTIONS[key]) {
      if (key === "type_consistency") {
        const allowed = data.review_kind === "qualified_risk" ? ["确认原合格", "推翻原合格", "无法判定"] : ["一致", "类型不一致", "不适用_人工判合格", "无法判定"];
        if (!allowed.includes(value)) continue;
      }
      const opt = node("option", "", value); opt.value = value; select.append(opt);
    }
  }
  for (const key of Object.keys(C.OPTIONS)) if (key !== "human_verdict") addOptions(key, key);
  for (const value of C.OPTIONS.human_verdict) {
    const label = node("label", "verdict-label"); label.dataset.value = value;
    const input = node("input"); input.type = "radio"; input.name = "human_verdict"; input.value = value;
    label.append(input, node("span", "", value)); $("verdict-options").append(label);
  }
  for (const bank of [...new Set(tasks.map(t => t.material.bank))].sort()) {
    const opt = node("option", "", bank); opt.value = bank; $("bank-filter").append(opt);
  }
  function titleFor(t) {
    const m = t.material;
    return m.public?.function_name || m.public?.entry_point || m.task_id || t.review_id;
  }
  function filteredTasks() {
    const q = $("search").value.trim().toLowerCase(), bank = $("bank-filter").value;
    return tasks.filter(t => {
      const s = C.status(rowFor(t.review_id), t.model);
      if (filter === "completed" && s !== "completed") return false;
      if (filter === "pending" && s === "completed") return false;
      if (bank && t.material.bank !== bank) return false;
      return !q || t.search_text.includes(q);
    });
  }
  const STATUS = {empty: "未开始", draft: "草稿", comparison: "待核对", completed: "已完成"};
  function renderQueue() {
    const visible = filteredTasks(), list = $("task-list"); list.replaceChildren();
    if (!visible.length) list.append(node("p", "empty-message", "没有符合筛选条件的任务。"));
    for (const t of visible) {
      const s = C.status(rowFor(t.review_id), t.model);
      const btn = node("button", `task-item${t.review_id === state.current ? " active" : ""}`);
      btn.type = "button"; btn.dataset.reviewId = t.review_id;
      if (t.review_id === state.current) btn.setAttribute("aria-current", "true");
      const top = node("span", "task-item-top");
      top.append(node("span", "", t.review_id), node("span", `task-state-icon ${s}`, STATUS[s]));
      btn.append(top, node("span", "task-item-name", t.material.bank), node("span", "task-item-name", titleFor(t)));
      btn.addEventListener("click", () => goTo(t.review_id)); list.append(btn);
    }
    const done = tasks.filter(t => C.status(rowFor(t.review_id), t.model) === "completed").length;
    $("overall-count").textContent = `${done} / ${tasks.length}`;
    $("overall-progress").max = tasks.length; $("overall-progress").value = done;
    $("queue-count").textContent = visible.length;
    const currentIndex = visible.findIndex(t => t.review_id === state.current);
    $("prev-button").disabled = visible.length === 0 || currentIndex === 0;
    $("next-button").disabled = visible.length === 0 || currentIndex === visible.length - 1;
    const s = C.status(currentRow(), currentTask().model);
    $("row-state").textContent = STATUS[s]; $("row-state").className = `state-pill ${s}`;
  }
  function codeBlock(text) {
    const wrap = node("div", "code-block"), lines = node("ol", "code-lines");
    String(text || "").split("\n").forEach(line => lines.append(node("li", "", line || " ")));
    wrap.append(lines); return wrap;
  }
  function card(title, caption) {
    const c = node("section", "material-card"), h = node("div", "card-header");
    h.append(node("h3", "", title)); if (caption) h.append(node("span", "card-caption", caption));
    c.append(h); return c;
  }
  function textCard(title, text, caption, path) {
    const c = card(title, caption); c.append(node("div", "card-body translation-text", text));
    if (path) c.append(node("div", "source-caption", path)); return c;
  }
  function sourceCard(title, text, path) {
    const c = card(title, "原始材料 · 保留换行和缩进"); c.append(codeBlock(text));
    if (path) c.append(node("div", "source-caption", path)); return c;
  }
  function disclosure(title, text, path) {
    const d = node("details", "material-card"); d.append(node("summary", "", title), codeBlock(text));
    if (path) d.append(node("div", "source-caption", path)); return d;
  }
  const PUBLIC_LABELS = {description:"任务描述", function_name:"函数名", arguments:"参数", returns:"返回值", raises:"异常", security_policy:"安全要求", context:"公开上下文", problem:"题面 / Problem", entry_point:"入口函数", insecure_code:"公开起始代码 / Insecure Code"};
  function renderPublic(container, t) {
    container.append(node("div", "notice", "中文译文仅辅助阅读；不补充隐藏规则，不改变代码、标识符和测试。证据请引用原文，并核对原始上下文。"));
    const language = state.language, m = t.material;
    if (language !== "en") container.append(textCard("题面中文译文", t.translation, "辅助阅读 · 以原文为准"));
    if (m.public) {
      const prose = card("生成时公开的原始信息", "public"); const body = node("div", "card-body");
      for (const [key, value] of Object.entries(m.public)) {
        if (key === "insecure_code") continue;
        const section = node("section", "public-field"); section.append(node("h4", "", `${PUBLIC_LABELS[key] || key} · public.${key}`));
        if (key === "problem" && /\bdef\s|\bimport\s|#include/.test(value)) section.append(codeBlock(value));
        else section.append(node("pre", "original-prose", value || "（原字段为空）"));
        body.append(section);
      }
      prose.append(body);
      if (language === "zh") {
        const d = node("details", "material-card"); d.append(node("summary", "", "展开公开原文（含完整示例和签名）"), prose); container.append(d);
      } else container.append(prose);
      if (m.public.insecure_code) container.append(sourceCard("公开起始代码", m.public.insecure_code, "public.insecure_code · 仅对照，不执行"));
    } else {
      for (const s of m.sources || []) if (s.role === "public") {
        const isCode = /\bdef\s|#include|\bimport\s|\bint\s+\w+\(/.test(s.text);
        const c = isCode ? sourceCard("公开代码 / 上下文", s.text, s.path) : textCard("公开原文", s.text, "public", s.path);
        if (language === "zh" && !isCode) {
          const d = node("details", "material-card"); d.append(node("summary", "", "展开公开原文（含完整示例）"), c); container.append(d);
        } else container.append(c);
      }
    }
  }
  function renderTests(container, t) {
    container.append(node("div", "notice amber", "这些测试仅供审核，不能当作生成时已公开的要求。本页只展示原始材料，不执行代码；静态怀疑不得写成动态验证结论。"));
    const m = t.material;
    if (m.bank === "CodeSecEval-Plus") container.append(node("div", "notice", "Plus 审核快照保留 Test-FP / Test-SP。当前验证器对带 Plus 标记的记录可能从总 Test 拆分套件；数据字段损坏与当前实际评分问题需分别核实。"));
    let count = 0;
    for (const [name, text] of Object.entries(m.tests || {})) {
      const titles = {setup:"测试准备 / setup", testcases:"功能与安全用例 / testcases", test_functional:"功能测试 / Test-FP", test_security:"安全测试 / Test-SP"};
      if (text) { container.append(sourceCard(titles[name] || name, text, `tests.${name}`)); count++; }
    }
    for (const s of m.sources || []) if (s.role !== "public") {
      if (/^reference/.test(s.role)) continue;
      container.append(sourceCard(`审核材料 · ${s.role}`, s.text, s.path)); count++;
    }
    if (!count) container.append(textCard("未提供测试材料", "请按材料边界选择“未提供”或“无法判定”，不能据此编造隐藏契约。"));
  }
  function renderRules(container) {
    const intro = textCard("先独立判断，再核对标签", "合格：题面、签名、示例和常规工程约定足以确定要求。\n有缺陷：存在不可推断的必要要求，或题面与具体断言直接冲突。\n无法判定：材料不足或公开边界不清，需要在补充说明中写明缺什么。"); container.append(intro);
    container.append(textCard("有缺陷必须给出三项证据", "1. 具体断言或调用：引用原文，附路径、字段、用例序号或行号。\n2. 缺失或冲突的必要要求：冲突时分别引用题面与测试。\n3. 无法推断的理由：说明为何不能从签名、示例、上下文和常规约定推出。\n\n接口契约：参数名、默认值、返回形态或异常类型等缺失且不可推断。\n业务规则或数据：必要阈值、白名单、数据源或全局状态未给。\n题面与测试冲突：公开要求与断言直接矛盾。\n环境依赖：测试所需外部服务、数据或环境缺少公开契约；本机没装包不算。"));
    container.append(textCard("将测试问题单列", "测试损坏：仅记录完整性，测试质量为“无法判定”，不自动判题面有缺陷。\n安全组偏弱：一律拒绝能过安全组，但功能组会拦住。\nJoint 可被绕过：违反题意的实现能同时过功能与安全组；未运行时只记静态推测。\n输出格式过严：过度依赖逐字符格式。\n缺少正例：缺少合法输入验证。\n仅有静态安全检查时，不能推断同题双动态 oracle 的 Joint。"));
    const scope = data.review_kind === "qualified_risk" ? "本批来自原合格题中“历史低通过∩规格风险双判一致”的交集。先独立判断，后核对是否确认原合格标签；风险不等于缺陷。此定向样本不能估计全体合格题准确率。" : "150 条均为机器判为缺陷且两次类型一致的候选，不能据此估计全库缺陷率或机器召回率。";
    container.append(textCard("样本和数据隔离", scope + "\n建议两名标注者独立完成，保留各自文件，分歧由第三人裁决。\nBase/Plus 的最终测试反馈不得用于 SCT 经验生成、门控或长期记忆更新。\n参考实现出错、实现困难和测试偏弱不自动构成题面缺陷。"));
    container.append(textCard("文件与导出", `输入：${data.review_path || "data/audit_release_20261118/human_review_150/"}\n原始数据只读；CSV 保留 annotation_template.csv 的 13 列。\n自动保存仅属于当前浏览器和当前文件/站点；换浏览器或更换打开地址时，请用 JSON 备份恢复。\nJSON 保留查看标签前的独立判断快照。CSV 用于最终汇总，不含该历史。\n未执行编译、功能、安全或静态分析，相关动态验证均为未测量。`, "题包 SHA-256", data.dataset_hash));
  }
  function renderMaterial() {
    const content = $("material-content"); content.replaceChildren();
    document.querySelectorAll("[data-tab]").forEach(b => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    content.setAttribute("aria-labelledby", `tab-${tab}`);
    if (tab === "public") renderPublic(content, currentTask());
    else if (tab === "tests") renderTests(content, currentTask());
    else renderRules(content);
    $("language").disabled = tab !== "public";
    content.scrollTop = 0; selection = "";
  }
  function renderModel() {
    const r = currentRow(), m = currentTask().model, box = $("model-content"); box.replaceChildren();
    if (!r._revealed) return;
    const labels = node("div", "model-labels"); labels.append(node("span", "model-label", `机器：${m.verdict}`), node("span", "model-label", m.defect_type || "无缺陷类型")); box.append(labels);
    if (m.review_kind === "qualified_risk") box.append(textCard("原合格标签与新增风险意见", `原标签：合格（不覆盖）。新风险：${m.risk_level} / ${m.risk_type}。\n风险不自动等于缺陷。请核对是否确认原合格；若推翻，填写自己的缺陷类型与三项证据。`), textCard("事后历史表现", JSON.stringify(m.history, null, 2)));
    const reasons = m.judgments || [];
    reasons.forEach((judgment, i) => {
      if (!judgment) return;
      const d = node("details"), s = node("summary", "", `查看第 ${i + 1} 次机器判断原文`);
      d.append(s, node("div", "model-reason", JSON.stringify(judgment, null, 2))); box.append(d);
    });
    box.append(node("p", "field-help", m.evidence_status || "机器审计意见，不是人工金标"));
  }
  function updateConditional() {
    const r = currentRow(), defect = r.human_verdict === "有缺陷", revealed = Boolean(r._revealed);
    $("defect-section").hidden = !defect;
    $("human_defect_type").value = r.human_defect_type;
    $("human_test_quality").value = r.human_test_quality;
    $("type_consistency").value = r.type_consistency;
    $("evidence-badge").textContent = defect ? "三项均必填" : "可补充";
    $("notes-required").textContent = r.human_verdict === "无法判定" ? "必填：缺少什么" : "选填";
    $("reveal-button").hidden = revealed;
    $("model-content").hidden = !revealed; $("comparison-fields").hidden = !revealed;
    $("comparison-intro").textContent = revealed ? "已保留独立判断快照。后续修改属于看过机器标签后的复核修订。" : "先完成上方独立判断，再查看机器结论。";
    $("consistency-hint").textContent = revealed ? `按当前人工判断应选：${C.expectedConsistency(r, currentTask().model) || "请先填写结论和类型"}` : "";
    $("test-quality-hint").textContent = r.human_test_quality === "Joint 可被绕过" ? "未动态运行时，请在补充说明写明“未运行，仅静态推测”，并说明可能的绕过实现。" : "测试损坏不自动构成题面缺陷。";
  }
  function renderErrors(stage) {
    const errs = C.validate(currentRow(), currentTask().model, stage);
    $("validation-errors").textContent = errs.map(e => `• ${e}`).join("\n");
    $("validation-errors").hidden = !errs.length; return errs;
  }
  function renderTask() {
    const t = currentTask(), m = t.material, r = currentRow();
    $("task-title").textContent = titleFor(t); $("task-key").textContent = m.key || m.task_id || t.review_id;
    $("task-position").textContent = `${ids.indexOf(state.current) + 1} / ${tasks.length}`;
    $("task-badges").replaceChildren(node("span", "badge blue", t.review_id), node("span", "badge", m.bank));
    for (const text of [m.cwe, m.language, m.split]) if (text) $("task-badges").append(node("span", "badge", text));
    for (const f of C.FIELDS.slice(1)) {
      if (f === "human_verdict") continue;
      $(f).value = r[f] || (f === "annotator" ? state.annotator : "");
    }
    document.querySelectorAll('input[name="human_verdict"]').forEach(el => { el.checked = r.human_verdict === el.value; });
    $("language").value = state.language;
    $("validation-errors").hidden = true; errorStage = null;
    renderMaterial(); renderModel(); updateConditional(); renderQueue();
    $("annotation-form").scrollTop = 0;
    const visible = filteredTasks(), position = visible.findIndex(x => x.review_id === state.current);
    $("prev-button").disabled = position === 0 || visible.length === 0;
    $("next-button").disabled = position === visible.length - 1 || visible.length === 0;
  }
  function goTo(id) { saveNow(); state.current = id; renderTask(); saveNow(); }
  function navigate(direction) {
    const visible = filteredTasks(), index = visible.findIndex(t => t.review_id === state.current);
    const next = index === -1 ? visible[0] : visible[index + direction]; if (next) goTo(next.review_id);
  }
  function captureAnnotator() {
    const r = {...currentRow(), annotator: $("annotator").value}; putRow(r); state.annotator = r.annotator; return r;
  }
  $("annotation-form").addEventListener("submit", e => e.preventDefault());
  $("annotation-form").addEventListener("input", e => {
    if (C.FIELDS.includes(e.target.name) && e.target.tagName !== "SELECT" && e.target.type !== "radio") mutate(e.target.name, e.target.value);
  });
  $("annotation-form").addEventListener("change", e => {
    if (e.target.tagName === "SELECT" || e.target.type === "radio") mutate(e.target.name, e.target.value);
  });
  $("reveal-button").addEventListener("click", () => {
    const r = captureAnnotator(); errorStage = "blind";
    if (renderErrors("blind").length) { $("validation-errors").scrollIntoView({block:"nearest", behavior:"smooth"}); return; }
    r._independent = {captured_at: new Date().toISOString(), fields: Object.fromEntries(C.FIELDS.map(f => [f, r[f]]))};
    r._revealed = true; putRow(r); saveNow(); renderModel(); updateConditional(); renderQueue();
    toast("独立判断已保存，现在可以核对机器标签。");
  });
  function complete() {
    const r = captureAnnotator(); errorStage = "final";
    if (!r._revealed) { errorStage = "blind"; renderErrors("blind"); toast("请先提交独立判断并核对机器标签。"); return; }
    if (renderErrors("final").length) { $("validation-errors").scrollIntoView({block:"nearest", behavior:"smooth"}); return; }
    r._completed = true; putRow(r); saveNow();
    const candidates = filteredTasks();
    const position = ids.indexOf(state.current);
    const pending = candidates.filter(t => t.review_id !== state.current && C.status(rowFor(t.review_id), t.model) !== "completed");
    const next = pending.find(t => ids.indexOf(t.review_id) > position) || pending[0];
    if (next) goTo(next.review_id); else { renderQueue(); toast("当前筛选范围已完成，可以导出 CSV。"); }
  }
  $("complete-button").addEventListener("click", complete);
  $("prev-button").addEventListener("click", () => navigate(-1)); $("next-button").addEventListener("click", () => navigate(1));
  document.querySelectorAll("[data-tab]").forEach(b => b.addEventListener("click", () => { tab = b.dataset.tab; renderMaterial(); }));
  $("help-button").addEventListener("click", () => { tab = "rules"; renderMaterial(); $("reading-pane").scrollIntoView({block:"start", behavior:"smooth"}); });
  $("search").addEventListener("input", renderQueue); $("bank-filter").addEventListener("change", renderQueue);
  document.querySelectorAll("[data-filter]").forEach(b => b.addEventListener("click", () => {
    filter = b.dataset.filter; document.querySelectorAll("[data-filter]").forEach(x => x.classList.toggle("active", x === b)); renderQueue();
  }));
  $("language").addEventListener("change", () => { state.language = $("language").value; saveNow(); renderMaterial(); });
  document.addEventListener("selectionchange", () => {
    const s = window.getSelection(); if (!s || s.isCollapsed) return;
    const anchor = s.anchorNode?.nodeType === 1 ? s.anchorNode : s.anchorNode?.parentElement;
    if (anchor && $("material-content").contains(anchor)) selection = s.toString();
  });
  $("quote-selection").addEventListener("click", () => {
    if (!selection.trim()) { toast("请先在题面或测试中选中要引用的原文。"); return; }
    const prefix = `[${state.current} / ${tab === "tests" ? "审核测试" : "公开题面"}]\n`;
    const value = [currentRow().assertion_or_call, prefix + selection].filter(Boolean).join("\n\n");
    $("assertion_or_call").value = value; mutate("assertion_or_call", value); toast("选中文字已填入证据，请补充字段路径或行号。");
  });
  function download(content, name, type) {
    saveNow(); const url = URL.createObjectURL(new Blob([content], {type}));
    const a = node("a"); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function stamp() { return new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19); }
  function exportCSV(completedOnly) {
    const selected = tasks.filter(t => !completedOnly || C.status(rowFor(t.review_id), t.model) === "completed").map(t => rowFor(t.review_id));
    download(C.csv(selected), `human_review_${completedOnly ? "completed" : "all"}_${stamp()}.csv`, "text/csv;charset=utf-8");
    $("export-dialog").close(); toast(`已导出 ${selected.length} 行标注。`);
  }
  $("export-button").addEventListener("click", () => {
    const done = tasks.filter(t => C.status(rowFor(t.review_id), t.model) === "completed").length;
    $("export-summary").textContent = `${tasks.length} 条任务中已完成 ${done} 条。可以只导出已完成记录，或导出全部记录保留草稿。`;
    $("export-completed").disabled = done === 0; $("export-dialog").showModal();
  });
  $("export-completed").addEventListener("click", () => exportCSV(true)); $("export-all").addEventListener("click", () => exportCSV(false));
  $("backup-button").addEventListener("click", () => { download(JSON.stringify(state, null, 2), `human_review_backup_${stamp()}.json`, "application/json;charset=utf-8"); toast("已下载含独立判断快照的完整备份。"); });
  $("import-button").addEventListener("click", () => $("import-file").click());
  $("import-file").addEventListener("change", async e => {
    const file = e.target.files[0]; if (!file) return;
    try {
      if (file.size > 15 * 1024 * 1024) throw new Error("文件超过 15 MB，请确认选择的是标注 CSV 或 JSON 备份");
      const text = await file.text();
      let rows;
      if (file.name.toLowerCase().endsWith(".json")) rows = Object.values(recover(JSON.parse(text)).rows);
      else rows = C.importRows(C.parseCSV(text), ids).map(r => ({...r, _revealed: Boolean(r.type_consistency), _completed: Boolean(r.type_consistency) && C.validate(r, byId.get(r.review_id).model).length === 0}));
      rows = C.importRows(rows, ids);
      if (!rows.length) throw new Error("文件没有可导入的已填写记录");
      pendingImport = rows;
      const overwritten = rows.filter(r => C.FIELDS.slice(1).some(f => rowFor(r.review_id)[f])).length;
      $("import-summary").textContent = `将导入 ${rows.length} 条记录，其中 ${overwritten} 条将替换当前已填写记录。导入前会自动下载现有进度的 JSON 备份。`;
      $("import-dialog").showModal();
    } catch (err) { toast(`导入失败：${err.message}`); }
    e.target.value = "";
  });
  $("confirm-import").addEventListener("click", () => {
    if (!pendingImport) return;
    download(JSON.stringify(state, null, 2), `human_review_before_import_${stamp()}.json`, "application/json;charset=utf-8");
    for (const r of pendingImport) state.rows[r.review_id] = r;
    const count = pendingImport.length; pendingImport = null; saveNow(); renderTask(); $("import-dialog").close(); toast(`已恢复 ${count} 条记录。`);
  });
  $("cancel-import").addEventListener("click", () => { pendingImport = null; $("import-dialog").close(); });
  document.addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !document.querySelector("dialog[open]")) { e.preventDefault(); complete(); } });
  window.addEventListener("pagehide", saveNow);
  $("overall-progress").max = tasks.length;
  renderTask(); if (storageOK) $("save-status").textContent = "已自动保存到本机";
})();
