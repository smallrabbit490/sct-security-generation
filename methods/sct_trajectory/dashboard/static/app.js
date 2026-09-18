/* CLE 自进化任务看板 — 前端逻辑
 * 只读后端 API，负责：运行选择、状态徽章、5 个 Tab 渲染、导出、自动刷新。
 * 图表全部用内联 SVG/div 手绘，不引入任何第三方库。
 */
const $ = (id) => document.getElementById(id);
const state = { run: "", runs: [], timer: null };

/* ---------------- 基础工具 ---------------- */
async function api(path, params = {}) {
  const q = new URLSearchParams(params).toString();
  const res = await fetch(path + (q ? "?" + q : ""));
  return res.json();
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

async function renderPhase2() {
  const d = await api("/api/phase2", { run: state.run });
  const rounds = d.rounds || [];
  $("p2Cards").innerHTML =
    card("重放池任务数", nz((d.replay_pool || []).length), "D_grow") +
    card("演进轮数", nz(rounds.length), "轮") +
    card("Phase2 轨迹数", nz((d.trajectories || []).length), "条") +
    card("晋升总数", nz(rounds.reduce((a, r) => a + (r.promoted || 0), 0)), "经验入树");

  $("p2Pool").innerHTML = (d.replay_pool || []).length ? `
    <div class="scroll"><table><tr><th>task_id</th><th>CWE</th><th>描述</th></tr>
    ${d.replay_pool.map(r => `<tr><td>${esc(r.task_id)}</td><td>CWE-${esc(r.cwe)}</td>
      <td class="mini">${esc((r.description || "").slice(0, 90))}</td></tr>`).join("")}
    </table></div>` : empty("该运行未采集任务池（历史运行）");

  $("p2Rounds").innerHTML = rounds.length ? rounds.map(r => {
    const sch = r.schedule || {};
    const dec = (sch.raw_decisions || []).filter(x => x.Selected);
    return `<details class="cwe" open><summary>第 ${esc(r.round)} 轮
      · 池 ${esc(r.replay_candidates)} · 选中 ${esc(r.selected)} · 晋升 ${esc(r.promoted)}
      · 树 ${esc(r.tree_nodes)} 节点</summary>
      <div class="mini">LLM 返回 ${(sch.raw_decisions || []).length} 条决策，选中 id：
        ${esc(JSON.stringify(sch.selected_ids || []))}
        ${sch.fallback_used ? "（触发规则兜底）" : ""} ${sch.error ? "错误：" + esc(sch.error) : ""}</div>
      ${dec.length ? `<table><tr><th>task_id</th><th>理由</th></tr>
        ${dec.map(x => `<tr><td>${esc(x.Task_ID)}</td><td class="mini">${esc(x.Reason || "")}</td></tr>`).join("")}
        </table>` : `<div class="empty">本轮 LLM 未选中任何任务</div>`}
    </details>`;
  }).join("") : empty("该运行未采集轮次记录");

  $("p2Abcd").innerHTML = abcdBar(d.abcd || {});
  $("p2Traj").innerHTML = (d.trajectories || []).length ? `
    <table><tr><th>task</th><th>CWE</th><th>状态序列</th><th>检索命中</th></tr>
    ${d.trajectories.map(t => `<tr><td>${esc(t.task_id)}</td><td>CWE-${esc(t.cwe)}</td>
      <td>${esc((t.states || []).join(" → "))}</td>
      <td class="mini">${esc((t.retrieved_ids || []).join(", ") || "（无）")}</td></tr>`).join("")}
    </table>` : empty("无轨迹");

  $("p2Growth").innerHTML = growthChart(d.tree_growth || []);
}

async function renderPhase3() {
  const d = await api("/api/phase3", { run: state.run });
  const dec = d.decision_counts || {};
  const fe = d.final_eval_summary || {};
  $("p3Cards").innerHTML =
    card("门控审计条目", nz((d.audit_entries || []).length), "条经验") +
    card("supported", nz(dec.supported || 0), "晋升入树") +
    card("revised/demoted", nz((dec.revised || 0) + (dec.demoted || 0)), "未通过") +
    card("unmeasured", nz(dec.unmeasured || 0), "无可用审计任务") +
    card("冻结 M*", nz(d.frozen_size), "条经验") +
    card("最终评测 JointPass", fe.joint_pass_rate != null ? pct(fe.joint_pass_rate) : "未进行",
         fe.eval_pool_size ? `${fe.joint_pass}/${fe.eval_pool_size}` : "");

  const entries = d.audit_entries || [];
  $("p3Audit").innerHTML = entries.length ? `
    <div class="scroll"><table>
    <tr><th>经验</th><th>来源</th><th>需通过任务数</th><th>审计来源</th><th>基线</th><th>加经验</th><th>Δ</th><th>判定</th></tr>
    ${entries.map(a => `<tr>
      <td class="mini">${esc(a.candidate_id)}</td>
      <td class="mini">${esc(a.source_stage || "")}/${esc(a.source_kind || "")}</td>
      <td>${esc(a.audit_task_count)}</td>
      <td class="mini">${esc(a.audit_source || "")}</td>
      <td>${esc(nz(a.baseline_pass))}</td><td>${esc(nz(a.with_candidate_pass))}</td>
      <td>${esc(a.delta_joint_pass)}</td>
      <td><span class="pill ${esc(a.decision)}">${esc(a.decision)}</span></td></tr>`).join("")}
    </table></div>` : empty("该运行未采集门控审计明细");

  $("p3TreeChange").innerHTML = `<div class="mini">判定分布：`
    + Object.entries(dec).map(([k, v]) => `<span class="pill ${esc(k)}">${esc(k)}: ${v}</span>`).join("")
    + `</div>` + empty("树快照见 Phase1 / Phase2 页（每轮快照）");

  if (!fe.eval_pool_size) {
    $("p3Final").innerHTML = empty("未进行最终评测（该运行未采集）");
    $("p3FinalFail").innerHTML = empty("—");
    return;
  }
  const byCwe = fe.by_cwe || {};
  $("p3Final").innerHTML = `
    <div class="cards">
      ${card("评测任务数", fe.eval_pool_size, "审计池全量")}
      ${card("JointPass", fe.joint_pass, pct(fe.joint_pass_rate))}
    </div>
    ${abcdBar(fe.abcd || {})}
    <h4 style="margin-top:12px">分 CWE 表现</h4>
    <table><tr><th>CWE</th><th>通过/总数</th><th>通过率</th><th>ABCD</th></tr>
    ${Object.entries(byCwe).map(([c, v]) => `<tr><td>CWE-${esc(c)}</td>
      <td>${v.joint}/${v.total}</td><td>${pct(v.joint_pass_rate)}</td>
      <td class="mini">${esc(JSON.stringify(v.abcd))}</td></tr>`).join("")}
    </table>`;

  const fails = (fe.failures || []);
  $("p3FinalFail").innerHTML = fails.length ? `
    <div class="mini">共 ${fails.length} 条未达 A</div>
    <div class="scroll"><table><tr><th>task</th><th>CWE</th><th>状态</th><th>功能</th><th>安全</th><th>检索</th></tr>
    ${fails.map(r => `<tr><td>${esc(r.task_id)}</td><td>CWE-${esc(r.cwe)}</td>
      <td><span class="pill unmeasured">${esc(r.state)}</span></td>
      <td>${esc(r.functional)}</td><td>${esc(r.security)}</td>
      <td class="mini">${esc((r.retrieved_ids || []).join(", ") || "（无）")}</td></tr>`).join("")}
    </table></div>` : empty("全部通过 🎉");
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
  await Promise.all([renderOverview(), renderPhase1(), renderPhase2(),
                     renderPhase3(), renderPool()]);
  $("lastUpdated").textContent = "最后刷新：" + new Date().toLocaleTimeString();
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tabpane").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      $("tab-" + btn.dataset.tab).classList.add("active");
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
