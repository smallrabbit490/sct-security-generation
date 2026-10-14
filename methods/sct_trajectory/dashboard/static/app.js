/* CLE 自进化任务看板 — 前端逻辑
 * 只读后端 API，负责：运行选择、状态徽章、5 个 Tab 渲染、导出、自动刷新。
 * 图表全部用内联 SVG/div 手绘，不引入任何第三方库。
 */
const $ = (id) => document.getElementById(id);
const state = { run: "", runs: [], timer: null, errors: [] };

/* ---------------- 基础工具 ---------------- */
async function api(path, params = {}) {
  const q = new URLSearchParams(params).toString();
  const res = await fetch(path + (q ? "?" + q : ""));
  const data = await res.json();
  // 后端捕获异常时会返回 {error, message}；必须显式暴露，否则页面只会显示空数据，
  // 让人误以为"该运行没有数据"（实测踩过一次：类型守卫缺失导致全页显示 0）。
  if (data && data.error) {
    state.errors.push(`${path} → ${data.error}: ${data.message || ""}`);
    throw new Error(`${path} 失败：${data.error} ${data.message || ""}`);
  }
  return data;
}
const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const pct = (v) => (v == null ? "—" : (v * 100).toFixed(1) + "%");
const nz = (v) => (v == null || v === "" ? "—" : v);
function card(k, v, s) { return `<div class="card"><div class="k">${esc(k)}</div>
  <div class="v">${esc(v)}</div>${s ? `<div class="s">${esc(s)}</div>` : ""}</div>`; }
function empty(msg) { return `<div class="empty">${esc(msg)}</div>`; }

/* ABCD 堆叠条 + 图例 */
function abcdBar(abcd) {
  const keys = ["A", "B", "C", "D"];
  const total = keys.reduce((a, k) => a + (abcd[k] || 0), 0);
  if (!total) return empty("暂无数据（该运行未采集 ABCD）");
  const segs = keys.map(k => {
    const v = abcd[k] || 0;
    return v ? `<span class="seg-${k}" style="width:${(v / total) * 100}%"
      title="${k}: ${v}"></span>` : "";
  }).join("");
  const legend = keys.map(k => `<span><i class="dot seg-${k}"></i>${k}: ${abcd[k] || 0}</span>`).join("");
  return `<div class="bar">${segs}</div><div class="legend">${legend}<span>共 ${total} 条</span></div>`;
}

/* 折线/柱状：树成长轨迹 */
function growthChart(points) {
  if (!points || !points.length) return empty("暂无树快照（该运行未采集）");
  const W = 640, H = 180, pad = 30;
  const maxY = Math.max(1, ...points.map(p => p.nodes));
  const stepX = points.length > 1 ? (W - pad * 2) / (points.length - 1) : 0;
  const y = (v) => H - pad - (v / maxY) * (H - pad * 2);
  const pts = points.map((p, i) => [pad + i * stepX, y(p.nodes)]);
  const line = pts.map((p, i) => (i ? "L" : "M") + p[0] + " " + p[1]).join(" ");
  const dots = points.map((p, i) => `<circle cx="${pad + i * stepX}" cy="${y(p.nodes)}" r="4"
      fill="var(--blue)"><title>${esc(p.label)}: ${p.nodes} 节点(active ${p.active})</title></circle>`).join("");
  const labels = points.map((p, i) => `<text x="${pad + i * stepX}" y="${H - 8}"
      fill="#8b98a5" font-size="11" text-anchor="middle">${esc(p.label)}</text>`).join("");
  const bars = points.map((p, i) => {
    const h = (p.active / maxY) * (H - pad * 2);
    return `<rect x="${pad + i * stepX - 6}" y="${y(p.active)}" width="12" height="${h}"
      fill="var(--accent)" opacity="0.45"><title>${esc(p.label)}: active ${p.active}</title></rect>`;
  }).join("");
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:${W}px">
    <line x1="${pad}" y1="${H - pad}" x2="${W - pad}" y2="${H - pad}" stroke="#2a3441"/>
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${H - pad}" stroke="#2a3441"/>
    <text x="4" y="${pad + 4}" fill="#8b98a5" font-size="11">${maxY}</text>
    <text x="4" y="${H - pad}" fill="#8b98a5" font-size="11">0</text>
    ${bars}${line ? `<path d="${line}" fill="none" stroke="var(--blue)" stroke-width="2"/>` : ""}${dots}${labels}
  </svg>
  <div class="legend"><span><i class="dot" style="background:var(--blue)"></i>总节点数（折线）</span>
  <span><i class="dot" style="background:var(--accent)"></i>active 节点（柱）</span></div>`;
}

/* 树结构视图 */
function treeView(tree) {
  if (!tree || !Object.keys(tree).length) return empty("暂无树数据");
  return Object.entries(tree).map(([cwe, fam]) => {
    const invs = fam.invariants || [];
    if (!invs.length) return "";
    const rows = invs.map(n => `<div class="inv">
      <span class="tag ${esc(n.status)}">${esc(n.status)}</span>
      <b>CWE-${esc(cwe)}</b>
      ${n.utility != null ? `<span class="mini">utility=${n.utility}</span>` : ""}
      ${n.source && n.source.stage ? `<span class="mini">[${esc(n.source.stage)}/${esc(n.source.kind || "")}]</span>` : ""}
      <div>${esc(n.high_level_invariant || "")}</div>
      ${n.positive_principle ? `<div class="mini">正向：${esc(n.positive_principle)}</div>` : ""}
      ${n.negative_guardrail ? `<div class="mini">红线：${esc(n.negative_guardrail)}</div>` : ""}
    </div>`).join("");
    return `<details class="cwe" open><summary>CWE-${esc(cwe)} （${invs.length} 节点）</summary>${rows}</details>`;
  }).join("") || empty("树为空");
}

/* 代码 diff 染色 */
function diffHtml(text) {
  if (!text) return "";
  return esc(text).split("\n").map(l =>
    l.startsWith("+") ? `<span class="diff-add">${l}</span>` :
    l.startsWith("-") ? `<span class="diff-del">${l}</span>` : l).join("\n");
}

/* ---------------- 运行列表与状态 ---------------- */
async function loadRuns() {
  const data = await api("/api/runs");
  state.runs = data.runs || [];
  const sel = $("runSelect");
  sel.innerHTML = state.runs.map(r =>
    `<option value="${esc(r.run_name)}">${esc(r.run_name)}  [${esc(statusText(r.status))}]</option>`
  ).join("") || `<option value="">（暂无运行）</option>`;
  if (!state.run && state.runs.length) state.run = state.runs[0].run_name;
  sel.value = state.run;
  sel.onchange = () => { state.run = sel.value; refreshAll(); };
}

function statusText(s) {
  return { running: "进行中", completed: "已完成", failed: "失败",
           stale: "已中断", unknown: "未知" }[s] || s || "未知";
}
function badgeClass(s) {
  return { running: "running", completed: "completed", failed: "failed",
           stale: "stale" }[s] || "unknown";
}

/* ---------------- 各 Tab 渲染 ---------------- */
async function renderOverview() {
  const d = await api("/api/overview", { run: state.run });
  const st = d.status || {};
  const badge = $("statusBadge");
  badge.className = "badge " + badgeClass(st.status);
  badge.textContent = statusText(st.status) + (st.stage ? " · " + st.stage : "");

  const c = d.pools_counts || {};
  const tc = d.has_pools
    ? { v: d.total_tasks, s: "source+replay+audit" }
    : { v: d.total_tasks == null ? "—" : d.total_tasks,
        s: d.total_tasks_inferred ? "推断值（历史运行无 pools.json）" : "未采集" };
  $("overviewCards").innerHTML =
    card("总任务数", nz(tc.v), tc.s) +
    card("D_init 冷启动池", d.has_pools ? nz(c.source) : "—", "source") +
    card("D_grow 重放池", d.has_pools ? nz(c.replay) : "—", "replay") +
    card("D_gate 审计池", d.has_pools ? nz(c.audit) : "—", "audit") +
    card("Phase1 已完成", nz(d.phase1_done), "条") +
    card("演进轮数", nz(d.rounds), "轮") +
    card("最终评测", d.final_eval && d.final_eval.rate != null ? pct(d.final_eval.rate) : "未进行",
         d.final_eval && d.final_eval.size ? `${d.final_eval.joint_pass}/${d.final_eval.size}` : "");

  // 阶段进度
  const stages = [
    ["Phase 1 冷启动", d.phase1_done > 0],
    ["Phase 2 重放进化", d.rounds > 0],
    ["Phase 3 门控", (d.rounds > 0)],
    ["最终评测（审计池全量）", d.final_eval && d.final_eval.size > 0],
  ];
  $("stageProgress").innerHTML = stages.map(([name, done]) =>
    `<div style="margin:6px 0"><span class="pill ${done ? "supported" : "unmeasured"}">
      ${done ? "已进行" : "未进行"}</span> ${esc(name)}</div>`).join("")
    + (st.detail ? `<div class="mini" style="margin-top:8px">当前：${esc(st.detail)}
       ${st.updated_at ? "（" + esc(st.updated_at) + "）" : ""}</div>` : "");

  // 成本统计（真实 API usage 累计，非估算）
  const meta = d.metadata || {};
  const cost = d.cost;
  let costHtml;
  if (cost && cost.total) {
    const t = cost.total;
    const stages = cost.stages || {};
    const labels = cost.by_label || {};
    const money = (v) => (v == null ? "—" : v.toFixed(4) + " " + (cost.currency || ""));
    costHtml = `
      <div class="cards" style="margin-bottom:10px">
        ${card("LLM 调用", nz(t.calls), "次")}
        ${card("输入 tokens", nz(t.prompt_tokens), "")}
        ${card("输出 tokens", nz(t.completion_tokens), "")}
        ${card("合计 tokens", nz(t.total_tokens), "")}
        ${card("费用", money(t.cost_ca), cost.model || "")}
        ${card("usage 缺失", nz(t.usage_missing), t.usage_missing ? "⚠️ 未计费" : "全部采集到")}
      </div>
      <h4>按阶段</h4>
      <table><tr><th>阶段</th><th>调用</th><th>输入 tok</th><th>输出 tok</th><th>合计 tok</th><th>费用</th></tr>
      ${Object.entries(stages).map(([s, v]) => `<tr><td>${esc(s)}</td><td>${v.calls}</td>
        <td>${v.prompt_tokens}</td><td>${v.completion_tokens}</td><td>${v.total_tokens}</td>
        <td>${money(v.cost_ca)}</td></tr>`).join("")}
      </table>
      <h4 style="margin-top:12px">按调用点</h4>
      <table><tr><th>阶段.调用点</th><th>调用</th><th>输入 tok</th><th>输出 tok</th><th>费用</th></tr>
      ${Object.entries(labels).map(([k, v]) => `<tr><td class="mini">${esc(k)}</td><td>${v.calls}</td>
        <td>${v.prompt_tokens}</td><td>${v.completion_tokens}</td><td>${money(v.cost_ca)}</td></tr>`).join("")}
      </table>
      <div class="mini" style="margin-top:8px">单价：${esc(JSON.stringify(cost.pricing || {}))}
        （${esc(cost.currency || "")} / 1K tokens）　来源：${esc(cost.pricing_source || "")}</div>
      ${t.errors ? `<div class="mini">失败调用 ${t.errors} 次（无 usage，未计费）</div>` : ""}`;
  } else {
    costHtml = `<div class="warnbox">该运行未采集成本数据（历史运行，无 cost.json）。
      新运行会精确记录每次 LLM 调用的真实 usage。</div>`;
  }
  $("costPanel").innerHTML = costHtml +
    `<details style="margin-top:10px"><summary class="mini">运行元数据</summary>
     <table><tr><th>项</th><th>值</th></tr>
     <tr><td>模型</td><td>${esc(meta.model || "—")}</td></tr>
     <tr><td>数据集</td><td>${esc(meta.dataset || "—")}</td></tr>
     <tr><td>commit</td><td>${esc(meta.git_commit || "—")}</td></tr>
     <tr><td>参数</td><td class="mini">${esc(JSON.stringify(meta.args || {}))}</td></tr>
     </table></details>`;

  $("missingPanel").innerHTML = (d.missing && d.missing.length)
    ? `<div class="warnbox">该运行未采集以下看板数据（历史运行兼容显示）：${esc(d.missing.join("、"))}</div>`
    : `<div class="mini">数据完整：pools / status / 树快照 / 冻结清单 / 最终评测 均已采集。</div>`;
}

async function renderPhase1() {
  const d = await api("/api/phase1", { run: state.run });
  $("p1Cards").innerHTML =
    card("任务数", nz(d.total), "source 池") +
    card("第一次测试 A 率", pct(d.first_pass && d.first_pass.rate),
         d.first_pass ? `${d.first_pass.A}/${d.first_pass.total}` : "") +
    card("迭代后 A 率", pct(d.after_pass && d.after_pass.rate),
         d.after_pass ? `${d.after_pass.A}/${d.after_pass.total}` : "") +
    card("失败案例", nz((d.failures || []).length), "可展开看代码");

  const f = d.first_pass || {}, a = d.after_pass || {};
  $("p1Rates").innerHTML = `
    <table><tr><th>测试阶段</th><th>达 A 数</th><th>总数</th><th>成功率</th></tr>
    <tr><td>第一次动态测试（c⁰ 从零生成）</td><td>${nz(f.A)}</td><td>${nz(f.total)}</td>
        <td><b>${pct(f.rate)}</b></td></tr>
    <tr><td>迭代后测试（c¹ 修复轮）</td><td>${nz(a.A)}</td><td>${nz(a.total)}</td>
        <td><b>${pct(a.rate)}</b></td></tr></table>
    <div class="mini">提升：${f.rate != null && a.rate != null
      ? ((a.rate - f.rate) * 100).toFixed(1) + " 个百分点" : "—"}
      ${d.rate_source && d.rate_source.includes("回退")
        ? `　<span class="pill unmeasured">数据来源：${esc(d.rate_source)}</span>` : ""}</div>`;

  $("p1AbcdFirst").innerHTML = abcdBar(d.abcd_first || {});
  $("p1AbcdAfter").innerHTML = abcdBar(d.abcd_after || {});
  // 架构归一化后 Phase1 不直接入树：优先展示"Phase1 形成的经验池"，树为空是预期行为
  const pool = d.phase1_pool || [];
  const treeHasNodes = d.tree_snapshot && Object.keys(d.tree_snapshot).length;
  const p1Tree = $("p1Tree");
  if (pool.length) {
    const byCwe = pool.reduce((acc, n) => {
      const c = n.cwe || "?"; (acc[c] = acc[c] || []).push(n); return acc;
    }, {});
    const synth = Object.fromEntries(Object.entries(byCwe).map(([c, arr]) => [c, { invariants: arr }]));
    p1Tree.insertAdjacentHTML("beforebegin",
      `<div class="mini">架构归一化：Phase 1 产出的经验统一插入经验池（${pool.length} 条），
       不直接入树——是否入树由 Phase 3 门控决定。下图按 CWE 分组展示这些经验。</div>`);
    mountTree(p1Tree, synth);
  } else if (treeHasNodes) {
    mountTree(p1Tree, d.tree_snapshot);
  } else {
    p1Tree.innerHTML = empty("暂无数据（该运行未采集 Phase1 经验池快照）");
  }

  const fails = d.failures || [];
  $("p1FailCount").textContent = fails.length;
  $("p1Failures").innerHTML = fails.length ? fails.map((r, i) => renderFailCompare(r, i)).join("")
    : empty("无失败案例 🎉");
}

/* 并排 diff：失败最终代码 vs 成功代码（差异行高亮） */
function sideBySideDiff(codeA, codeB) {
  if (!codeA && !codeB) return "";
  const A = (codeA || "").split("\n"), B = (codeB || "").split("\n");
  // 简易 LCS：标记两边的差异行（够用于人工核对，不做完整 Myers 算法）
  const setB = new Set(B.map(s => s.trim()));
  const setA = new Set(A.map(s => s.trim()));
  const rows = [];
  const max = Math.max(A.length, B.length);
  for (let i = 0; i < max; i++) {
    const a = A[i], b = B[i];
    const aDiff = a != null && !setB.has(a.trim());
    const bDiff = b != null && !setA.has(b.trim());
    rows.push(`<tr>
      <td class="mini" style="width:50%;${aDiff ? "background:#2d1214" : ""}">
        <span class="diff-del">${a == null ? "" : esc(a)}</span></td>
      <td class="mini" style="width:50%;${bDiff ? "background:#0d2a17" : ""}">
        <span class="diff-add">${b == null ? "" : esc(b)}</span></td></tr>`);
  }
  return `<table style="table-layout:fixed"><tr><th>失败实现</th><th>成功实现</th></tr>
    ${rows.join("")}</table>`;
}

/* Analysis / Planning 三键归因对比 */
function agentCompare(failCtx, okCtx) {
  const fa = (failCtx && failCtx.analysis) || {}, fp = (failCtx && failCtx.plan) || {};
  const oa = (okCtx && okCtx.analysis) || {}, op = (okCtx && okCtx.plan) || {};
  const arr = (v) => Array.isArray(v) ? v.join("；") : (v || "—");
  const row = (k, a, b) => `<tr><td class="mini">${esc(k)}</td>
    <td class="mini">${esc(a)}</td><td class="mini">${esc(b)}</td></tr>`;
  return `<table>
    <tr><th>四步 Agent 的中间判断</th><th>失败案例</th><th>成功案例</th></tr>
    ${row("Analysis 漏洞假设", arr(fa.vulnerability_hypothesis), arr(oa.vulnerability_hypothesis))}
    ${row("Analysis 不可信输入", arr(fa.untrusted_inputs), arr(oa.untrusted_inputs))}
    ${row("Analysis 功能不变量", arr(fa.functional_invariants), arr(oa.functional_invariants))}
    ${row("Planning 保留功能", fp.Preserved_Func, op.Preserved_Func)}
    ${row("Planning 补丁范围", fp.Patch_Scope, op.Patch_Scope)}
    ${row("Planning 避免清单", arr(fp.Avoidance_List), arr(op.Avoidance_List))}
    </table>`;
}

function renderFailCompare(r, idx) {
  const ev = r.evidence_first, ev2 = r.evidence_after_repair;
  const cmp = r.compare;
  const scope = r.compare_scope;
  const scopeTag = scope === "same_cwe" ? `<span class="pill supported">同 CWE 对照</span>`
    : scope === "cross_cwe" ? `<span class="pill revised">CWE 不同，仅供参考</span>`
    : `<span class="pill unmeasured">无对照案例</span>`;
  const failCode = (r.generated_codes || []).filter(Boolean).slice(-1)[0] || "";
  const okCode = cmp ? ((cmp.generated_codes || []).filter(Boolean).slice(-1)[0] || "") : "";
  return `
  <details class="fail"><summary>
    <b>task ${esc(r.task_id)}</b> · CWE-${esc(r.cwe)} ·
    <span class="pill unmeasured">${esc(r.state_first || "?")} → ${esc(r.state_after_repair || "?")}</span>
    ${scopeTag}
  </summary>
    <div class="kv">失败侧验证：compile=<b>${esc((ev || {}).syntax_or_compile)}</b>
      func=<b>${esc((ev || {}).functional)}</b> sec=<b>${esc((ev || {}).security)}</b>
      ${ev2 ? `→ 迭代后 func=<b>${esc(ev2.functional)}</b> sec=<b>${esc(ev2.security)}</b>` : ""}</div>
    ${cmp ? `<div class="kv">成功侧（task ${esc(cmp.task_id)} · CWE-${esc(cmp.cwe)}）：
      state=<b>${esc(cmp.state_first)}</b>${cmp.state_after_repair ? `→<b>${esc(cmp.state_after_repair)}</b>` : ""}
      compile=<b>${esc((cmp.evidence_first || {}).syntax_or_compile)}</b>
      func=<b>${esc((cmp.evidence_first || {}).functional)}</b>
      sec=<b>${esc((cmp.evidence_first || {}).security)}</b></div>` : ""}

    <div class="compare">
      <div class="side fail">
        <h4>失败实现（最终轮代码）</h4>
        <pre>${esc(failCode) || "（该运行未采集代码）"}</pre>
        ${(r.patch_diffs || []).filter(Boolean).map((p, k) =>
          `<div class="mini">修复 diff #${k + 1}</div><pre>${diffHtml(p)}</pre>`).join("")}
      </div>
      <div class="side ok">
        <h4>对照成功实现${cmp ? `（task ${esc(cmp.task_id)} · CWE-${esc(cmp.cwe)}）` : ""}</h4>
        <pre>${esc(okCode) || "（无对照或无代码）"}</pre>
      </div>
    </div>

    ${cmp ? `<h4 style="margin-top:12px">并排 diff（失败 vs 成功）</h4>
      <div class="scroll" style="max-height:320px">${sideBySideDiff(failCode, okCode)}</div>` : ""}

    ${cmp ? `<h4 style="margin-top:12px">四步 Agent 归因对比</h4>
      ${agentCompare((r.agent_context || [])[0] || {}, (cmp.agent_context || [])[0] || {})}` : ""}
  </details>`;
}

/* 多折线图：series = [{name, color, points:[{x,label,y}]}]，y 为 0~1 比率 */
function multiLineChart(series, { yLabel = "通过率", height = 200 } = {}) {
  const all = series.flatMap(s => s.points.map(p => p.y)).filter(v => v != null);
  if (!all.length) return empty("暂无数据");
  const labels = series[0].points.map(p => p.label);
  const W = 700, H = height, padL = 48, padR = 16, padT = 16, padB = 34;
  const maxY = 1, minY = 0;
  const n = labels.length;
  const stepX = n > 1 ? (W - padL - padR) / (n - 1) : 0;
  const yOf = (v) => padT + (maxY - v) / (maxY - minY) * (H - padT - padB);
  const xOf = (i) => padL + i * stepX;
  const grid = [0, 0.25, 0.5, 0.75, 1].map(v => `
    <line x1="${padL}" y1="${yOf(v)}" x2="${W - padR}" y2="${yOf(v)}" stroke="#222b36"/>
    <text x="${padL - 8}" y="${yOf(v) + 4}" fill="#8b98a5" font-size="10"
      text-anchor="end">${(v * 100).toFixed(0)}%</text>`).join("");
  const xlabels = labels.map((l, i) =>
    `<text x="${xOf(i)}" y="${H - 12}" fill="#8b98a5" font-size="10"
      text-anchor="middle">${esc(l)}</text>`).join("");
  const lines = series.map(s => {
    const pts = s.points.map((p, i) => p.y == null ? null : [xOf(i), yOf(p.y)]).filter(Boolean);
    const d = pts.map((p, i) => (i ? "L" : "M") + p[0] + " " + p[1]).join(" ");
    const dots = s.points.map((p, i) => p.y == null ? "" :
      `<circle cx="${xOf(i)}" cy="${yOf(p.y)}" r="3.5" fill="${s.color}">
        <title>${esc(p.label)} ${esc(s.name)}: ${(p.y * 100).toFixed(1)}%
        ${p.pass != null ? `(${p.pass}/${p.total})` : ""}</title></circle>`).join("");
    return { d, dots, color: s.color, name: s.name };
  });
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:${W}px">
    ${grid}${xlabels}
    ${lines.map(l => l.d ? `<path d="${l.d}" fill="none" stroke="${l.color}" stroke-width="2"/>` : "").join("")}
    ${lines.map(l => l.dots).join("")}
  </svg>
  <div class="legend">${series.map(s =>
    `<span><i class="dot" style="background:${s.color}"></i>${esc(s.name)}</span>`).join("")}
    <span class="mini">纵轴：${esc(yLabel)}</span></div>`;
}

/* 通过率单元格：显示百分比 + 绝对数（避免小样本误导） */
function rateCell(r) {
  if (!r || r.total == null) return `<span class="muted">—</span>`;
  const cls = r.rate >= 0.99 ? "diff-add" : r.rate <= 0.01 ? "diff-del" : "";
  return `<b class="${cls}">${(r.rate * 100).toFixed(0)}%</b>
    <span class="mini">${r.pass}/${r.total}</span>`;
}

async function renderPhase2() {
  const d = await api("/api/phase2", { run: state.run });
  const rounds = d.rounds || [];
  const detail = d.rounds_detail || [];
  const totalPromoted = rounds.reduce((a, r) => a + (r.promoted || 0), 0);
  $("p2Cards").innerHTML =
    card("重放池任务数", nz((d.replay_pool || []).length), "D_grow") +
    card("演进轮数", nz(rounds.length), "轮") +
    card("Phase2 轨迹数", nz((d.trajectories || []).length), "条") +
    card("晋升总数", nz(totalPromoted), "经验入树");

  // ---- 各轮通过率（功能 / 安全 / 联合）----
  const init = d.initial_baseline;
  const hasRates = detail.some(x => x.pass_rates);
  if (hasRates) {
    const rows = [];
    if (init) {
      rows.push({ label: "初始（Phase1）", f: init.c0.functional, s: init.c0.security,
                  j: null, samples: init.c0.samples, tree: "—", promoted: "—", round: 0 });
    }
    detail.forEach(x => {
      const pr = x.pass_rates || {};
      rows.push({ label: `第 ${x.round} 轮`, f: (pr.functional || {}), s: (pr.security || {}),
                  j: (pr.joint || {}), samples: pr.samples,
                  tree: x.tree_after ? `${x.tree_after.active} active / ${x.tree_after.total}` : "—",
                  promoted: x.promoted, round: x.round });
    });
    $("p2Rates").innerHTML = `
      <table>
        <tr><th>迭代</th><th>功能通过率</th><th>安全通过率</th><th>联合通过率</th>
            <th>样本数</th><th>树（active/总）</th><th>晋升</th></tr>
        ${rows.map(r => `<tr>
          <td>${esc(r.label)}</td>
          <td>${rateCell(r.f)}</td>
          <td>${rateCell(r.s)}</td>
          <td>${r.j ? rateCell(r.j) : '<span class="muted">—</span>'}</td>
          <td>${nz(r.samples)}</td>
          <td class="mini">${esc(r.tree)}</td>
          <td>${esc(r.promoted)}</td></tr>`).join("")}
      </table>
      <div class="mini" style="margin-top:6px">
        分母为**该轮实际产生的轨迹数**：已达 A 的任务不再跑后续轮，故样本数逐轮递减。
        「初始（Phase1）」为冷启动首轮 c⁰ 的基线。</div>`
      + `<h4 style="margin-top:12px">通过率随轮次变化</h4>`
      + multiLineChart([
          { name: "功能通过率", color: "#58a6ff",
            points: rows.map(r => ({ label: r.label.replace("（Phase1）", ""), y: r.f ? r.f.rate : null,
                                     pass: r.f && r.f.pass, total: r.f && r.f.total })) },
          { name: "安全通过率", color: "#3fb950",
            points: rows.map(r => ({ label: r.label.replace("（Phase1）", ""), y: r.s ? r.s.rate : null,
                                     pass: r.s && r.s.pass, total: r.s && r.s.total })) },
          { name: "联合通过率", color: "#d29922",
            points: rows.map(r => ({ label: r.label.replace("（Phase1）", ""), y: r.j ? r.j.rate : null,
                                     pass: r.j && r.j.pass, total: r.j && r.j.total })) },
        ]);

    // 任务内修复轮 c0 → c1
    const repairRows = detail.filter(x => x.repair_rounds).map(x => {
      const rr = x.repair_rounds;
      return `<tr><td>第 ${x.round} 轮</td>
        <td>${rateCell(rr.c0.functional)} → ${rateCell(rr.c1.functional)}</td>
        <td>${rateCell(rr.c0.security)} → ${rateCell(rr.c1.security)}</td></tr>`;
    }).join("");
    if (repairRows) {
      $("p2Rates").innerHTML += `<h4 style="margin-top:14px">任务内修复轮效果（c⁰ 首次生成 → c¹ 修复后）</h4>
        <table><tr><th>轮次</th><th>功能通过率 变化</th><th>安全通过率 变化</th></tr>${repairRows}</table>`;
    }
  } else {
    $("p2Rates").innerHTML = `<div class="warnbox">该运行未采集逐轮通过率
      （历史运行无 pass_rates 字段）。新运行会记录每轮的功能/安全/联合通过率。</div>`;
  }

  // ---- 任务池 ----
  $("p2Pool").innerHTML = (d.replay_pool || []).length ? `
    <div class="scroll"><table><tr><th>task_id</th><th>CWE</th><th>描述</th></tr>
    ${d.replay_pool.map(r => `<tr><td>${esc(r.task_id)}</td><td>CWE-${esc(r.cwe)}</td>
      <td class="mini">${esc((r.description || "").slice(0, 90))}</td></tr>`).join("")}
    </table></div>` : empty("该运行未采集任务池（历史运行）");

  // ---- 逐轮折叠卡片（多轮友好：默认只展开第一轮）----
  $("p2Rounds").innerHTML = detail.length ? `
    <div class="mini" style="margin-bottom:8px">
      <button onclick="document.querySelectorAll('#p2Rounds details').forEach(d=>d.open=true)">展开全部轮次</button>
      <button onclick="document.querySelectorAll('#p2Rounds details').forEach((d,i)=>d.open=(i===0))">仅看第一轮</button>
    </div>`
    + detail.map((r, idx) => {
      const sch = r.schedule || {};
      const dec = (sch.raw_decisions || []).filter(x => x.Selected);
      const pr = r.pass_rates || {};
      const rh = r.retrieval_hit || {};
      const tasks = r.tasks || [];
      return `<details class="cwe" ${idx === 0 ? "open" : ""}>
        <summary><b>第 ${esc(r.round)} 轮</b>
          · 池 ${esc(r.replay_candidates)} · 选中 ${esc(r.selected)}
          ${(r.forced_replay || []).length ? `· <span class="pill revised">强制重放 ${esc((r.forced_replay || []).length)}</span>` : ""}
          · ABCD ${esc(JSON.stringify(pr.abcd || {}))}
          · 晋升 ${esc(r.promoted)} · 树 ${esc(r.tree_nodes)} 节点</summary>
        <div class="kv">功能 ${rateCell(pr.functional)}　安全 ${rateCell(pr.security)}　联合 ${rateCell(pr.joint)}
          　样本 ${nz(pr.samples)}</div>
        <div class="kv">检索命中 ${rh.hit ?? "—"}/${rh.total ?? "—"}
          ${rh.rate != null ? `（${(rh.rate * 100).toFixed(0)}%）` : ""}
          ${r.zero_hit_compensations ? `　<span class="pill revised">零命中补偿 ${esc(r.zero_hit_compensations)} 条</span>` : ""}
          ${(r.forced_replay || []).length ? `　<span class="pill revised">强制重放 task=${esc(JSON.stringify(r.forced_replay))}</span>` : ""}</div>
        <div class="mini">LLM 返回 ${(sch.raw_decisions || []).length} 条决策，选中 id：
          ${esc(JSON.stringify(sch.selected_ids || []))}
          ${sch.forced_ids && sch.forced_ids.length ? `（其中强制重放 ${esc(JSON.stringify(sch.forced_ids))}）` : ""}
          ${sch.fallback_used ? "（触发规则兜底）" : ""} ${sch.error ? "错误：" + esc(sch.error) : ""}</div>
        ${dec.length ? `<table><tr><th>task_id</th><th>LLM 选中理由</th></tr>
          ${dec.map(x => `<tr><td>${esc(x.Task_ID)}</td><td class="mini">${esc(x.Reason || "")}</td></tr>`).join("")}
          </table>` : `<div class="empty">本轮 LLM 未选中任何任务</div>`}
        ${tasks.length ? `<h4 style="margin-top:10px">本轮任务四态</h4>
          <table><tr><th>task</th><th>CWE</th><th>状态序列</th><th>功能</th><th>安全</th></tr>
          ${tasks.map(t => `<tr><td>${esc(t.task_id)}</td><td>CWE-${esc(t.cwe)}</td>
            <td>${esc((t.states || []).join(" → "))}</td>
            <td>${t.functional ? "✅" : "❌"}</td><td>${t.security ? "✅" : "❌"}</td></tr>`).join("")}
          </table>` : ""}
      </details>`;
    }).join("") : empty("该运行未采集轮次记录");

  // ---- 全局 ABCD + 逐任务 ----
  $("p2Abcd").innerHTML = abcdBar(d.abcd || {});
  $("p2Traj").innerHTML = (d.trajectories || []).length ? `
    <table><tr><th>轮</th><th>task</th><th>CWE</th><th>状态序列</th><th>检索命中</th></tr>
    ${d.trajectories.map(t => `<tr><td>${esc(t.round ?? "?")}</td><td>${esc(t.task_id)}</td>
      <td>CWE-${esc(t.cwe)}</td>
      <td>${esc((t.states || []).join(" → "))}</td>
      <td class="mini">${esc((t.retrieved_ids || []).join(", ") || "（无）")}</td></tr>`).join("")}
    </table>` : empty("无轨迹");

  // ---- 树成长轨迹（逐轮相邻对比：这一轮比上一轮多了哪些规则）----
  const g = await api("/api/tree_growth", { run: state.run });
  renderTreeGrowth(g);
}

function renderTreeGrowth(g) {
  const timeline = g.timeline || [];
  const diffs = g.diffs || [];
  const box = $("p2Growth");
  if (!timeline.length) {
    box.innerHTML = empty("该运行未采集树快照（历史运行）");
    return;
  }
  const chart = growthChart(timeline.map(t => ({
    label: t.label, nodes: t.rule_count || 0, active: t.rule_count || 0 })));
  const diffCards = diffs.map((d, i) => {
    const c = d.counts || {};
    const rows = (list, cls, sign) => list.length ? list.map(r => `
      <tr><td class="mini">${esc(r.invariant_id)}</td><td>CWE-${esc(r.cwe || "")}</td>
      <td><span class="pill ${esc(r.status || "unmeasured")}">${esc(r.status || "")}</span></td>
      <td class="mini">${esc((r.summary || "").slice(0, 60))}</td>
      <td class="mini">${sign}${esc(r.filled_leaves ?? "")}叶</td></tr>`).join("")
      : `<tr><td colspan="5" class="mini">（无）</td></tr>`;
    const changed = (d.changed || []).map(x => `
      <tr><td class="mini">${esc(x.invariant_id)}</td>
      <td><span class="pill ${esc(x.before?.status || "")}">${esc(x.before?.status || "")}</span> →
          <span class="pill ${esc(x.after?.status || "")}">${esc(x.after?.status || "")}</span></td>
      <td class="mini">叶 ${esc(x.before?.filled_leaves ?? 0)} → ${esc(x.after?.filled_leaves ?? 0)}</td>
      <td class="mini">${esc((x.after?.summary || "").slice(0, 60))}</td></tr>`).join("");
    return `<details class="cwe" ${i === diffs.length - 1 ? "open" : ""}>
      <summary><b>${esc(d.from)} → ${esc(d.to)}</b>
        ：规则 ${c.before} → ${c.after}
        <span class="pill supported">+${c.added} 新增</span>
        <span class="pill demoted">-${c.removed} 移除</span>
        <span class="pill revised">~${c.changed} 变更</span></summary>
      <h4 style="margin-top:8px">新增规则（这一轮多了哪些）</h4>
      <table><tr><th>规则 ID</th><th>CWE</th><th>状态</th><th>摘要</th><th>L4叶</th></tr>
        ${rows(d.added || [], "supported", "+")}</table>
      ${(d.removed || []).length ? `<h4 style="margin-top:8px">移除规则</h4>
        <table><tr><th>规则 ID</th><th>CWE</th><th>状态</th><th>摘要</th><th>L4叶</th></tr>
        ${rows(d.removed || [], "demoted", "-")}</table>` : ""}
      ${(d.changed || []).length ? `<h4 style="margin-top:8px">状态/内容变更</h4>
        <table><tr><th>规则 ID</th><th>状态变化</th><th>L4 叶变化</th><th>摘要</th></tr>
        ${changed}</table>` : ""}
    </details>`;
  }).join("");
  box.innerHTML = `<div class="mini">折线=累计规则数；下方为<b>逐轮相邻对比</b>（回答"这一轮比上一轮多了哪些规则"）</div>`
    + chart + diffCards
    + `<h4 style="margin-top:12px">任选两轮对比</h4>
       <div class="row" style="align-items:center;gap:8px;margin-bottom:8px">
         <select id="cmpFrom">${timeline.map(t => `<option>${esc(t.label)}</option>`).join("")}</select>
         <span class="mini">vs</span>
         <select id="cmpTo">${timeline.map((t, i) => `<option ${i === timeline.length - 1 ? "selected" : ""}>${esc(t.label)}</option>`).join("")}</select>
         <button onclick="compareTwoRounds()">对比</button>
       </div><div id="cmpResult"></div>`;
}

window.compareTwoRounds = async function () {
  const from = document.getElementById("cmpFrom").value;
  const to = document.getElementById("cmpTo").value;
  const [a, b] = await Promise.all([
    api("/api/tree", { run: state.run, label: from }),
    api("/api/tree", { run: state.run, label: to }),
  ]);
  // 计算两轮之间新增/移除的规则，并在树形图上高亮
  const idsOf = (tree) => {
    const s = new Set();
    Object.entries(tree || {}).forEach(([cwe, fam]) =>
      (fam.invariants || []).forEach(n => s.add(n.invariant_id)));
    return s;
  };
  const A = idsOf(a.tree), B = idsOf(b.tree);
  const highlight = {};
  B.forEach(id => { if (!A.has(id)) highlight[id] = "added"; });
  A.forEach(id => { if (!B.has(id)) highlight[id] = "removed"; });
  const added = [...B].filter(i => !A.has(i)), removed = [...A].filter(i => !B.has(i));
  document.getElementById("cmpResult").innerHTML =
    `<div class="mini">${esc(from)} → ${esc(to)}：新增 ${added.length} 条、移除 ${removed.length} 条
      （绿框=新增，红框=移除）</div>
     <div class="row"><div class="half"><h4>${esc(from)}</h4><div id="cmpTreeA"></div></div>
     <div class="half"><h4>${esc(to)}</h4><div id="cmpTreeB"></div></div></div>`;
  mountTree(document.getElementById("cmpTreeA"), a.tree || {}, { highlight });
  mountTree(document.getElementById("cmpTreeB"), b.tree || {}, { highlight });
};

async function renderPhase3() {
  const d = await api("/api/phase3", { run: state.run });
  const dec = d.decision_counts || {};
  const fe = d.final_eval_summary || {};
  $("p3Cards").innerHTML =
    card("门控审计条目", nz((d.audit_entries || []).length), "条经验") +
    card("supported", nz(dec.supported || 0), "有正证据，晋升入树") +
    card("revised/demoted", nz((dec.revised || 0) + (dec.demoted || 0)), "未通过") +
    card("unmeasured", nz(dec.unmeasured || 0), "无证据（Δ=0），不晋升但保留在池里检索") +
    card("冻结 M*", nz(d.frozen_size), "条经验") +
    card("最终评测 JointPass", fe.joint_pass_rate != null ? pct(fe.joint_pass_rate) : "未进行",
         fe.eval_pool_size ? `${fe.joint_pass}/${fe.eval_pool_size}` : "");

  const entries = d.audit_entries || [];
  // 门控 LLM 选择器：来源分布、跨 CWE 情况
  const bySource = {};
  (entries).forEach(a => { const k = a.audit_source || "?"; bySource[k] = (bySource[k] || 0) + 1; });
  const llmSelected = entries.filter(a => a.audit_source === "llm_selected").length;
  const crossTotal = entries.reduce((s, a) => s + (a.cross_cwe_count || 0), 0);
  $("p3Audit").innerHTML = entries.length ? `
    <div class="cards" style="margin-bottom:10px">
      ${card("LLM 选择器规划", llmSelected + "/" + entries.length, "条经验由 LLM 挑任务")}
      ${card("跨 CWE 审计任务", crossTotal, "检验泛化性")}
      ${card("审计来源", Object.entries(bySource).map(([k, v]) => k + ":" + v).join(" "), "")}
    </div>
    <table>
    <tr><th>经验</th><th>来源</th><th>需通过任务</th><th>选了哪些任务</th><th>跨CWE</th>
        <th>基线</th><th>加经验</th><th>Δ</th><th>判定</th></tr>
    ${entries.map(a => {
      const tasks = a.selected_tasks || [];
      const taskCells = tasks.length ? tasks.map(t =>
        `<span class="pill ${t.cross_cwe ? "revised" : "supported"}"
          title="CWE-${esc(t.cwe)}${t.cross_cwe ? "（跨 CWE）" : ""}">${esc(t.task_id)}</span>`).join("")
        : '<span class="muted">（无）</span>';
      return `<tr>
      <td class="mini">${esc(a.candidate_id)}<br>
        <span class="muted">${esc(a.source_stage || "")}/${esc(a.source_kind || "")}</span></td>
      <td class="mini">${esc(a.audit_source || "")}</td>
      <td>${esc(a.audit_task_count)}</td>
      <td>${taskCells}${a.selector_reason ? `<div class="mini">理由：${esc(a.selector_reason)}</div>` : ""}</td>
      <td>${a.cross_cwe_count ? `<b>${esc(a.cross_cwe_count)}</b>` : "0"}</td>
      <td>${esc(nz(a.baseline_pass))}</td><td>${esc(nz(a.with_candidate_pass))}</td>
      <td>${esc(a.delta_joint_pass)}</td>
      <td><span class="pill ${esc(a.decision)}">${esc(a.decision)}</span></td></tr>`;
    }).join("")}
    </table>
    <div class="mini" style="margin-top:6px">绿框=同 CWE 任务，黄框=跨 CWE 任务（用于检验经验泛化性）</div>`
    : empty("该运行未采集门控审计明细");

  // ---- 树的变化（清晰化）----
  const tb = d.tree_before || {}, ta = d.tree_after || {};
  const delta = d.cwe_delta || [];
  const changeRows = d.change_rows || [];
  const hasChange = tb.total != null || ta.total != null || changeRows.length;
  if (!hasChange) {
    $("p3TreeChange").innerHTML = empty("该运行未采集树变化数据（历史运行）");
  } else {
    const statBar = (label, x) => `<tr><td>${esc(label)}</td>
      <td>${nz(x.total)}</td><td>${nz(x.active)}</td><td>${nz(x.provisional)}</td>
      <td>${nz(x.consolidated)}</td><td>${nz(x.revised)}</td><td>${nz(x.retired)}</td>
      <td>${nz(x.cwe_count)}</td></tr>`;
    // 分 CWE 增减柱状图
    const maxAbs = Math.max(1, ...delta.map(x => Math.abs(x.delta)));
    const bars = delta.length ? delta.map(x => {
      const w = Math.abs(x.delta) / maxAbs * 100;
      const pos = x.delta >= 0;
      return `<div style="display:flex;align-items:center;gap:8px;margin:3px 0">
        <span class="mini" style="width:78px">CWE-${esc(x.cwe)}</span>
        <span style="flex:1;display:flex">
          <span style="flex:1;text-align:right">
            ${pos ? "" : `<span style="display:inline-block;height:12px;width:${w}%;background:var(--bad);border-radius:2px"></span>`}
          </span>
          <span style="width:2px;background:var(--line)"></span>
          <span style="flex:1">
            ${pos ? `<span style="display:inline-block;height:12px;width:${w}%;background:var(--accent);border-radius:2px"></span>` : ""}
          </span>
        </span>
        <span class="mini" style="width:110px">${esc(x.before)} → ${esc(x.after)}
          <b class="${x.delta > 0 ? "diff-add" : x.delta < 0 ? "diff-del" : ""}">
          ${x.delta > 0 ? "+" : ""}${x.delta}</b></span>
      </div>`;
    }).join("") : empty("无分 CWE 变化");

    $("p3TreeChange").innerHTML = `
      <h4>门控前后树的整体对比</h4>
      <table><tr><th>时点</th><th>总节点</th><th>active</th><th>provisional</th>
        <th>consolidated</th><th>revised</th><th>retired</th><th>CWE 数</th></tr>
        ${tb.total != null ? statBar("门控前", tb) : ""}
        ${ta.total != null ? statBar("门控后", ta) : ""}
      </table>
      <div class="mini" style="margin-top:6px">经验池：共 ${nz(d.pool_total)} 条，
        状态分布 ${esc(JSON.stringify(d.pool_by_status || {}))}</div>

      <h4 style="margin-top:14px">分 CWE 节点数增减</h4>
      ${bars}

      <h4 style="margin-top:14px">每条经验的升级/降级明细（门控判定结果）</h4>
      ${changeRows.length ? `
      <div class="cards" style="margin-bottom:8px">
        ${Object.entries(d.decision_counts || {}).map(([k, v]) =>
          card(k, v, { supported: "有正证据，晋升入树", revised: "退回修订",
                       demoted: "有负证据，降级淘汰",
                       unmeasured: "无证据（Δ=0），不晋升但保留检索" }[k] || "")).join("")}
      </div>
      <div class="scroll"><table>
        <tr><th>经验</th><th>CWE</th><th>来源</th><th>审计来源</th><th>ΔJointPass</th>
            <th>审查任务数</th><th>判定（升级/降级）</th><th>理由</th></tr>
        ${changeRows.map(r => `<tr>
          <td class="mini">${esc(r.invariant_id)}</td><td>CWE-${esc(r.cwe)}</td>
          <td class="mini">${esc(r.source_stage || "")}/${esc(r.source_kind || "")}</td>
          <td class="mini">${esc(r.audit_source || "")}</td>
          <td>${esc(nz(r.delta))}</td><td>${esc(nz(r.audit_tasks))}</td>
          <td><span class="pill ${esc(r.decision)}">${esc(r.decision)}</span>
            <span class="mini">${r.decision === "supported" ? "↑ 升级入树"
              : r.decision === "demoted" ? "↓ 降级淘汰"
              : r.decision === "revised" ? "→ 退回修订" : "? 未测量"}</span></td>
          <td class="mini">${esc((r.reasons || []).join(", "))}</td></tr>`).join("")}
      </table></div>` : empty("无门控明细")}

      <h4 style="margin-top:14px">逐轮树状态（门控前 → 门控后）</h4>
      ${(d.rounds_tree || []).length ? `
      <table><tr><th>轮</th><th>门控前 active</th><th>门控后 active</th><th>晋升</th>
        <th>归并</th><th>剪枝</th><th>审查条数</th></tr>
        ${(d.rounds_tree || []).map(r => `<tr><td>第 ${esc(r.round)} 轮</td>
          <td>${nz(r.before && r.before.active)} <span class="mini">/${nz(r.before && r.before.total)}</span></td>
          <td>${nz(r.after && r.after.active)} <span class="mini">/${nz(r.after && r.after.total)}</span></td>
          <td>${esc(nz(r.promoted))}</td><td>${esc(nz(r.merged))}</td><td>${esc(nz(r.pruned))}</td>
          <td>${esc(nz(r.audited))}</td></tr>`).join("")}
      </table>` : empty("无逐轮树记录")}

      <h4 style="margin-top:14px">门控后的树（可缩放拖动）</h4>
      <div id="p3TreeGraph"></div>`;
    const tg = $("p3TreeGraph");
    const treeData = d.tree_final_snapshot || d.tree_after_snapshot;
    if (treeData && Object.keys(treeData).length) mountTree(tg, treeData);
    else tg.innerHTML = empty("无树数据");
  }

  if (!fe.eval_pool_size) {
    $("p3Final").innerHTML = empty("未进行最终评测（该运行未采集）");
    $("p3FinalFail").innerHTML = empty("—");
    return;
  }

  const arms = fe.arms || {};
  const ARM_LABEL = {
    baseline: "baseline（无经验）",
    memory: "memory（注入经验池）",
    filtered: "filtered（门控筛选，主结果）",
  };
  const armOrder = ["baseline", "memory", "filtered"].filter(k => arms[k]);
  const cav = fe.caveats || {};

  // ---- 口径声明：引用本页任何数字都必须带上，避免把带选择偏差的数当成泛化结果 ----
  const caveatHtml = (cav.selection_bias || cav.independent_heldout === false) ? `
    <div class="caveat">
      <b>口径声明（引用本页数字时必须一并说明）</b>
      <ul>
        ${cav.independent_heldout === false
          ? "<li><code>independent_heldout = false</code>：filtered 臂用 D_gate 做选择，"
            + "<b>不是独立泛化证据</b>，只能作为门控筛选后的观测值。</li>" : ""}
        ${cav.selection_bias ? `<li>${esc(cav.selection_bias)}</li>` : ""}
        ${cav.generation_policy
          ? `<li>生成策略 <code>${esc(cav.generation_policy)}</code>：单次生成、不做修复，`
            + "因此该数字是方法的<b>单轮能力上限</b>，不是多轮修复后的结果。</li>" : ""}
        ${cav.long_term_memory_modified === false
          ? "<li>最终评测期间 <code>long_term_memory_modified = false</code>："
            + "评测反馈未回流进经验库，数据隔离成立。</li>" : ""}
      </ul>
    </div>` : "";

  // ---- 三臂对比：分母统一用 measured（实测样本），未测量单列，不与失败混同 ----
  const baseJoint = ((arms.baseline || {}).measured_rates || {}).joint_pass;
  const armsTable = armOrder.length ? `
    <h4>三臂对比（同一审计池，分母为实测样本）</h4>
    <table><tr><th>臂</th><th>功能</th><th>安全</th><th>Joint</th><th>实测样本</th>
      <th>Joint 相对 baseline</th></tr>
    ${armOrder.map(k => {
      const a = arms[k], mr = a.measured_rates || {};
      // baseline 与自身比较没有意义，显示 "—" 而不是 "+0.0pp"
      const delta = (k !== "baseline" && mr.joint_pass != null && baseJoint != null)
        ? mr.joint_pass - baseJoint : null;
      const dTxt = delta == null ? "—"
        : `<b style="color:${delta > 0 ? "var(--accent)" : delta < 0 ? "var(--bad)" : "var(--muted)"}">`
          + `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)}pp</b>`;
      return `<tr>
        <td>${esc(ARM_LABEL[k] || k)}</td>
        <td>${nz(a.functional_pass)}/${nz(a.measured)} <span class="muted">${pct(mr.functional_pass)}</span></td>
        <td>${nz(a.security_pass)}/${nz(a.measured)} <span class="muted">${pct(mr.security_pass)}</span></td>
        <td><b>${nz(a.joint_pass)}/${nz(a.measured)}</b> <span class="muted">${pct(mr.joint_pass)}</span></td>
        <td>${nz(a.measured)}${a.unmeasured ? ` <span class="muted">(未测 ${a.unmeasured})</span>` : ""}</td>
        <td>${dTxt}</td></tr>`;
    }).join("")}
    </table>
    <div class="mini" style="margin-top:6px">评测池共 ${esc(fe.eval_pool_size)} 条；
      上表分母是<b>实测样本数</b>（扣掉未测量），未测量项单列显示，绝不折算成失败或通过。</div>
    <h4 style="margin-top:14px">四态分布（A=功能+安全都过 · B=只过功能 · C=只过安全 · D=都不过）</h4>
    ${armOrder.map(k => `<div style="margin-bottom:8px">
      <div class="mini">${esc(ARM_LABEL[k] || k)}</div>${abcdBar(arms[k].states || {})}</div>`).join("")}
  ` : empty("该运行未采集三臂对比（global_gate.arms 缺失）");

  // ---- 分 CWE：通过率升序，最差在前；对"安全全过但功能全挂"的家族给出诊断提示 ----
  const byCwe = fe.by_cwe || [];
  const cweTable = byCwe.length ? `
    <h4 style="margin-top:14px">分 CWE 表现（按 Joint 通过率升序，重灾区在前）</h4>
    <table><tr><th>CWE</th><th>Joint</th><th>通过率</th><th>四态</th><th>诊断提示</th></tr>
    ${byCwe.map(v => {
      const st = v.states || {};
      const zero = !v.joint;
      const stTxt = ["A", "B", "C", "D", "U"].filter(x => st[x]).map(x => `${x}=${st[x]}`).join(" ");
      // C 桶 == 全量且样本>=5：安全全过、功能全挂。这个组合更像过度防御
      // （安全补丁把功能测试的合法输入也拒了）或 harness 函数签名不匹配，
      // 而不是模型"写不出安全代码"。必须让它在页面上显眼，否则会被误读成模型能力问题。
      const funcWipeout = zero && (st.C || 0) === v.total && v.total >= 5;
      return `<tr${zero ? ' class="row-zero"' : ""}>
        <td>CWE-${esc(v.cwe)}</td>
        <td>${v.joint}/${v.total}</td>
        <td><b>${pct(v.joint_pass_rate)}</b></td>
        <td class="mini">${esc(stTxt)}</td>
        <td class="mini">${funcWipeout
          ? '<span class="flag">安全全过 / 功能全挂 → 优先排查过度防御或夹具签名，而非模型能力</span>'
          : ""}</td></tr>`;
    }).join("")}
    </table>
    <div class="mini" style="margin-top:6px">红色行 = 该 CWE 家族 Joint 通过率为 0。
      注意通过率是按 CWE 聚合的<b>描述性统计</b>，单个家族样本少（最小 10 条），不要据此下强结论。</div>
  ` : "";

  // ---- 距目标线差距分解：把"还差几条"换算成"要从哪个桶回收多少条" ----
  const gapHtml = `
    <h4 style="margin-top:14px">距目标线的差距分解</h4>
    <div class="row" style="align-items:center;margin-bottom:8px">
      <label class="mini">目标 Joint 通过率
        <select id="gapTarget" onchange="window.updateGap(this.value)">
          ${[30, 35, 40, 45, 50].map(t =>
            `<option value="${t}"${t === 40 ? " selected" : ""}>${t}%</option>`).join("")}
        </select></label>
      <span class="mini">（目标线仅用于差距量化，<b>不是已取得的结果</b>）</span>
    </div>
    <div id="gapBox"></div>`;

  $("p3Final").innerHTML =
    caveatHtml +
    `<div class="cards">
      ${card("JointPass（主结果）", pct(fe.joint_pass_rate), `${nz(fe.joint_pass)}/${nz(fe.eval_pool_size)} 全池`)}
      ${card("未达 A", nz(fe.failure_count), "功能/安全未同时通过")}
      ${card("C 桶（安全过·功能挂）", nz((arms.filtered || {}).states ? arms.filtered.states.C : null), "当前最大的可回收空间")}
      ${card("评测任务数", nz(fe.eval_pool_size), "审计池全量")}
    </div>` +
    armsTable + gapHtml + cweTable;

  // 差距分解依赖 arms，选择目标后只重算这一块，不重渲染整页
  state.gapArms = arms;
  window.updateGap = function (targetPct) {
    const box = $("gapBox");
    if (!box) return;
    const f = arms.filtered || arms.memory || arms.baseline;
    if (!f) { box.innerHTML = empty("无臂数据"); return; }
    const measured = f.measured || 0;
    const current = f.joint_pass || 0;
    const st = f.states || {};
    const target = Number(targetPct) / 100;
    if (!measured) { box.innerHTML = empty("无实测样本，无法分解"); return; }
    const required = Math.ceil(target * measured);
    const need = Math.max(0, required - current);
    const recoverable = (st.C || 0) + (st.B || 0);
    const minShare = recoverable ? Math.min(100, (need / recoverable) * 100) : 0;
    box.innerHTML = `
      <div class="cards">
        ${card("当前", pct((f.measured_rates || {}).joint_pass), `${current}/${measured} 实测`)}
        ${card("需要达到", `${required} 条`, `目标 ${(target * 100).toFixed(0)}%`)}
        ${card(need ? "还差" : "已达标", need ? `${need} 条` : "✓", need ? "需要额外转为 A 的任务数" : "当前已满足该目标线")}
        ${card("可回收桶 C+B", recoverable, `C=${st.C || 0} · B=${st.B || 0}`)}
        ${card("需回收比例", need ? minShare.toFixed(1) + "%" : "0%", "占 C+B 的比例")}
      </div>
      <div class="mini">
        口径：<b>C</b>（安全已过、只差功能）与 <b>B</b>（功能已过、只差安全）各回收 1 条 = Joint +1。
        <b>D</b> 桶（功能和安全都挂）需要同时修好两项，成本高得多，未计入可回收空间。
        ${need ? "" : "当前已达标，无需回收。"}
      </div>`;
  };
  window.updateGap(40);

  // ---- 失败明细：必须区分"未采集"和"真的全过" ----
  const fails = fe.failures;
  if (fails == null) {
    // 字段缺失 ≠ 全部通过。老产物没有该字段时不能报喜。
    $("p3FinalFail").innerHTML =
      empty("该运行未采集失败明细（字段缺失，不代表全部通过）");
  } else if (!fails.length) {
    $("p3FinalFail").innerHTML = empty("已采集明细，0 条未达 A");
  } else {
    const cnt = fails.reduce((m, r) => { m[r.state] = (m[r.state] || 0) + 1; return m; }, {});
    $("p3FinalFail").innerHTML = `
      <div class="mini">共 ${fails.length} 条未达 A　
        ${["C", "B", "D", "U"].filter(k => cnt[k]).map(k => `${k}=${cnt[k]}`).join(" · ")}　
        （默认 C 桶优先，它是差距分解里的可回收空间）</div>
      <div class="scroll"><table>
      <tr><th>task</th><th>CWE</th><th>状态</th><th>功能</th><th>安全</th><th>语法</th><th>检索到的经验</th></tr>
      ${fails.map(r => `<tr>
        <td>${esc(r.task_id)}</td><td>CWE-${esc(r.cwe)}</td>
        <td><span class="pill ${r.state === "C" ? "revised" : "unmeasured"}">${esc(r.state)}</span></td>
        <td>${esc(r.functional)}</td><td>${esc(r.security)}</td><td>${esc(r.syntax)}</td>
        <td class="mini">${esc((r.retrieved_ids || []).join(", ") || "（无）")}</td></tr>`).join("")}
      </table></div>`;
  }
}

async function renderPool() {
  const pool = await api("/api/pool", { run: state.run, which: "audit" });
  const exp = await api("/api/phase3", { run: state.run });
  const frozen = exp.frozen_sample || [];
  $("poolCards").innerHTML =
    card("审计池任务", nz(pool.counts), "D_gate") +
    card("冻结经验 M*", nz(exp.frozen_size), "条");
  $("poolList").innerHTML = "";
  if (frozen.length) {
    mountTree($("poolList"), frozen.reduce((acc, n) => {
      const c = n.cwe || "?";
      (acc[c] = acc[c] || { invariants: [] }).invariants.push(n);
      return acc;
    }, {}));
  } else {
    $("poolList").innerHTML = empty("未采集冻结经验清单");
  }
  $("auditPoolList").innerHTML = (pool.tasks || []).length ? `
    <table><tr><th>task_id</th><th>CWE</th><th>描述</th></tr>
    ${pool.tasks.map(r => `<tr><td>${esc(r.task_id)}</td><td>CWE-${esc(r.cwe)}</td>
      <td class="mini">${esc((r.description || "").slice(0, 100))}</td></tr>`).join("")}
    </table>` : empty("未采集审计池清单");
}

/* ---------------- 导出 ---------------- */
window.exportData = async function (kind) {
  const data = await api("/api/export", { run: state.run, kind });
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${state.run}_${kind}.json`;
  a.click();
};

/* ---------------- 主循环 ---------------- */
async function refreshAll() {
  if (!state.run) return;
  state.errors = [];
  const jobs = [renderOverview(), renderPhase1(), renderPhase2(), renderPhase3(), renderPool()];
  const settled = await Promise.allSettled(jobs);
  const failed = settled.filter(s => s.status === "rejected");
  if (failed.length) {
    // 明确提示加载失败，而不是让页面显示一堆 0
    const box = document.getElementById("loadErrors");
    box.style.display = "block";
    box.innerHTML = `<b>⚠️ 有 ${failed.length} 个面板加载失败</b>` +
      state.errors.map(e => `<div class="mini">${esc(e)}</div>`).join("");
  } else {
    document.getElementById("loadErrors").style.display = "none";
  }
  $("lastUpdated").textContent = "最后刷新：" + new Date().toLocaleTimeString();
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tabpane").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      $("tab-" + btn.dataset.tab).classList.add("active");
      // 切换后通知页面内容：树形图在隐藏状态下 clientWidth=0，
      // 初次 fit 会算出极小缩放（实测被压到 0.17），必须等可见后重新适应。
      window.dispatchEvent(new CustomEvent("dsh-tab-shown", {
        detail: { tab: btn.dataset.tab },
      }));
    };
  });
}

function setupAutoRefresh() {
  $("autoRefresh").onchange = (e) => {
    if (state.timer) { clearInterval(state.timer); state.timer = null; }
    if (e.target.checked) {
      state.timer = setInterval(async () => { await loadRuns(); await refreshAll(); }, 5000);
    }
  };
  $("refreshBtn").onclick = async () => { await loadRuns(); await refreshAll(); };
}

(async function init() {
  setupTabs();
  setupAutoRefresh();
  await loadRuns();
  await refreshAll();
})();
