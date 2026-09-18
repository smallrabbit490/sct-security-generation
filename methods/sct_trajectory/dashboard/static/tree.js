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
const COL_X = [40, 340, 640];      // 三列的 x 起点
const V_GAP = 14;                  // 垂直间距
const LEAF_GAP = 6;

/* 把 {cwe: {invariants}} 转成布局用的三层节点表 */
function buildTreeLayout(tree) {
  const cwes = Object.keys(tree || {}).sort();
  const rootNodes = [], invNodes = [], leafNodes = [], edges = [];
  let y = 30;
  cwes.forEach((cwe) => {
    const fam = tree[cwe] || {};
    const invs = fam.invariants || [];
    const blockTop = y;
    let invY = y;
    invs.forEach((inv, i) => {
      const iid = inv.invariant_id || `${cwe}-${i}`;
      invNodes.push({ id: iid, cwe, inv, x: COL_X[1], y: invY, w: NODE_W, h: NODE_H });
      edges.push({ from: `cwe:${cwe}`, to: `inv:${iid}`, kind: "cwe-inv" });
      // 语言叶
      const leaves = Object.keys(inv.language_leaves || {});
      const useLeaves = leaves.length ? leaves : ["(无叶)"];
      let leafY = invY + (NODE_H - (useLeaves.length * (LEAF_H + LEAF_GAP) - LEAF_GAP)) / 2;
      useLeaves.forEach((lang, k) => {
        const lid = `${iid}::${lang}`;
        leafNodes.push({ id: lid, lang, isEmpty: !leaves.length, x: COL_X[2],
                         y: leafY, w: LEAF_W, h: LEAF_H });
        edges.push({ from: `inv:${iid}`, to: `leaf:${lid}`, kind: "inv-leaf" });
        leafY += LEAF_H + LEAF_GAP;
      });
      invY += Math.max(NODE_H, useLeaves.length * (LEAF_H + LEAF_GAP) - LEAF_GAP) + V_GAP;
    });
    const blockBottom = Math.max(invY - V_GAP, blockTop + NODE_H);
    rootNodes.push({ id: `cwe:${cwe}`, cwe,
                     x: COL_X[0], y: (blockTop + blockBottom) / 2 - NODE_H / 2,
                     w: NODE_W * 0.7, h: NODE_H, count: invs.length });
    y = blockBottom + 28;
  });
  return { rootNodes, invNodes, leafNodes, edges, height: y + 20, width: COL_X[2] + LEAF_W + 60 };
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

  function apply() {
    vp.setAttribute("transform", `translate(${state.x} ${state.y}) scale(${state.k})`);
    svgEl.setAttribute("width", width * state.k + pad * 2);
    svgEl.setAttribute("height", height * state.k + pad * 2);
  }
  function fit() {
    const cw = canvas.clientWidth || 800, ch = canvas.clientHeight || 520;
    state.k = Math.min((cw - 20) / width, (ch - 20) / height, 1.2);
    state.k = Math.max(state.k, 0.05);
    state.x = (cw - width * state.k) / 2;
    state.y = 10;
    apply();
  }

  container.querySelectorAll("[data-act]").forEach(btn => {
    btn.onclick = () => {
      const a = btn.dataset.act;
      if (a === "in") state.k = Math.min(state.k * 1.25, 6);
      else if (a === "out") state.k = Math.max(state.k / 1.25, 0.05);
      else if (a === "reset") { state.k = 1; state.x = pad; state.y = pad; }
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
  setTimeout(fit, 30);
}
