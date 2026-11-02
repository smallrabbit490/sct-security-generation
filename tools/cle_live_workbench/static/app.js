const $=s=>document.querySelector(s);let state=null;let receivedAt=0,serverAge=0,connectionError='',fetching=false;
const labels={awaiting_analysis:'待回放与分析',postprocessing:'回放与分析中',needs_wiring:'等待续跑接线',awaiting_case_review:'待案例复盘',passed:'已通过',partial:'部分结果',pending_actual_code_review:'待实际代码复盘',stopped_technical:'技术中断',paused:'用户暂停',preparing:'准备中',manual_pending:'待本窗口接续',partial_analysis:'部分结果已分析',deferred_full:'全量暂缓，跳过',running:'正在运行',waiting_window:'等待允许时段',interrupted:'进程退出，待修复',completed:'已完成',not_started:'未启动',failed:'运行失败',failed_or_unresolved:'请求中断',starting:'启动中',needs_technical_recovery:'技术中断',deferred:'暂缓',not_required:'按协议不执行',ended:'已结束',blocked_external:'外部等待',waiting_dependency:'等待前置完成',waiting_capacity:'等待并发空位',waiting_turn:'按顺序排队',ready:'待接续'};
const armNames={B0:'无经验',BM:'原经验',BF:'功能经验',BS:'安全经验',BFS:'功能＋安全'};
const el=(tag,text,cls)=>{let n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
const num=n=>Number(n||0).toLocaleString('zh-CN');const pct=(a,b)=>b?`${(100*a/b).toFixed(1)}%`:'—';
const executorTypes={api:{label:'API 调用',note:'调用实验模型或 Embedding；实际派发情况看运行状态。'},codex:{label:'Codex 执行',note:'由 GPT-6.1 Sol / xhigh 执行分析、接线或维护，CLI 用量单独记录。'},local:{label:'本地计算',note:'本机脚本执行训练或计算，不调用实验模型。'},human:{label:'人工复核',note:'需要人工确认标签，Codex 不代签。'},external:{label:'外部依赖',note:'等待模型接入或外部环境，不代表已发起 API 调用。'}};
function executorTag(key,label){let type=executorTypes[key],tag=el('span',label||type.label,'executor-tag executor-'+key);tag.dataset.executor=key;tag.title=type.note;tag.setAttribute('aria-label','执行方式：'+(label||type.label));return tag}
function taskExecutor(task){if(task.operation==='repair')return ['codex','Codex 修复'];if(task.id==='FR.human')return ['human','人工复核'];if(task.kind==='external')return ['external','外部依赖'];if(['run','probe'].includes(task.kind))return ['api','API 调用'];if(task.kind==='train')return ['local','本地训练'];return ['codex',({analysis:'Codex 分析',custom:'Codex 分析',prepare:'Codex 接线',closeout:'Codex 报告'})[task.kind]||'Codex 维护']}
function packageExecutors(key){let tags=el('div',undefined,'executor-tags'),types=new Set();for(let task of state?.autonomy?.tasks||[]){if(task.package!==key)continue;let [type]=taskExecutor(task);if(type!=='external')types.add(type)}if(key==='IR02')types.add('codex');if(key==='R01')types.add('local');if(!types.size)types.add('api');for(let type of ['api','codex','local','human'])if(types.has(type))tags.append(executorTag(type,type==='codex'?'Codex 分析':undefined));return tags}
function renderExecutorLegend(){let legend=$('#executor-legend');legend.replaceChildren(el('span','执行方式','small'));for(let key of Object.keys(executorTypes))legend.append(executorTag(key));legend.append(el('span','颜色区分执行方式，运行状态单独显示。','small'))}
function progress(a,b){let n=el('div',undefined,'progress'),i=el('i');i.style.width=b?`${Math.min(100,100*a/b)}%`:'0';n.append(i);return n}
function metric(label,value,note){let n=el('div',undefined,'metric');n.append(el('div',label,'label'),el('div',value,'value'),el('div',note,'note'));return n}
function verdict(value,measured){return el('span',measured===false?'未测量':value===true?'通过':value===false?'失败':'—',measured===false?'unknown':value===true?'pass':value===false?'fail':'unknown')}

const timeText=value=>value?new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'尚无记录';
const stateText=value=>labels[value]||({prepared:'请求已准备',submitted:'请求已发送',completed:'已完成',failed_or_unresolved:'请求中断，响应未完整保存',awaiting_agent_analysis:'待案例分析'})[value]||value||'未开始';
const shownStatus=p=>p.display_status||p.status;
function render(s){
  state=s;
  $('#clock').textContent=`最近采样 ${timeText(s.time)} · 第 ${s.sequence??'—'} 次`;
  $('#window').textContent=s.allowed?'允许调用时段':'禁止新派发时段';
  $('#window').className='badge '+(s.allowed?'running':'');
  $('#model').textContent=s.model||'正在加载';
  $('#workers').textContent=`实验 worker ${s.workers} / ${s.worker_limit}`;
  $('#root').textContent=s.run_root||'';
  $('#refresh-policy').textContent=`每${s.sample_interval_seconds||5}秒采样 · 页面每2秒同步 · 最近采样耗时${s.sample_duration_seconds??'—'}秒`;
  renderCurrent(s);renderOverview(s);
  const active=$('#active');active.replaceChildren();
  const visible=s.packages.filter(p=>p.processes?.length||['interrupted','needs_technical_recovery','postprocessing','waiting_window'].includes(shownStatus(p)));
  for(const p of visible){
    const status=shownStatus(p),n=el('div',undefined,'active-run'),a=el('div'),b=el('div'),title=el('div',undefined,'execution-title');
    title.append(el('strong',p.label),executorTag(status==='postprocessing'?'local':'api'));
    a.append(title,el('span',stateText(status),'badge '+status));
    const processes=p.processes||[],slots=processes.reduce((v,p)=>v+p.workers,0);
    a.append(el('p',processes.length?`${processes.length}个实例 · ${slots}个实验worker · PID ${processes.map(p=>p.pid).join('、')}`:'当前未检测到该实验进程','small'));
    if(p.scope)a.append(el('p',`${p.scope}道题 × ${p.conditions}个条件 × ${p.repeats}次重复`,'small'));
    const done=p.display_completed??p.completed,total=p.display_planned??p.planned;
    b.append(el('strong',`${num(done)} / ${num(total)} 次已保存`),progress(done,total),el('p',`最近结果保存：${timeText(p.last_saved_at)}`,'small'));
    if(p.request){const r=p.request;b.append(el('p',`最近请求：${r.cell_id} · ${r.stage} · ${stateText(r.status)}`),el('p',`请求记录：${timeText(r.time)}${r.elapsed_seconds!=null?' · 耗时'+r.elapsed_seconds.toFixed(1)+'秒':''}`,'small'))}
    if(p.activity){const e=p.activity;b.append(el('p',`传输记录：${e.state}${e.reason_type||e.error_type?' · '+(e.reason_type||e.error_type):''} · ${timeText(e.time)}`,'small'))}
    if(p.native_state?.reason)b.append(el('p','原生状态原因：'+p.native_state.reason,'small'));
    if(p.workflow){const w=p.workflow;a.append(el('p',`生成：${stateText(w.generation)}；回放：${stateText(w.replay)}`,'small'),el('p',`统计覆盖${w.analyzed_cells}次${w.statistics_current?'（已同步）':'（尚未覆盖当前进度）'}；案例复盘：${stateText(w.case_review)}`,'small'))}
    n.append(a,b);active.append(n);
  }
  const guardian=s.guardian;
  if(guardian?.pid&&guardian.current?.status==='running'){let n=el('div',undefined,'active-run');n.append(el('strong','Codex后台任务'),el('span',`PID ${guardian.pid} · ${guardian.model} / ${guardian.reasoning_effort}`));active.append(n)}
  if(!active.children.length)active.append(el('p','当前没有运行或待恢复的实验，查看下方各类型的安排。','empty'));
  renderGroups($('#packages'),s.packages,['实验 / 当前范围','执行方式','状态','保存 / 计划','进度','最近保存'],p=>{
    const tr=el('tr'),execution=el('td'),name=el('td');execution.append(packageExecutors(p.key));name.append(el('div',`${p.label} (${p.key})`));
    if(p.display_note)name.append(el('div',p.display_note,'small'));
    if(p.workflow){const w=p.workflow;name.append(el('div',`回放：${stateText(w.replay)} · 统计覆盖${w.analyzed_cells}次 · 代码复盘：${stateText(w.case_review)}`,'small'))}
    const total=p.display_planned??p.planned,count=p.display_completed??p.completed;
    tr.append(name,execution,el('td',stateText(shownStatus(p))),el('td',total===0&&p.planned?`本轮不执行（原计划${p.planned}次）`:`${num(count)} / ${total??'按原协议'}`));
    const td=el('td');td.append(progress(count,total));tr.append(td,el('td',timeText(p.last_saved_at||p.summary?.updated_utc)));return tr;
  });
  const fs=s.packages.find(p=>p.key==='FFS'),arms=$('#arms');arms.replaceChildren();
  for(const [key,v] of Object.entries((fs?.display_summary||fs?.summary||{}).arms||{})){const n=el('div',undefined,'arm');n.append(el('div',armNames[key]||key),progress(v.joint,v.measured),el('div',`${v.joint} / ${v.measured} · ${pct(v.joint,v.measured)}（保存${v.completed}次）`));arms.append(n)}
  if(!arms.children.length)arms.append(el('p','尚未保存对照结果。','empty'));
  renderResults();draw(s.curve);updateFilters(s);renderRows();renderGuardian(s.guardian);
}
const cohortNames={"1017_only":"1017模型","flash_only":"无1017模型","mixed_saved_prefix":"旧前缀＋无1017模型"};
function renderResults(){
  const select=$('#results-package'),old=select.value;
  const batches=state.packages.filter(p=>['FQ_RETEST','FG_LABELS'].includes(p.key));
  select.replaceChildren(...batches.map(p=>{const option=el('option',p.label);option.value=p.key;return option}));
  if(batches.some(p=>p.key===old))select.value=old;
  const p=batches.find(p=>p.key===select.value),target=$('#live-results');target.replaceChildren();if(!p)return;
  const summary=p.display_summary||p.summary||{},groups=p.model_strata||summary.model_strata;
  const rows=[];
  if(groups&&Object.keys(groups).length){
    for(const [cohort,group] of Object.entries(groups))for(const [name,a]of Object.entries(group.arms||{}))rows.push([cohortNames[cohort]||cohort,name,a.completed,a.measured,a.completed-a.measured,a.functional,a.security,`${a.joint} / ${a.measured}（${pct(a.joint,a.measured)}）`]);
    target.append(el('p','按响应来源分层。旧模型、新模型、复用旧前缀的成绩分别展示；总进度只表示固定名单已保存的次数。','hint'));
  }else for(const [name,a] of Object.entries(summary.arms||{}))rows.push(['1017模型',name,a.completed,a.measured,a.completed-a.measured,a.functional,a.security,`${a.joint} / ${a.measured}（${pct(a.joint,a.measured)}）`]);
  if(rows.length)target.append(evidenceTable(['模型来源','条件','已保存','已测量','未测量','功能通过','安全通过','Joint'],rows));else target.append(el('p','尚无已保存结果。','empty'));
}
function renderOverview(s){
  const packages=s.packages, status=p=>p.display_status||p.status;
  const count=(...states)=>packages.filter(p=>states.includes(status(p))).length;
  const complete=count('completed'),partial=packages.filter(p=>status(p)!=='completed'&&(p.display_completed??p.completed??0)>0).length;
  const running=packages.filter(p=>['running','starting','waiting_window','postprocessing'].includes(status(p)));
  const interrupted=count('needs_technical_recovery','interrupted','failed','failed_or_unresolved','stopped_technical');
  const paused=count('paused'),deferred=count('deferred','deferred_full');
  const waiting=packages.length-complete-running.length-interrupted-paused-deferred;
  const types=new Set(packages.map(researchType)).size;
  $('#metrics').replaceChildren(
    metric('研究全景',`${types} 类 · ${packages.length} 项`,'当前登记的实验与探针'),
    metric('结果积累',`${complete} 项完成`,`${partial} 项已有部分结果 · 各项统计口径见下方`),
    metric('当前执行',`${s.workers} / ${s.worker_limit} worker`,`${running.length} 项运行 · ${interrupted} 项技术中断`),
    metric('后续安排',`${paused} 项暂停`,`${deferred} 项暂缓 · ${waiting} 项待接续或依赖`),
    metric('累计已报告 Token',(Number(s.usage?.known_reported_tokens||0)/1e6).toFixed(2)+' M',`未知或在途 HTTP ${num(s.usage?.unknown_or_inflight_HTTP)}`)
  );
}
function draw(points){let svg=$('#curve');svg.replaceChildren();if(!points.length)return;let maxX=points.length,maxY=Math.max(...points.map(v=>v.coverage),1);let line=points.map((v,i)=>`${45+540*i/Math.max(1,maxX-1)},${192-160*v.coverage/maxY}`).join(' ');let path=document.createElementNS('http://www.w3.org/2000/svg','polyline');path.setAttribute('points',line);path.setAttribute('fill','none');path.setAttribute('stroke','#506e9c');path.setAttribute('stroke-width','2.5');svg.append(path);for(let [x,y,t]of [[10,30,num(maxY)],[20,195,'0'],[45,218,'1'],[550,218,String(maxX)]]){let n=document.createElementNS('http://www.w3.org/2000/svg','text');n.setAttribute('x',x);n.setAttribute('y',y);n.textContent=t;svg.append(n)}}
function renderRows(){if(!state)return;let q=$('#search').value.trim().toLowerCase(),pkg=$('#package').value;let rows=state.rows.filter(r=>(!pkg||r.package===pkg)&&(!q||[r.task_id,...r.selected,...r.adopted].join(' ').toLowerCase().includes(q))).slice(0,100),tbody=$('#tasks');tbody.replaceChildren();for(let r of rows){let tr=el('tr');tr.tabIndex=0;tr.append(el('td',`${r.task_id} / ${r.stage||r.arm||r.package}`),el('td',cohortNames[r.model_cohort]||'1017模型'),el('td',r.selected.join('\n')||(r.package==='IR02'?'见原始材料，此处未展开':'无卡'),'card-ids'),el('td',r.adopted.join('\n')||(r.package==='IR02'?'此记录未提取':'未声明'),'card-ids'));for(let key of ['functional','security','joint']){let td=el('td');td.append(verdict(r[key],r.measured));tr.append(td)}tr.onclick=()=>detail(r);tr.onkeydown=e=>{if(e.key==='Enter')detail(r)};tbody.append(tr)}}
function renderGuardian(g){if(!g)return;$('#auto').textContent=g.enabled?'自主执行：已开启':'自主执行：已关闭';$('#auto').className=g.enabled?'badge running':'';$('#guardian').textContent=g.pid?`Codex CLI 正在处理，PID ${g.pid}`:g.current?.status==='capacity_wait'?'6.1 Sol容量已满，等待后以原模型自动续试。':g.enabled?'正在监视运行状态；发现新错误后自动处理。':'自动派发和自动修复已关闭；当前由本窗口接续，暂停实验不会自动恢复。';$('#cli').textContent=g.codex||'未找到 Codex CLI';let jobs=$('#jobs');jobs.replaceChildren();let values=[...(g.history||[])].reverse();if(g.current&&!values.some(x=>x.job_id===g.current.job_id))values.unshift(g.current);for(let job of values){let n=el('div',undefined,'job'),title=el('div',undefined,'execution-title');title.append(el('h3',`历史记录 · ${job.incident?.package||'检查'} · ${job.status==='running'&&!g.pid?'进程已结束':job.status==='finished'?'已结束':job.status}`),executorTag(...taskExecutor(job.incident?.work_item||{kind:'maintenance'})));n.append(title,el('p',`${job.started} ${job.finished?'→ '+job.finished:''}`,'small'));if(job.result){n.append(el('p',job.result.summary));for(let action of job.result.actions||[])n.append(el('p','· '+action));for(let rest of job.result.remaining||[])n.append(el('p','当时记录的后续安排：'+rest))}jobs.append(n)}if(!values.length)jobs.append(el('p','尚无修复事件。','empty'))}
function evidenceTable(headers,rows){let wrap=el('div',undefined,'table-scroll'),t=el('table'),head=el('thead'),tr=el('tr');headers.forEach(h=>tr.append(el('th',h)));head.append(tr);t.append(head);let body=el('tbody');rows.forEach(values=>{let r=el('tr');values.forEach(v=>r.append(el('td',String(v??'—'))));body.append(r)});t.append(body);wrap.append(t);return wrap}
async function detail(r){let data=await(await fetch(`/api/task?package=${encodeURIComponent(r.package)}&cell=${encodeURIComponent(r.cell_id)}`)).json();$('#detail-title').textContent=`题目 ${data.task_id} · ${data.cell_id}`;let body=$('#detail-body');body.replaceChildren();body.append(el('h3','选卡与采用'),evidenceTable(['生成轮次','候选卡 / 已学Q','选入卡号','声明采用','所选卡Q'],(data.mechanism||[]).map(m=>[Number(m.attempt)+1,`${m.candidate_count} / ${m.learned_candidates}`,m.selected.join('\n'),m.adopted.join('\n')||'未声明',m.selected_Q.join(', ')])),el('h3','Q 更新记录'),evidenceTable(['卡号','奖励','更新前 Q','更新后 Q','反馈次数','是否记账'],(data.q_credit_events||[]).map(e=>[e.invariant_id,e.reward,Number(e.q_before).toFixed(3),Number(e.q_after).toFixed(3),e.q_visits,e.credited?'是':e.skip_reason||'否'])));for(let a of data.attempts||[]){let d=el('details'),summary=el('summary',`第 ${Number(a.attempt)+1} 次生成 · Joint ${a.joint===true?'通过':a.joint===false?'失败':'未测'}`);d.append(summary,el('pre',a.code||'代码未保存'));body.append(d)}$('#detail').showModal()}
function renderSelftest(test){let target=$('#selftest');if(!target)return;target.replaceChildren();if(!test||test.status==='not_started')return;target.append(el('h3','隔离自动修复全链路验收'));if(test.status==='passed'){target.append(el('p',`通过 · ${Object.values(test.checks||{}).filter(Boolean).length} 项检查；${test.mock_unique_cells} 条本地模拟请求全部唯一，正式实验 API ${test.experiment_API_calls} 次。`,'pass'),el('p',`${test.model} / ${test.reasoning_effort} 自动完成修复续跑、阶段分析及下一阶段启动。`))}else target.append(el('p',test.status==='running'?'隔离验收运行中，正式实验独立继续。':`验收状态：${test.status} ${test.error||''}`));target.append(el('p',test.root||'','path'))}
function renderAutonomy(data){if(!data)return;let counts=data.counts||{},names=Object.fromEntries(data.tasks.map(t=>[t.id,t.title]));$('#autonomy-summary').textContent=`${data.status==='manual_supervision'?'当前由本窗口接续，自主派发关闭':'任务状态'} · ${counts.completed||0}项完成 · ${counts.partial_analysis||0}项部分分析 · ${counts.paused||0}项暂停 · ${counts.not_required||0}项不执行 · 共${data.tasks.length}个节点`;$('#autonomy-next').textContent=data.next_description?'下一步：'+data.next_description:data.next?'下一项：'+names[data.next]:'当前没有可立即接续的新任务。';let status={completed:'已完成',running:'正在运行',ready:'待接续',blocked_external:'外部等待',waiting_dependency:'等待前置完成',waiting_capacity:'等待并发空位',waiting_window:'等待允许时段',waiting_turn:'按顺序排队'},kinds={replay:'本地回放',probe:'小批探针',run:'全量执行',analysis:'回放与分析',prepare:'接线准备',train:'离线训练',custom:'综合分析',external:'外部依赖',closeout:'报告收尾'},reasons={cli_model_capacity:"6.1 Sol容量等待，自动续试",v32_unavailable:'v3.2不可用',original_validator_image_missing:'缺原验证镜像',human_review_pending:'待人工标签确认',provider_balance_or_auth:'服务余额或认证待处理',budget_exhausted:'已达固定预算',scientific_decision_required:'需要明确实验决策',paused_by_user:'按用户要求暂停',negative_gate_stop:'未通过扩大条件，不执行确认实验',verified_bounded_result:'已核对小批结果、回放与分析'};renderGroups($('#autonomy-tasks'),data.tasks,['任务','执行方式','阶段','状态','前置任务 / 等待原因'],t=>{let row=el('tr'),title=el('td');title.append(el('div',t.title),el('div',t.id,'small'));let why=t.reason?.startsWith('upstream:')?'前置任务受外部依赖阻塞':reasons[t.reason]||t.reason||(t.execution==='not_required_by_protocol'?'本轮无需执行，不生成成绩':(t.depends||[]).map(d=>names[d]||d).join('；')||'—');let execution=el('td');execution.append(executorTag(...taskExecutor(t)));let job=state?.guardian?.current;if(job?.status==='running'&&job.incident?.task_id===t.id&&job.incident?.work_item?.operation==='repair')execution.append(executorTag('codex','Codex 修复'));row.append(title,execution,el('td',kinds[t.kind]||t.kind),el('td',labels[t.display_status]||status[t.status]||t.status),el('td',why));return row})}

function renderCurrent(s){let c=s.control;let box=$('#control-state');box.hidden=!c;if(c){box.textContent=`${c.owner} · ${c.Q} · ${c.memory} · ${c.full_tasks} · ${c.retrieval}`;$('#auto').disabled=true;$('#auto').title='当前按用户要求关闭自主派发';$('#check').disabled=true;$('#check').title='当前按用户要求关闭自动修复'}let f=$('#findings');f.replaceChildren();for(let item of s.findings||[]){let n=el('div',undefined,'job');n.append(el('h3',item.title),el('p',item.result),el('p',item.impact,'small'));f.append(n)}let costs=$('#costs');costs.replaceChildren(evidenceTable(['实验','已报告Token','物理HTTP','用量未知或在途HTTP','本批预算占用 / Token上限','HTTP / 上限'],s.packages.filter(p=>p.usage_summary?.physical_HTTP||Object.keys(p.stages||{}).length).map(p=>{let v=p.key==='FQ_LEARN'?Object.values(p.stages).reduce((a,b)=>({known_reported_tokens:a.known_reported_tokens+(b.known_reported_tokens||0),physical_HTTP:a.physical_HTTP+(b.physical_HTTP||0),unknown_or_inflight_HTTP:a.unknown_or_inflight_HTTP+(b.unknown_or_inflight_HTTP||0)}),{known_reported_tokens:0,physical_HTTP:0,unknown_or_inflight_HTTP:0}):p.usage_summary;return[p.label,num(v.known_reported_tokens),num(v.physical_HTTP),num(v.unknown_or_inflight_HTTP),p.budget?num(p.budget.charged_tokens_including_unknown_and_inflight_bounds)+' / '+num(p.budget.cap_tokens):'—',p.budget?num(p.budget.transport_attempts_including_prior)+' / '+num(p.budget.cap_HTTP):'—']})));costs.append(el('p',s.usage?.note||'','small'))}
function updateFilters(s){let select=$('#package'),value=select.value;let keys=new Set(s.rows.map(r=>r.package));select.replaceChildren(el('option','全部实验'));select.firstChild.value='';for(let key of keys){let name=s.packages.find(p=>p.key===key)?.label||key,opt=el('option',name);opt.value=key;select.append(opt)}if(keys.has(value))select.value=value}


const researchTypes=['Q机制','功能与安全','记忆粒度','检索质量','建库与迁移','影响半径与原因复验','报告与归档'];
function researchType(item){let key=item.package||item.key||'';if(key.startsWith('FQ_'))return 'Q机制';if(key==='FFS'&&!['FS.single_edit'].includes(item.id))return '功能与安全';if(key.startsWith('FG_'))return '记忆粒度';if(key.startsWith('FR'))return '检索质量';if(key.startsWith('IR')||key==='IMPACT_RADIUS'||key==='R01'||item.id==='FS.single_edit')return '影响半径与原因复验';if(['BUILD_C41','FX_GATE','FX_EXTERNAL','P3_EXTERNAL'].includes(key))return '建库与迁移';return '报告与归档'}
function renderGroups(target,items,headers,makeRow){let first=!target.dataset.loaded;target.dataset.loaded='true';let opened=new Set([...target.querySelectorAll('details[open]')].map(n=>n.dataset.type));target.replaceChildren();for(let type of researchTypes){let members=items.filter(item=>researchType(item)===type);if(!members.length)continue;let group=el('details',undefined,'experiment-group');group.dataset.type=type;group.open=opened.has(type)||(first&&members.some(x=>['running','needs_technical_recovery','interrupted'].includes(x.display_status||x.status)));let summary=el('summary'),active=members.filter(x=>(x.display_status||x.status)==='running').length,done=members.filter(x=>(x.display_status||x.status)==='completed').length;summary.append(el('strong',type),el('span',`${members.length}项 · ${done}项完成${active?' · '+active+'项运行中':''}`,'small'),el('span','点击展开 / 收起','small group-action'));let scroll=el('div',undefined,'table-scroll'),table=el('table'),head=el('thead'),tr=el('tr');headers.forEach(h=>tr.append(el('th',h)));head.append(tr);let body=el('tbody');members.forEach(item=>body.append(makeRow(item)));table.append(head,body);scroll.append(table);group.append(summary,scroll);target.append(group)}}


function freshness(){
  const age=receivedAt?serverAge+(Date.now()-receivedAt)/1000:Infinity;
  const stale=age>20, badge=$('#freshness');
  badge.textContent=connectionError?'连接中断':state?.monitor_error?'采样失败':stale?(state?'数据已过期':'正在连接'):`实时 · ${Math.max(0,Math.floor(age))}秒前`;
  badge.className='badge '+(!stale&&!connectionError&&!state?.monitor_error?'running':'interrupted');
  const message=connectionError?`无法连接工作台，保留最后一次数据：${connectionError}`:state?.monitor_error?`采样失败，保留最后一次数据：${state.monitor_error}`:stale&&state?'超过20秒未获得新采样，当前数字为最后一次保存的显示值。':'';
  $('#error').hidden=!message;$('#error').textContent=message;
}
async function refresh(){
  if(fetching)return;fetching=true;$('#refresh').disabled=true;
  try{
    const r=await fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error(r.status);
    const data=await r.json();connectionError='';
    if(data.loading){$('#freshness').textContent='正在读取原生结果';return}
    receivedAt=Date.now();serverAge=Math.max(0,(Date.parse(data.server_time||data.time)-Date.parse(data.time))/1000);
    render(data);renderSelftest(data.selftest);renderAutonomy(data.autonomy);
  }catch(e){connectionError=e.name==='TimeoutError'?'请求超时':e.message}
  finally{fetching=false;$('#refresh').disabled=false;freshness()}
}
async function poll(){await refresh();setTimeout(poll,2000)}
async function control(action){let r=await fetch('/api/guardian/'+action,{method:'POST',headers:{'X-CLE-Control':'workbench'}});if(!r.ok){alert('操作失败：'+r.status);return}refresh()}
for(let b of document.querySelectorAll('nav button'))b.onclick=()=>{document.querySelectorAll('nav button,.tab').forEach(n=>n.classList.remove('active'));b.classList.add('active');$('#'+b.dataset.tab).classList.add('active')};$('#package').onchange=renderRows;$('#search').oninput=renderRows;$('#close').onclick=()=>$('#detail').close();$('#auto').onclick=()=>control('toggle');$('#check').onclick=()=>control('check');$('#results-package').onchange=renderResults;$('#refresh').onclick=refresh;document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});window.addEventListener('focus',refresh);renderExecutorLegend();poll();setInterval(freshness,1000);
