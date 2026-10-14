/* CLE 看板 — 树形图模块（纯 SVG，无第三方库）
 *
 * 三层布局：CWEFamily(根) → SecurityInvariantNode(中) → LanguageLeaf(叶)
 * 特性：
 *   - 全部节点都画（不过滤状态），节点按 status 上色
 *   - 滚轮缩放 + 鼠标拖动平移 + 适应窗口 / 100% / 放大 / 缩小 按钮
 *   - 悬停 tooltip 显示完整不变量文本（图上会被截断）
 *   - 与列表视图可切换
 *
 * 数据来源：tree.json / tree_snapshots/*.json 的 {cwe: {invariants: [...]}} 结构。
 */

const STATUS_COLOR = {
  active:      { fill: "#0d2a17", stroke: "#3fb950", text: "#3fb950" },
  consolidated:{ fill: "#0d2233", stroke: "#58a6ff", text: "#58a6ff" },
  provisional: { fill: "#222a33", stroke: "#8b98a5", text: "#8b98a5" },
  revised:     { fill: "#2d2412", stroke: "#d29922", text: "#d29922" },
  retired:     { fill: "#2d1214", stroke: "#f85149", text: "#f85149" },
  unmeasured:  { fill: "#1b2330", stroke: "#7d8b99", text: "#7d8b99" },
};
const NODE_W = 250, NODE_H = 54, LEAF_W = 90, LEAF_H = 26;
const H_GAP = 56;                  // CWE 家族块之间的横向间距
const V_GAP = 14;                  // 不变量节点之间的纵向间距
const LEAF_GAP = 6;
// 三层的水平偏移（相对家族块左边界）：CWE 根 → 不变量 → 语言叶。
// 原先用 0 / 300 / 600 的固定列起点，导致每个家族块占 700+ px 宽；
// 7 个家族横排后总宽 5406px，缩放后文字不可读。这里压到 0 / 280 / 500。
const LAYER_DX = [0, 280, 500];
// 每个家族块的总宽（含右侧语言叶宽度）
const BLOCK_W = LAYER_DX[2] + LEAF_W;

/* 把 {cwe: {invariants}} 转成布局用的三层节点表
 *
 * 【布局：横向铺开 + 自动分列】
 * 原先是所有 CWE 家族纵向堆叠 → 树又高又窄（8 个家族就 2000+ px），
 * 在固定 560px 高的画布里"适应窗口"会被压到 0.25 倍，完全看不清。
 * 现在改为：先算出每个家族块的**高度**，再按目标行高把家族分到若干列，
 * 每列内部纵向排列、列与列之间横向排列 —— 整体接近画布宽高比，缩放后仍可读。
 */
function buildTreeLayout(tree, opts = {}) {
  // 目标每列高度（px）：让列数自适应，避免单列过高
  const COL_HEIGHT = opts.colHeight || 900;
  const cwes = Object.keys(tree || {}).sort();

  // ---- 第一遍：算每个家族块的高度（不变量数 + 语言叶数决定）----
  const blocks = cwes.map((cwe) => {
    const invs = (tree[cwe] || {}).invariants || [];
    let h = 0;
    invs.forEach((inv) => {
      const leaves = Object.keys(inv.language_leaves || {});
      const n = Math.max(1, leaves.length);
      h += Math.max(NODE_H, n * (LEAF_H + LEAF_GAP) - LEAF_GAP) + V_GAP;
    });
    return { cwe, invs, h: Math.max(h, NODE_H) };
  });

  // ---- 第二遍：把家族分到若干列（每列高度不超过 COL_HEIGHT）----
  const columns = [];
  let cur = [], curH = 0;
  blocks.forEach((b) => {
    // 单个块本身就超过目标高度时，独占一列
    if (curH > 0 && curH + b.h > COL_HEIGHT) {
      columns.push({ blocks: cur, h: curH });
      cur = []; curH = 0;
    }
    cur.push(b);
    curH += b.h + 28;                  // 28 = 家族之间的留白
  });
  if (cur.length) columns.push({ blocks: cur, h: curH });

  // ---- 第三遍：按列摆放坐标 ----
  const rootNodes = [], invNodes = [], leafNodes = [], edges = [];
  let colX = 40;
  let maxBottom = 0;
  columns.forEach((col) => {
    let y = 30;
    col.blocks.forEach((b) => {
      const { cwe, invs } = b;
      const blockTop = y;
      let invY = y;
      invs.forEach((inv, i) => {
        const iid = inv.invariant_id || `${cwe}-${i}`;
        invNodes.push({ id: iid, cwe, inv, x: colX + LAYER_DX[1], y: invY, w: NODE_W, h: NODE_H });
        edges.push({ from: `cwe:${cwe}`, to: `inv:${iid}`, kind: "cwe-inv" });
        const leaves = Object.keys(inv.language_leaves || {});
        const useLeaves = leaves.length ? leaves : ["(无叶)"];
        let leafY = invY + (NODE_H - (useLeaves.length * (LEAF_H + LEAF_GAP) - LEAF_GAP)) / 2;
        useLeaves.forEach((lang, k) => {
          const lid = `${iid}::${lang}`;
          leafNodes.push({ id: lid, lang, isEmpty: !leaves.length, x: colX + LAYER_DX[2],
                           y: leafY, w: LEAF_W, h: LEAF_H });
          edges.push({ from: `inv:${iid}`, to: `leaf:${lid}`, kind: "inv-leaf" });
          leafY += LEAF_H + LEAF_GAP;
        });
        invY += Math.max(NODE_H, useLeaves.length * (LEAF_H + LEAF_GAP) - LEAF_GAP) + V_GAP;
      });
      const blockBottom = Math.max(invY - V_GAP, blockTop + NODE_H);
      rootNodes.push({ id: `cwe:${cwe}`, cwe,
                       x: colX, y: (blockTop + blockBottom) / 2 - NODE_H / 2,
                       w: NODE_W * 0.7, h: NODE_H, count: invs.length });
      y = blockBottom + 28;
      maxBottom = Math.max(maxBottom, y);
    });
    colX += BLOCK_W + H_GAP;   // 列宽 = 家族块宽 + 家族间距
  });

  return {
    rootNodes, invNodes, leafNodes, edges,
    height: maxBottom + 20,
    width: Math.max(colX + 40, 700),
    columns: columns.length,
  };
}

const esc2 = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const clip = (s, n) => (s && s.length > n ? s.slice(0, n) + "…" : (s || ""));

/* 生成 SVG 字符串 */
function treeSvgMarkup(tree, { highlight = {} } = {}) {
  const L = buildTreeLayout(tree);
  if (!L.rootNodes.length) return { svg: "", width: 400, height: 120, empty: true };
  const pos = {};
  L.rootNodes.forEach(n => pos[n.id] = n);
  L.invNodes.forEach(n => pos[n.id] = n);
  L.leafNodes.forEach(n => pos[n.id] = n);

  const edgeSvg = L.edges.map(e => {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) return "";
    const x1 = a.x + a.w, y1 = a.y + a.h / 2, x2 = b.x, y2 = b.y + b.h / 2;
    const mx = (x1 + x2) / 2;
    const stroke = e.kind === "cwe-inv" ? "#2f4a63" : "#242e3a";
    return `<path d="M${x1} ${y1} C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}"
      fill="none" stroke="${stroke}" stroke-width="1.4"/>`;
  }).join("");

  const rootSvg = L.rootNodes.map(n => `
    <g class="tnode"><title>CWE-${esc2(n.cwe)}：${n.count} 个不变量节点</title>
      <rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="8"
        fill="#12212f" stroke="#58a6ff" stroke-width="1.6"/>
      <text x="${n.x + 12}" y="${n.y + 22}" fill="#58a6ff" font-size="13" font-weight="600">
        CWE-${esc2(n.cwe)}</text>
      <text x="${n.x + 12}" y="${n.y + 40}" fill="#8b98a5" font-size="11">
        ${n.count} 个不变量</text>
    </g>`).join("");

  const invSvg = L.invNodes.map(n => {
    const inv = n.inv || {};
    const st = inv.status || "provisional";
    const c = STATUS_COLOR[st] || STATUS_COLOR.provisional;
    const hl = highlight[n.id];
    const stroke = hl === "added" ? "#3fb950" : hl === "removed" ? "#f85149"
                 : hl === "changed" ? "#d29922" : c.stroke;
    const sw = hl ? 2.6 : 1.4;
    const tip = `[${st}] utility=${inv.utility ?? "-"}\n${inv.high_level_invariant || ""}\n`
      + (inv.positive_principle ? `正向：${inv.positive_principle}\n` : "")
      + (inv.negative_guardrail ? `红线：${inv.negative_guardrail}\n` : "")
      + (inv.source ? `来源：${inv.source.stage || ""}/${inv.source.kind || ""}` : "");
    return `<g class="tnode"><title>${esc2(tip)}</title>
      <rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="6"
        fill="${c.fill}" stroke="${stroke}" stroke-width="${sw}"/>
      <text x="${n.x + 10}" y="${n.y + 17}" fill="${c.text}" font-size="10.5">
        ${esc2(st)}${inv.utility != null ? ` · u=${inv.utility}` : ""}${
          inv.source && inv.source.stage ? ` · ${esc2(inv.source.stage)}` : ""}</text>
      <text x="${n.x + 10}" y="${n.y + 33}" fill="#c9d4e0" font-size="11">
        ${esc2(clip(inv.high_level_invariant, 30))}</text>
      <text x="${n.x + 10}" y="${n.y + 47}" fill="#8b98a5" font-size="10">
        ${esc2(clip(inv.positive_principle || inv.negative_guardrail || inv.applicability, 34))}</text>
    </g>`;
  }).join("");

  const leafSvg = L.leafNodes.map(n => `
    <g class="tnode"><title>语言叶：${esc2(n.lang)}${n.isEmpty ? "（无叶数据）" : ""}</title>
      <rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="13"
        fill="${n.isEmpty ? "#161c24" : "#152430"}" stroke="${n.isEmpty ? "#2a3441" : "#3d6b8a"}"
        stroke-width="1.2"/>
      <text x="${n.x + n.w / 2}" y="${n.y + 17}" text-anchor="middle"
        fill="${n.isEmpty ? "#5a6673" : "#79b8e0"}" font-size="11">${esc2(n.lang)}</text>
    </g>`).join("");

  return {
    svg: `${edgeSvg}${rootSvg}${invSvg}${leafSvg}`,
    width: L.width, height: L.height, empty: false,
    stats: { cwe: L.rootNodes.length, inv: L.invNodes.length, leaf: L.leafNodes.length },
  };
}

/* 挂载一个可缩放拖动的树形图到容器 */
function mountTree(container, tree, opts = {}) {
  const { svg, width, height, empty, stats } = treeSvgMarkup(tree, opts);
  if (empty) {
    container.innerHTML = `<div class="empty">树为空（该运行未采集树数据）</div>`;
    return;
  }
  const pad = 40;
  const state = { x: 0, y: 0, k: 1, dragging: false, lx: 0, ly: 0 };
  container.innerHTML = `
    <div class="treebar">
      <button data-act="in">＋ 放大</button>
      <button data-act="out">－ 缩小</button>
      <button data-act="reset">100%</button>
      <button data-act="fit">适应窗口</button>
      <button data-act="fitw">适应宽度</button>
      <span class="mini">滚轮缩放 · 按住拖动平移 · 悬停看完整文本</span>
      <span class="mini">CWE ${stats.cwe} · 不变量 ${stats.inv} · 语言叶 ${stats.leaf}</span>
      <button data-act="list" class="tree-toggle">切换列表视图</button>
    </div>
    <div class="treecanvas"><svg xmlns="http://www.w3.org/2000/svg">
      <g class="viewport">${svg}</g>
    </svg></div>`;

  const canvas = container.querySelector(".treecanvas");
  const svgEl = container.querySelector("svg");
  const vp = container.querySelector(".viewport");

  /* 画布高度自适应：树很高时给更高画布，避免"适应窗口"把内容压成糊。
     上限 1100px（超过就该靠缩放/拖动看，而不是无限拉长页面）。*/
  const canvasH = Math.max(420, Math.min(1100, Math.round(height * 0.62) + 80));
  canvas.style.height = `${canvasH}px`;

  function apply() {
    vp.setAttribute("transform", `translate(${state.x} ${state.y}) scale(${state.k})`);
    const w = width * state.k + pad * 2, h = height * state.k + pad * 2;
    svgEl.setAttribute("width", w);
    svgEl.setAttribute("height", h);
    // 让 svg 至少撑满画布，避免内容比画布小时出现"贴边"的视觉问题
    svgEl.style.minWidth = "100%";
    svgEl.style.minHeight = `${canvasH}px`;
  }
  /* 画布可用宽度：减去左侧固定导航栏（黑色栏）的宽度，避免内容被栏挡住。
     优先用 canvas 自身宽度；若为 0（未布局完）则退回窗口宽度估算。*/
  function usableWidth() {
    const cw = canvas.clientWidth;
    return (cw && cw > 120) ? cw : Math.max(320, window.innerWidth - 300);
  }
  /* 适应窗口：宽高都要放下（树很大时会缩得很小，适合先看全貌） */
  function fit() {
    const cw = usableWidth();
    const ch = canvas.clientHeight || canvasH;
    state.k = Math.min((cw - 24) / width, (ch - 24) / height, 1.0);
    state.k = Math.max(state.k, 0.05);
    state.x = Math.max(12, (cw - width * state.k) / 2);
    state.y = 12;
    apply();
  }
  /* 适应宽度（默认视图）：只按宽度缩放，纵向可滚动。
     横向铺开的树用这个最清楚——实测"适应窗口"会把 4466px 宽的树压到 0.21 倍
     （正文只剩 2.3px 不可读）。
     MIN_READABLE_K 保证节点文字可辨认（11px × 0.55 ≈ 6px，配合悬停 tooltip 看全文）；
     若内容确实比画布宽，就允许横向滚动，而不是继续缩小到糊。*/
  const MIN_READABLE_K = 0.55;
  function fitWidth() {
    const cw = usableWidth();
    const kw = (cw - 24) / width;
    state.k = Math.max(MIN_READABLE_K, Math.min(kw, 1.4));
    state.x = 12;
    state.y = 12;
    apply();
  }

  container.querySelectorAll("[data-act]").forEach(btn => {
    btn.onclick = () => {
      const a = btn.dataset.act;
      if (a === "in") state.k = Math.min(state.k * 1.25, 6);
      else if (a === "out") state.k = Math.max(state.k / 1.25, 0.05);
      else if (a === "reset") { state.k = 1; state.x = pad; state.y = pad; }
      else if (a === "fitw") fitWidth();
      else if (a === "fit") return fit();
      else if (a === "list") {
        container.dataset.view = container.dataset.view === "list" ? "graph" : "list";
        container.querySelector(".treecanvas").style.display =
          container.dataset.view === "list" ? "none" : "block";
        container.querySelector(".treelist").style.display =
          container.dataset.view === "list" ? "block" : "none";
        btn.textContent = container.dataset.view === "list" ? "切换图视图" : "切换列表视图";
        return;
      }
      apply();
    };
  });

  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    const nk = Math.min(Math.max(state.k * factor, 0.05), 6);
    // 以鼠标位置为焦点缩放
    state.x = mx - (mx - state.x) * (nk / state.k);
    state.y = my - (my - state.y) * (nk / state.k);
    state.k = nk;
    apply();
  }, { passive: false });

  canvas.addEventListener("mousedown", (e) => {
    state.dragging = true; state.lx = e.clientX; state.ly = e.clientY;
    canvas.style.cursor = "grabbing";
  });
  window.addEventListener("mousemove", (e) => {
    if (!state.dragging) return;
    state.x += e.clientX - state.lx;
    state.y += e.clientY - state.ly;
    state.lx = e.clientX; state.ly = e.clientY;
    apply();
  });
  window.addEventListener("mouseup", () => {
    state.dragging = false;
    canvas.style.cursor = "grab";
  });

  // 列表视图（复用原 treeView，看全文）
  const list = document.createElement("div");
  list.className = "treelist";
  list.style.display = "none";
  list.innerHTML = treeView(tree);
  container.appendChild(list);

  canvas.style.cursor = "grab";
  // 初次布局：等容器完成布局后再 fit（否则 clientWidth 为 0，会退回错误的估算宽度）
  setTimeout(fitWidth, 30);
  // 窗口尺寸变化时重新适应，避免侧栏遮挡或内容溢出
  window.addEventListener("resize", () => { fitWidth(); });
  // 【关键】标签切换后重新适应：树在隐藏的 tabpane 里渲染时 clientWidth=0，
  // 初次 fit 会把缩放压到极小（实测 0.17，完全看不清）。等标签可见后再 fit 一次。
  window.addEventListener("dsh-tab-shown", () => {
    if (!document.body.contains(container)) return;   // 容器已被替换
    if (container.clientWidth === 0) return;          // 仍不可见，等下次
    setTimeout(fitWidth, 20);
  });
}
