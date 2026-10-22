/* 新版沿用旧站五页、SVG树、ABCD分布与代码对照；只读取已落盘产物。 */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const state = {index:null,bundle:null,run:"",round:"",snapshot:"",tab:"overview",stack:[],filter:"fail",poolStatus:"all",query:"",comparison:"repair",trigger:null,busy:false};
const labels = {overview:"概览",phase1:"冷启动",replay:"重放",gate:"候选审计",audit:"收尾审计",active:"活跃",consolidated:"合并",provisional:"候选",revised:"待修订",retired:"退役",unmeasured:"未测量",supported:"支持",rejected:"未通过",admitted:"准入"};
const colors = {A:"#a8d3b8",B:"#ebd49f",C:"#c8d9eb",D:"#e4aaaa",U:"#e6e8eb"};
const metricColors = ["#8a929e","#a9bfd9","#a8d3b8"];
const num = v => typeof v === "number" ? v.toLocaleString("zh-CN",{maximumFractionDigits:2}) : "未采集";
const pct = v => typeof v === "number" ? `${(v*100).toFixed(1)}%` : "未测量";
const deltaPct = v => typeof v === "number" ? `${v>0?"+":""}${(v*100).toFixed(1)} 个百分点` : "未测量";
const roundName = r => r === "all" ? "全部轮次" : r === "unassigned" ? "轮次未记录" : r === "0" ? "冷启动" : r === "final" ? "运行收尾" : `第 ${r} 轮`;
const empty = text => `<div class="empty">${esc(text)}</div>`;
const note = text => `<p class="hint">${esc(text)}</p>`;
const badge = (v,cls="") => `<span class="tag ${esc(cls)}">${esc(labels[v] || v || "未记录")}</span>`;
const panel = (title,body,action="") => `<article class="panel"><div class="panel-title"><h3>${esc(title)}</h3>${action}</div>${body}</article>`;
const table = (heads,rows) => rows.length ? `<div class="table-scroll"><table><thead><tr>${heads.map(h=>`<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(c=>`<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : empty("没有对应记录；缺失记录不计为零或不通过。");
const cards = items => `<div class="cards">${items.map(([k,v,s="",tone=""])=>`<div class="card ${tone}"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div><div class="s">${esc(s)}</div></div>`).join("")}</div>`;
const recorded = (file,value) => state.bundle.artifacts[file] ? num(value) : "未采集";
const taskLink = t => `<button class="entity-link" data-task="${esc(t.key)}">${esc(t.task_id)}</button>`;
const cardLink = id => `<button class="entity-link" data-card="${esc(id)}">${esc(id)}</button>`;
const stageTasks = stage => (state.bundle?.tasks || []).filter(t=>t.stage===stage);
const finalState = t => [...(t.states || [])].reverse().find(s=>["A","B","C","D"].includes(s));
const countStates = ts => ts.reduce((a,t)=>{const s=finalState(t)||"U";a[s]=(a[s]||0)+1;return a;},{});
function stateTag(s) { return `<span class="cell-state ${s==="A"?"status-pass":s==="B"?"tone-amber":s==="C"?"tone-blue":s==="D"?"status-fail":"status-unknown"}">${esc(s || "未测量")}</span>`; }
function abcd(dist) {
  const values = ["A","B","C","D","U"].map(s=>[s,Number(dist?.[s] || 0)]), total=values.reduce((n,v)=>n+v[1],0);
  if(!total) return empty("尚无已记录的四态测量。");
  return `<div class="bar" aria-label="四态分布，共${total}条">${values.filter(v=>v[1]).map(([s,n])=>`<span class="seg-${s}" style="width:${100*n/total}%" title="${s}：${n}">${s} ${n}</span>`).join("")}</div><div class="legend">${[["A","功能与安全均通过"],["B","仅功能通过"],["C","仅安全通过"],["D","均不通过"],["U","未测量"]].filter(([s])=>s!=="U"||dist?.U).map(([s,text])=>`<span class="legend-item"><i class="dot" style="background:${colors[s]}"></i>${s} ${text}</span>`).join("")}</div>`;
}
function rates(ts,version=null) {
  const ss=ts.map(t=>version===null?finalState(t):t.states?.[version]).filter(s=>["A","B","C","D"].includes(s));
  return {n:ss.length,values:["AB","AC","A"].map(chars=>ss.length?ss.filter(s=>chars.includes(s)).length/ss.length:null)};
}
function groupedBars(groups) {
  if(!groups.length || !groups.some(g=>g.values.some(v=>typeof v==="number"))) return empty("尚无可绘制的通过率；需要已测量样本和分母。");
  const width=660,rowH=92,height=groups.length*rowH+40,x0=150,plotW=430;
  let svg=`<div class="chart-scroll"><svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="功能、安全、联合通过率对比">`;
  [0,25,50,75,100].forEach(p=>{const x=x0+plotW*p/100;svg+=`<line class="gridline" x1="${x}" x2="${x}" y1="15" y2="${height-30}"/><text x="${x}" y="${height-8}" text-anchor="middle" font-size="11">${p}%</text>`;});
  groups.forEach((g,i)=>{const y=22+i*rowH;svg+=`<text x="0" y="${y+18}" font-size="13">${esc(g.name)}</text><text x="0" y="${y+38}" font-size="11">n=${num(g.n)}</text>`;g.values.forEach((v,j)=>{const yy=y+j*22; if(typeof v==="number") svg+=`<rect x="${x0}" y="${yy}" width="${Math.max(0,v)*plotW}" height="14" fill="${metricColors[j]}"/><text x="${x0+v*plotW+6}" y="${yy+12}" font-size="11">${pct(v)}</text>`;else svg+=`<text x="${x0}" y="${yy+12}" font-size="11">未测量</text>`;});});
  return svg+`</svg></div><div class="legend">${["功能通过率","安全通过率","联合通过率"].map((t,i)=>`<span class="legend-item"><i class="dot" style="background:${metricColors[i]}"></i>${t}</span>`).join("")}</div>`;
}
function roundRates(row) {
  const p=row.pass_rates || {};
  return {n:p.samples ?? p.total ?? p.joint?.total,values:["functional","security","joint"].map(k=>p[k]?.rate ?? p[`${k}_pass_rate`] ?? null)};
}
function lineChart(rows,series) {
  if(!rows.length) return empty("尚无逐轮数据。");
  const w=660,h=244,left=55,top=18,pw=540,ph=175;
  const x=i=>left+(rows.length===1?pw/2:i*pw/(rows.length-1));
  let svg=`<div class="chart-scroll"><svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="逐轮测量趋势">`;
  [0,.25,.5,.75,1].forEach(v=>{const y=top+ph*(1-v);svg+=`<line class="gridline" x1="${left}" x2="${left+pw}" y1="${y}" y2="${y}"/><text x="${left-8}" y="${y+4}" text-anchor="end" font-size="11">${v*100}%</text>`;});
  rows.forEach((r,i)=>svg+=`<text x="${x(i)}" y="${h-25}" text-anchor="middle" font-size="12">${esc(roundName(String(r.round)))}</text><text x="${x(i)}" y="${h-8}" text-anchor="middle" font-size="10">n=${num(roundRates(r).n)}</text>`);
  series.forEach((name,j)=>{let segment=[];const flush=()=>{if(segment.length)svg+=`<polyline points="${segment.join(" ")}" fill="none" stroke="${metricColors[j]}" stroke-width="2.5"/>`;segment=[];};rows.forEach((r,i)=>{const v=roundRates(r).values[j];if(typeof v!=="number"){flush();return;}const y=top+ph*(1-v);segment.push(`${x(i)},${y}`);svg+=`<circle cx="${x(i)}" cy="${y}" r="4" fill="${metricColors[j]}"><title>${esc(name)} ${pct(v)}</title></circle>`;});flush();});
  return svg+`</svg></div><div class="legend">${series.map((s,j)=>`<span class="legend-item"><i class="dot" style="background:${metricColors[j]}"></i>${esc(s)}</span>`).join("")}</div>`;
}
function costView(cost) {
  if(!cost?.total) return empty("未采集usage与费用。补充 cost.json 后刷新；不从任务量推算费用。");
  const rows=Object.entries(cost.stages || {}),max=Math.max(1,...rows.map(([,r])=>(r.prompt_tokens||0)+(r.completion_tokens||0)));
  const bars=rows.map(([name,r])=>`<div style="margin:14px 0"><div class="section-actions"><b>${esc(name)}</b><span class="small">${num(r.calls)} 次调用 · ${num((r.prompt_tokens||0)+(r.completion_tokens||0))} tokens</span></div><div class="bar" style="height:18px;margin-top:7px"><span style="width:${100*(r.prompt_tokens||0)/max}%;background:#aab8c9"></span><span style="width:${100*(r.completion_tokens||0)/max}%;background:#d7dde4"></span></div></div>`).join("");
  const total=cost.total,money=total.cost_ca ?? total.cost ?? total.cost_usd;
  return bars+`<div class="legend"><span class="legend-item"><i class="dot" style="background:#aab8c9"></i>输入 tokens</span><span class="legend-item"><i class="dot" style="background:#d7dde4"></i>输出 tokens</span></div>`+note(`总调用 ${num(total.calls)} 次；usage缺失 ${num(total.usage_missing)} 次；费用 ${typeof money==="number"?num(money)+" "+(cost.currency||"币种未记录"):"未采集"}。各阶段用量按统一刻度显示。`);
}
function treeFromCards(cs) {const tree={};cs.forEach(c=>(tree[String(c.cwe||"?")] ??= {invariants:[]}).invariants.push(c));return tree;}
function treeView(tree) {
  return Object.entries(tree).map(([cwe,f])=>`<h4>CWE-${esc(cwe)}</h4>${(f.invariants||[]).map(c=>`<div class="tree-card"><div class="card-meta">${cardLink(c.invariant_id)} ${badge(c.status,c.status)}</div><b>${esc(c.high_level_invariant)}</b><p>${esc(c.positive_principle || c.negative_guardrail || c.applicability)}</p></div>`).join("")}`).join("");
}
function fileTable(artifacts) {return table(["产物","内容","状态"],Object.entries(state.index.files).map(([name,purpose])=>[`<code>${esc(name)}</code>`,esc(purpose),badge(artifacts?.[name]?(state.bundle.demo?"示例输入":"已存在"):"缺失")]));}
function renderEmpty() {
  $("#emptyState").innerHTML=`<div class="empty-state">${panel("尚无真实运行可读取",`<p>旧站与新版读取同一批已落盘产物。将项目已有运行目录放到下方位置，点击“刷新”即可载入。</p><div class="path">${esc(state.index.root)}/&lt;run_name&gt;/</div><p>先放入 <code>pools.json</code>、<code>run_metadata.json</code> 与 <code>status.json</code>；各阶段按下表补充。历史运行也可使用 <code>progress.log</code> 被发现。缺少哪一阶段，只显示该阶段缺失。</p><div class="section-actions"><button data-demo>查看示例运行</button><span class="small">合成数据，仅演示交互</span></div>`)}${panel("各页需要哪些现有文件",fileTable({}))}</div>`;
}
function renderOverview() {
  const b=state.bundle,o=b.overview,pc=o.pools_counts||{},has=b.artifacts["pools.json"];
  $("#tab-overview").innerHTML=cards([["任务清单",has?num(o.total_tasks):"未采集","按三池清单计数"],["Source",has?num(pc.source):"未采集","冷启动池"],["Replay",has?num(pc.replay):"未采集","回放池"],["Audit",has?num(pc.audit):"未采集","开发侧审计池"],["经验快照",b.snapshot||"未关联","随顶部轮次切换"]])+panel("执行位置",`<div class="stage-grid">${[["Phase 1 · 冷启动",`${recorded("phase1_results.jsonl",o.phase1_done)} 条轨迹`,"只执行一次",0],["Phase 2 · 重放进化",`${num(b.phase2.rounds?.length)} 轮记录`,"每轮先重放，再进入门控",1],["Phase 3 · 门控与审计",`${b.phase3.audit_entries?.length||0} 条当前范围记录`,"门控后返回下一轮重放",2]].map(([title,value,help,i])=>`<div><div class="stage-name">${title}</div><div>${value}</div><div class="progress"><span style="width:${[b.phase1.total,b.phase2.rounds?.length,b.phase3.audit_entries?.length][i]?100:0}%"></span></div><p class="small">${help}</p><button class="text-button" data-tab-jump="phase${i+1}">查看记录 →</button></div>`).join("")}</div>`)+`<div class="row wide">${panel("模型调用与Token用量",costView(o.cost))}${panel("运行信息",table(["项目","当前值"],[["运行",esc(b.run_name)],["模型",esc(b.model)],["语言",esc(b.language)],["状态",esc(o.status?.detail||o.status?.status||"未记录")],["评测范围",esc(b.final_scope)]]))}</div>`+panel("产物完整性",fileTable(b.artifacts));
}
function taskTable(ts,repair=true) {
  if(!repair)return table(["任务","CWE","最终状态","测量证据","操作"],ts.map(t=>[taskLink(t),`CWE-${esc(t.cwe)}`,stateTag(finalState(t)),evidenceMarkup(t.evidence.at(-1),finalState(t)),`<button data-task="${esc(t.key)}">查看保存的代码</button>`]));
  return table(["任务","CWE","首次状态",repair?"修复后状态":"最终状态","操作"],ts.map(t=>[taskLink(t),`CWE-${esc(t.cwe)}`,stateTag(t.states?.[0]),stateTag(finalState(t)),`<button data-task="${esc(t.key)}">${repair?"同题代码对照":"查看轨迹"}</button>`]));
}
function renderPhase1() {
  const b=state.bundle,p=b.phase1,ts=stageTasks("phase1"),first=rates(ts,0),after=rates(ts),failed=ts.filter(t=>finalState(t)&&finalState(t)!=="A");
  $("#tab-phase1").innerHTML=note("固定范围：冷启动全量来源任务，不随顶部轮次改变。四态以测量记录为准。")+cards([["已记录任务",recorded("phase1_results.jsonl",ts.length),"phase1_results.jsonl"],["首次联合通过",pct(first.values[2]),`n=${first.n}`,"pass"],["修复后联合通过",pct(after.values[2]),`n=${after.n}`,"pass"],["修复后仍未达 A",recorded("phase1_results.jsonl",failed.length),"点击任务查看具体证据","fail"]])+`<div class="row">${panel("同题首次 / 修复后通过率",groupedBars([{name:"首次生成",...first},{name:"修复后",...after}]))}${panel("四态分布",`<h4>首次生成</h4>${abcd(p.abcd_first||countStates(ts.map(t=>({...t,states:[t.states?.[0]]}))))}<h4>修复后</h4>${abcd(p.abcd_after||countStates(ts))}`)}</div>`+panel("冷启动经验树",`<div id="phase1Tree"></div>`+note("此处是冷启动快照。候选、活跃等为生命周期状态，不能直接解释为独立评测有效。"))+panel("逐题修复记录",`<div class="filters"><label>任务范围 <select id="phase1Filter"><option value="fail" ${state.filter==="fail"?"selected":""}>仍未达 A</option><option value="all" ${state.filter==="all"?"selected":""}>全部任务</option><option value="pass" ${state.filter==="pass"?"selected":""}>最终 A</option></select></label><span class="small">点击任务打开详情，关闭后保留列表与位置</span></div><div id="phase1Rows"></div>`);
  const tree=p.tree_snapshot?.tree || (p.tree_snapshot && !p.tree_snapshot.label?p.tree_snapshot:null) || treeFromCards(p.phase1_pool||[]);
  mountTree($("#phase1Tree"),Object.keys(tree||{}).length?tree:treeFromCards(p.phase1_pool||[]),{onSelect:openCard});
  renderPhase1Rows();$("#phase1Filter").onchange=e=>{state.filter=e.target.value;renderPhase1Rows();};
}
function renderPhase1Rows() {const ts=stageTasks("phase1").filter(t=>state.filter==="all"||(state.filter==="pass"?finalState(t)==="A":finalState(t)&&finalState(t)!=="A"));$("#phase1Rows").innerHTML=taskTable(ts);}
function renderPhase2() {
  const b=state.bundle,p=b.phase2,ts=stageTasks("replay"),details=p.rounds_detail||[];
  const current=rates(ts),known=ts.filter(t=>t.recalled_ids.length).length;
  $("#tab-phase2").innerHTML=cards([["当前范围任务轨迹",recorded("trajectories.jsonl",ts.length),roundName(b.round)],["联合通过率",pct(current.values[2]),`测量分母 n=${current.n}`],["有召回记录的轨迹",recorded("trajectories.jsonl",known),"记录中含经验ID；不等于采纳"],["可查轮次",recorded("rounds.jsonl",p.rounds?.length),"P2 → P3 → 下一轮"]])+`<div class="row">${panel("逐轮通过率趋势 · 全运行",lineChart(p.rounds||[],["功能通过率","安全通过率","联合通过率"])+note("各轮任务集合与样本量可能不同，折线差异不能直接当作同题净提升。"))}${panel("当前范围四态分布",abcd(p.abcd||countStates(ts))+groupedBars([{name:roundName(b.round),...current}]))}</div>`+panel("本轮调度与经验召回",details.length?details.map(r=>`<details class="record" open><summary>${esc(roundName(String(r.round)))} · ${num(Array.isArray(r.selected)?r.selected.length:r.selected)} 个调度任务</summary><p>${esc(r.schedule || "未记录调度原因")}</p>${table(["强制回放","召回命中","零命中补偿","经验池"],[[Array.isArray(r.forced_replay)?r.forced_replay.map(esc).join("、")||"无":num(r.forced_replay),num(r.retrieval_hit),num(r.zero_hit_compensations),num(r.pool_size)]])}</details>`).join(""):empty("没有当前轮次的调度记录；补充 rounds.jsonl 后刷新。"))+panel("回放任务 → 代码 / 经验",ts.length?`<div class="task-grid">${ts.map(t=>`<button class="task-chip ${finalState(t)||""}" data-task="${esc(t.key)}"><b>${esc(t.task_id)}</b><span class="small">${esc(roundName(t.round))} · ${esc(finalState(t)||"未测量")}</span></button>`).join("")}</div>`:empty("当前范围无回放轨迹；补充 trajectories.jsonl 或切换轮次。"))+panel("各轮记录",table(["轮次","测量任务","联合通过率","经验节点","定位"],(p.rounds||[]).map(r=>{const m=roundRates(r);return[esc(roundName(String(r.round))),num(m.n),pct(m.values[2]),num(r.tree_nodes),`<button data-global-round="${esc(r.round)}">定位此轮</button>`];})))+note("门控与经验库共用顶部轮次 / 快照。进入 Phase 3 后仍保留当前轮次。");
}
function armValues(arm) {return {n:arm.measured,values:["functional_pass","security_pass","joint_pass"].map(k=>arm.measured_rates?.[k] ?? (arm.measured?arm[k]/arm.measured:null))};}
function renderPhase3() {
  const b=state.bundle,p=b.phase3,entries=p.audit_entries||[],dc=p.decision_counts||{},fe=p.final_eval_summary||{},arms=fe.arms||{},audit=stageTasks("audit");
  const gateRows=entries.map(e=>[cardLink(e.candidate_id||"未记录ID"),esc(roundName(String(e.round??"unassigned"))),num(e.audit_task_count),`${pct(e.baseline_pass)} → ${pct(e.with_candidate_pass)}`,typeof e.delta_joint_pass==="number"?`<span class="cell-state ${e.delta_joint_pass>0?"status-pass":e.delta_joint_pass<0?"status-fail":"status-unknown"}">${deltaPct(e.delta_joint_pass)}</span>`:"未测量",badge(e.decision,e.decision),`<div class="table-links">${(e.selected_tasks||[]).map(t=>{const match=b.tasks.find(x=>x.stage==="gate"&&x.round===String(e.round??"unassigned")&&x.candidate_id===e.candidate_id&&x.task_id===String(t.task_id));return match?taskLink(match):esc(t.task_id);}).join("")}</div>`]);
  const byCwe={};audit.forEach(t=>{(byCwe[t.cwe]??=[]).push(t);});
  $("#tab-phase3").innerHTML=cards([["候选审计记录",recorded("audit_detail.jsonl",entries.length),roundName(b.round)],["支持",recorded("audit_detail.jsonl",dc.supported||dc.admitted||0),"当前范围门控决定"],["待修订 / 未通过",recorded("audit_detail.jsonl",(dc.revised||0)+(dc.rejected||0)),"不等于系统运行失败"],["未测量",recorded("audit_detail.jsonl",dc.unmeasured||0),"没有测量证据"]])+(b.unassigned_audits?`<div class="notice">有 ${b.unassigned_audits} 条门控记录未保存轮次。<button class="text-button" data-global-round="unassigned">查看未归属记录</button></div>`:"")+panel("候选经验门控 · 当前轮次",table(["候选经验","轮次","审计任务数","基线 → 加候选 联合通过率","Δ 联合通过率","决定","进入审计任务"],gateRows)+note("点击候选经验查看正文、选题原因与门控依据；点击任务查看该次门控实际保存的代码和测量。"))+panel("运行收尾审计 · 全运行",`<div class="notice">${esc(b.final_scope)}。Audit 池参与开发选择，不能作为独立 Base / Plus 泛化结论。</div>${groupedBars(Object.entries(arms).map(([key,arm])=>({name:{baseline:"无经验基线",memory:"冻结经验",filtered:"筛选后经验"}[key]||key,...armValues(arm)})))}${Object.entries(arms).map(([key,arm])=>`<h4>${esc({baseline:"无经验基线",memory:"冻结经验",filtered:"筛选后经验"}[key]||key)} · n=${num(arm.measured)}</h4>${abcd(arm.states)}`).join("")}${!Object.keys(arms).length?note("需要 final_eval_summary.json 的分臂测量字段。没有分臂结果时不把单臂结果画成对照。"):""}`)+`<div class="row">${panel("收尾逐题记录 · 按CWE",table(["CWE","轨迹数","测量数","功能","安全","联合"],Object.entries(byCwe).map(([c,ts])=>{const r=rates(ts);return[`CWE-${esc(c)}`,num(ts.length),num(r.n),...r.values.map(pct)];}))+note("此表按已保存的逐题轨迹汇总；如含多臂，同题会有多条轨迹。"))}${panel("冻结经验与边界",`<p>冻结经验数：<b>${recorded("frozen/m_star.jsonl",p.frozen_size)}</b></p><p>快照：${esc(b.snapshot||"未关联")}</p><button data-tab-jump="pool">查看经验库</button>`+note("生命周期、召回和门控决定分别展示；不互相代替。独立冻结评测需使用独立评测产物。"))}</div>`+panel("收尾审计逐题证据",taskTable(audit,false));
}
function renderPool() {
  const b=state.bundle,cs=b.cards||[],counts={},has=!!b.snapshot||(b.round==="all"&&(b.artifacts["experience_pool.jsonl"]||b.artifacts["frozen/m_star.jsonl"]));cs.forEach(c=>counts[c.status||"unmeasured"]=(counts[c.status||"unmeasured"]||0)+1);
  $("#tab-pool").innerHTML=cards([["当前快照经验",(has?num(cs.length):"未采集"),b.snapshot||"未关联快照"],["活跃",(has?num(counts.active||0):"未采集"),"生命周期状态"],["合并",(has?num(counts.consolidated||0):"未采集"),"生命周期状态"],["候选 / 待修订",(has?num((counts.provisional||0)+(counts.revised||0)):"未采集"),"需要进一步检验"]])+(!b.snapshot?`<div class="notice">当前轮次没有关联历史快照。${b.round!=="all"?'<button class="text-button" data-global-round="all">切到全部轮次查看当前经验池</button>':"当前池正文不代表某一轮的历史正文。"}</div>`:"")+panel("经验树 / 列表",`<div class="filters"><label>搜索经验 <input type="search" id="poolSearch" value="${esc(state.query)}" placeholder="ID、CWE或正文" aria-label="搜索经验"></label><label>生命周期 <select id="poolStatus"><option value="all">全部状态</option>${Object.keys(counts).map(s=>`<option value="${esc(s)}" ${state.poolStatus===s?"selected":""}>${esc(labels[s]||s)} (${counts[s]})</option>`).join("")}</select></label><span id="poolCount" class="small"></span></div><div class="legend"><span class="legend-item"><i class="dot" style="background:#e7eff7"></i>活跃 / 合并</span><span class="legend-item"><i class="dot" style="background:#f6edd9"></i>待修订</span><span class="legend-item"><i class="dot" style="background:#f2f3f5"></i>候选 / 未测量</span><span class="legend-item"><i class="dot" style="background:#f8e7e7"></i>退役</span></div><div id="memoryTree"></div>`+note("快照正文用于检查结构与来源，不等于当时实际注入的文本；召回记录在任务详情中单独展示。"));
  const update=()=>{const q=state.query.toLowerCase();const selected=cs.filter(c=>(state.poolStatus==="all"||c.status===state.poolStatus)&&(!q||JSON.stringify(c).toLowerCase().includes(q)));$("#poolCount").textContent=`显示 ${selected.length} / ${cs.length} 条`;if(!selected.length&&cs.length){$("#memoryTree").innerHTML=empty("没有匹配的经验；当前快照有数据。")+'<button id="clearMemoryFilter">清空筛选</button>';$("#clearMemoryFilter").onclick=()=>{state.query="";state.poolStatus="all";$("#poolSearch").value="";$("#poolStatus").value="all";update();};}else mountTree($("#memoryTree"),treeFromCards(selected),{onSelect:openCard});};
  $("#poolSearch").oninput=e=>{state.query=e.target.value;update();};$("#poolStatus").onchange=e=>{state.poolStatus=e.target.value;update();};update();
}
function chooseTab(tab) {
  if(!["overview","phase1","phase2","phase3","pool"].includes(tab))tab="overview";state.tab=tab;
  document.querySelectorAll(".tab").forEach(el=>{const active=el.dataset.tab===tab;el.classList.toggle("active",active);if(active)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  document.querySelectorAll(".tabpane").forEach(el=>el.classList.toggle("active",el.id===`tab-${tab}`));saveUrl();window.dispatchEvent(new Event("dsh-tab-shown"));
}
function saveUrl() {const p=new URLSearchParams();if(state.run)p.set("run",state.run);if(state.round)p.set("round",state.round);if(state.snapshot)p.set("snapshot",state.snapshot);p.set("tab",state.tab);history.replaceState(null,"",`?${p}`);}
function render() {
  const b=state.bundle;$("#emptyState").hidden=!!b;$("#demoNotice").hidden=!b?.demo;$("#modeLabel").textContent=b?.demo?"合成示例":"真实运行";
  document.querySelectorAll("[data-export]").forEach(el=>el.disabled=!b);
  $("#roundSelect").disabled=!b;$("#snapshotSelect").disabled=!b?.snapshots.length;
  if(!b){$("#roundSelect").innerHTML='<option>未选择轮次</option>';$("#snapshotSelect").innerHTML='<option>未关联快照</option>';$("#contextLine").textContent="读取已有产物 · 不运行模型或代码";$("#statusBadge").textContent="未选择";document.querySelectorAll(".tabpane").forEach(p=>p.innerHTML="");renderEmpty();chooseTab(state.tab);return;}
  $("#roundSelect").innerHTML=["all",...b.round_options].map(r=>`<option value="${r}" ${b.round===r?"selected":""}>${esc(roundName(r))}</option>`).join("");
  $("#snapshotSelect").innerHTML=b.snapshots.length?b.snapshots.map(s=>`<option value="${esc(s.label)}" ${b.snapshot===s.label?"selected":""}>${esc(s.label)}</option>`).join(""):'<option>该轮快照缺失</option>';
  const rs=b.overview.status?.status||"unknown";$("#statusBadge").className=`badge ${rs}`;$("#statusBadge").textContent={running:"运行中",completed:"流程已结束",failed:"运行失败",stale:"心跳已过期",unknown:"状态未记录"}[rs]||rs;
  $("#contextLine").innerHTML=`<span>${esc(b.demo?"示例运行":b.run_name)} / ${esc(roundName(b.round))} / 快照 ${esc(b.snapshot||"未关联")}</span><span>模型 ${esc(b.model)} · ${esc(b.language)} · 只读产物</span>`;
  renderOverview();renderPhase1();renderPhase2();renderPhase3();renderPool();chooseTab(state.tab);
}
async function api(url) {const r=await fetch(url,{cache:"no-store"});const data=await r.json();if(!r.ok)throw new Error(data.error||`HTTP ${r.status}`);return data;}
function showError(error) {$("#loadErrors").hidden=false;$("#loadErrors").textContent=`读取失败：${error.message}。请检查运行目录与JSON格式，再点击刷新。`;}
async function load(refreshIndex=false,resetScroll=false) {
  if(state.busy)return;state.busy=true;$("#refreshBtn").disabled=true;const scroll=resetScroll?0:window.scrollY;
  ["#runSelect","#roundSelect","#snapshotSelect"].forEach(s=>$(s).disabled=true);
  document.querySelector("main").setAttribute("aria-busy","true");
  try {
    if(refreshIndex || !state.index){state.index=await api("/api/index");const runs=state.index.runs;$("#runSelect").innerHTML=`<option value="">${runs.length?"选择真实运行":"暂无真实运行"}</option>${runs.map(r=>`<option value="${esc(r.run_name)}">${esc(r.run_name)}</option>`).join("")}<optgroup label="仅演示交互"><option value="__demo__">示例运行（合成数据）</option></optgroup>`;}
    if(state.run){const q=new URLSearchParams({run:state.run,round:state.round,snapshot:state.snapshot});state.bundle=await api(`/api/workbench?${q}`);state.round=state.bundle.round;state.snapshot=state.bundle.snapshot||"";}else state.bundle=null;
    $("#runSelect").value=state.run;$("#loadErrors").hidden=true;render();$("#lastUpdated").textContent=`读取 ${new Date().toLocaleTimeString("zh-CN",{hour12:false})}`;window.scrollTo(0,scroll);
  }catch(error){showError(error);}finally{state.busy=false;$("#refreshBtn").disabled=false;$("#runSelect").disabled=false;$("#roundSelect").disabled=!state.bundle;$("#snapshotSelect").disabled=!state.bundle?.snapshots.length;document.querySelector("main").setAttribute("aria-busy","false");}
}
function codeBlock(code,other,changeClass="diff-add") {
  if(typeof code!=="string"||!code.length)return empty("此记录未保存代码。缺失不补用其他阶段的代码。");
  const otherLines=new Set(typeof other==="string"?other.split("\n"):[]);
  return `<pre><code>${code.split("\n").map(line=>other===undefined?esc(line):`<span${otherLines.has(line)?"":` class="${changeClass}"`}>${esc(line)||" "}</span>`).join("\n")}</code></pre>`;
}
function evidenceMarkup(e={},s) {
  const status=(key,chars)=>{const v=e[key],explicit=typeof v==="object"?v?.status:v;if(explicit==="pass"||explicit===true)return ["通过","status-pass"];if(explicit==="fail"||explicit===false)return["不通过","status-fail"];if(chars&&s&&"ABCD".includes(s))return[chars.includes(s)?"通过（状态）":"不通过（状态）",chars.includes(s)?"status-pass":"status-fail"];return["未测量","status-unknown"];};
  return `<div class="evidence-row">${[["功能","functional","AB"],["安全","security","AC"],["语法/编译","syntax_or_compile",null]].map(([label,key,chars])=>{const [v,cls]=status(key,chars);return `<span class="cell-state ${cls}">${label} ${v}</span>`;}).join("")}</div>`;
}
function relatedLinks(t) {
  return `<div class="dialog-section"><h3>经验召回与采纳</h3><p>召回：${t.recalled_ids.length?t.recalled_ids.map(cardLink).join("、"):"未保存经验ID召回记录"}</p><p>采纳：${Array.isArray(t.adopted_ids)?t.adopted_ids.length?t.adopted_ids.map(cardLink).join("、"):"记录为未采纳":"未采集；不能由召回推断采纳"}</p>${t.candidate_id?`<p>本次审计候选：${cardLink(t.candidate_id)}</p>`:""}<p class="small">查看正文时使用当前选中快照；历史注入文本若未保存，将明确显示缺失。</p></div>`;
}
function taskDetail(t) {
  let compare="";
  if(state.comparison==="reference") {
    const ref=stageTasks("phase1").find(x=>x.task_id!==t.task_id&&x.cwe===t.cwe&&finalState(x)==="A");
    compare=`<div class="notice">同CWE成功题是跨任务参考，不能作为当前任务“修复前 / 后”的效果对照。</div>`+(ref?`<div class="compare"><div class="side"><h3>当前任务 ${esc(t.task_id)}</h3>${codeBlock(t.codes.at(-1))}</div><div class="side"><h3>同CWE另一任务 ${taskLink(ref)}</h3>${codeBlock(ref.codes.at(-1))}</div></div>`:empty("当前记录中没有同CWE的其他成功任务。"));
  } else if(t.branches.length) {
    compare=`<div class="notice">这是同题并行分支，彼此不是修复的先后步骤。选中分支属于训练侧选择，不等于部署时单次生成的通过率。</div><div class="compare">${t.branches.map((branch,i)=>`<div class="side"><h3>分支 ${esc(branch.branch_id||i+1)} ${i===t.branch_selection.index?"· 训练选中":""}</h3>${evidenceMarkup(branch.evidence,branch.state)}${codeBlock(branch.code)}</div>`).join("")}</div>`;
  } else if(t.stage==="audit") {
    compare=`<div class="side"><h3>收尾审计保存的最终代码</h3>${evidenceMarkup(t.evidence.at(-1),finalState(t))}${codeBlock(t.codes.at(-1))}</div>`;
  } else {
    const gate=t.stage==="gate",last=t.codes.length>1?t.codes.length-1:1;
    compare=`<div class="compare"><div class="side ${t.states[0]==="A"?"ok":t.states[0]?"fail":""}"><h3>${gate?"无候选基线":"首次生成 c₀"}</h3>${evidenceMarkup(t.evidence[0],t.states[0])}${codeBlock(t.codes[0],t.codes[last],"diff-del")}</div><div class="side ${t.states[last]==="A"?"ok":t.states[last]?"fail":""}"><h3>${gate?"加入候选经验":"最后一次修复 c"+last}</h3>${evidenceMarkup(t.evidence[last],t.states[last])}${codeBlock(t.codes[last],t.codes[0])}</div></div>`+note("左侧红底为移除行，右侧绿底为新增行；通过 / 不通过以保存的测量记录为准。");
  }
  return `<h2 id="detailTitle">${esc(t.task_id)} · ${esc(labels[t.stage]||t.stage)}</h2><div class="detail-meta"><span>CWE-${esc(t.cwe)}</span><span>${esc(roundName(t.round))}</span>${stateTag(finalState(t))}</div>${t.description?`<p>${esc(t.description)}</p>`:""}<div class="segmented"><button data-compare="repair" class="${state.comparison==="repair"?"active":""}">${t.stage==="gate"?"同次门控对照":t.stage==="audit"?"最终代码与测量":t.branches.length?"同题并行分支":"同题修复前后"}</button><button data-compare="reference" class="${state.comparison==="reference"?"active":""}">同CWE跨任务参考</button></div>${compare}${relatedLinks(t)}<div class="dialog-section"><h3>已保存反馈 / 上下文</h3>${t.feedback.length?`<pre>${esc(t.feedback.map(x=>typeof x==="string"?x:JSON.stringify(x,null,2)).join("\n"))}</pre>`:note("未保存公开反馈；不使用隐藏测试断言补充生成上下文。")}${t.context.length?`<details><summary>展开生成上下文记录</summary><pre>${esc(JSON.stringify(t.context,null,2))}</pre></details>`:""}</div>`;
}
function cardDetail(id) {
  const b=state.bundle,c=b.cards.find(c=>c.invariant_id===id),gates=(b.phase3.audit_entries||[]).filter(g=>g.candidate_id===id),uses=b.tasks.filter(t=>t.recalled_ids.includes(id)||(t.adopted_ids||[]).includes(id));
  const source=c?.source || {},sourceTask=b.tasks.find(t=>t.task_id===String(source.task_id)&&t.stage===(source.stage==="phase1"?"phase1":"replay"));
  return `<h2 id="detailTitle">经验 ${esc(id)}</h2><div class="detail-meta"><span>快照 ${esc(b.snapshot||"未关联")}</span>${c?badge(c.status,c.status):badge("正文缺失")}${c?`<span>CWE-${esc(c.cwe)}</span>`:""}</div>${c?`<div class="dialog-section"><h3>${esc(c.high_level_invariant||"未保存高层不变量")}</h3>${[["适用条件",c.applicability],["正向原则",c.positive_principle],["负向边界",c.negative_guardrail]].map(([k,v])=>`<h4>${k}</h4><p>${esc(v||"未保存")}</p>`).join("")}<h4>语言叶</h4><pre>${esc(JSON.stringify(c.language_leaves||{},null,2))}</pre></div>`:`<div class="notice">当前选中快照没有此ID的正文。保留关联记录，不用最新经验正文代替历史正文。</div>`}<div class="dialog-section"><h3>来源任务</h3><p>${sourceTask?taskLink(sourceTask):esc(source.task_id||"未保存来源任务ID")} · ${esc(source.stage||"阶段未记录")}</p><p class="small">当前快照正文不等于当时实际注入原文；生命周期不等于对模型效果的独立证明。</p></div><div class="dialog-section"><h3>当前轮次门控依据</h3>${gates.length?gates.map(g=>`<details class="record" open><summary>${esc(roundName(String(g.round??"unassigned")))} · ${esc(labels[g.decision]||g.decision)}</summary><p>选择原因：${esc(g.selector_reason||"未保存")}</p><p>审计任务：${num(g.audit_task_count)}；联合通过 ${pct(g.baseline_pass)} → ${pct(g.with_candidate_pass)}；Δ ${deltaPct(g.delta_joint_pass)}</p><p>${esc((g.reasons||[]).join("；")||"未保存决定原因")}</p>${table(["召回探针","功能回归数","安全回归数","回归缺测数"],[[typeof g.gate1_retrieved==="boolean"?(g.gate1_retrieved?"已召回":"未召回"):"未采集",num(g.functional_regressions),num(g.security_regressions),num(g.hpass_missing)]])}<div class="table-links">${b.tasks.filter(t=>t.stage==="gate"&&t.candidate_id===id&&t.round===String(g.round??"unassigned")).map(taskLink).join(" ")}</div></details>`).join(""):empty("当前轮次没有此经验的门控记录。可切换顶部轮次后查看。")}</div><div class="dialog-section"><h3>任务关联记录</h3>${table(["任务","阶段","轮次","关联"],uses.map(t=>[taskLink(t),esc(labels[t.stage]||t.stage),esc(roundName(t.round)),(t.adopted_ids||[]).includes(id)?"记录为采纳":"仅召回；采纳未知"]))}</div>`;
}
function renderDetail() {
  const current=state.stack.at(-1);if(!current)return;$("#detailBack").hidden=state.stack.length<2;$("#detailTrail").textContent=state.stack.map(s=>s.type==="card"?`经验 ${s.key}`:state.bundle.tasks.find(t=>t.key===s.key)?.task_id||"任务").join(" → ");
  if(current.type==="task"){const t=state.bundle.tasks.find(t=>t.key===current.key);$("#detailContent").innerHTML=t?taskDetail(t):empty("此范围内没有该任务记录。");}else $("#detailContent").innerHTML=cardDetail(current.key);
  $("#detailDialog").scrollTop=0;
}
function openDetail(type,key) {if(!$("#detailDialog").open){state.trigger=document.activeElement;state.stack=[];state.comparison="repair";}state.stack.push({type,key,comparison:state.comparison});state.comparison="repair";renderDetail();if(!$("#detailDialog").open)$("#detailDialog").showModal();}
function openTask(key) {openDetail("task",key);}
function openCard(id) {openDetail("card",id);}
function closeDetail() {$("#detailDialog").close();state.stack=[];state.trigger?.focus({preventScroll:true});}
async function changeRound(round) {if($("#detailDialog").open)closeDetail();state.round=round;state.snapshot="";await load();}
function exportData(kind) {
  const b=state.bundle;if(!b)return;const scope={run:b.run_name,round:b.round,snapshot:b.snapshot,demo:b.demo};
  const data={phase1:{...scope,scope:"冷启动全量",data:b.phase1,tasks:stageTasks("phase1")},phase2:{...scope,data:b.phase2,tasks:stageTasks("replay")},phase3:{...scope,final_scope:b.final_scope,data:b.phase3,tasks:b.tasks.filter(t=>["gate","audit"].includes(t.stage))},pool:{...scope,pools:b.pools,cards:b.cards,tree:b.tree}}[kind];
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json;charset=utf-8"})),link=document.createElement("a");link.href=url;link.download=`${b.demo?"DEMO":b.run_name}_${kind}_${b.round}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
document.addEventListener("click",e=>{
  const task=e.target.closest("[data-task]"),card=e.target.closest("[data-card]");
  // 图形树自己处理节点事件；其他任务/经验入口共用详情弹层。
  if(task)return openTask(task.dataset.task);if(card&&!card.closest("#phase1Tree,#memoryTree"))return openCard(card.dataset.card);
  const tab=e.target.closest("[data-tab],[data-tab-jump]");if(tab)return chooseTab(tab.dataset.tab||tab.dataset.tabJump);
  const round=e.target.closest("[data-global-round]");if(round)return changeRound(round.dataset.globalRound);
  if(e.target.closest("[data-demo]")){state.run="__demo__";state.round="";state.snapshot="";return load(false,true);}
  const compare=e.target.closest("[data-compare]");if(compare){state.comparison=compare.dataset.compare;state.stack.at(-1).comparison=state.comparison;return renderDetail();}
  const exp=e.target.closest("[data-export]");if(exp)exportData(exp.dataset.export);
});
$("#detailClose").onclick=closeDetail;$("#detailDialog").addEventListener("cancel",()=>{state.stack=[];});
$("#detailBack").onclick=()=>{state.stack.pop();state.comparison=state.stack.at(-1)?.comparison||"repair";renderDetail();};
$("#runSelect").onchange=e=>{if($("#detailDialog").open)closeDetail();state.run=e.target.value;state.round="";state.snapshot="";state.query="";state.poolStatus="all";load(false,true);};
$("#roundSelect").onchange=e=>changeRound(e.target.value);$("#snapshotSelect").onchange=e=>{state.snapshot=e.target.value;load();};
$("#refreshBtn").onclick=()=>load(true);$("#realMode").onclick=()=>{state.run=state.index.runs[0]?.run_name||"";state.round="";state.snapshot="";load(true,true);};
setInterval(()=>{if($("#autoRefresh").checked&&!$("#detailDialog").open)load(true);},5000);
const initial=new URLSearchParams(location.search);state.run=initial.get("run")||"";state.round=initial.get("round")||"";state.snapshot=initial.get("snapshot")||"";state.tab=initial.get("tab")||"overview";
load(true).then(()=>{if(!initial.has("run")&&state.index?.runs.length){state.run=state.index.runs[0].run_name;state.round="";load();}});
