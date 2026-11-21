/* 无浏览器 DOM 适配器检查实际 app.js 的事件流程；不执行题包中的代码。 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const crypto = require("node:crypto");
const C = require("../tools/dataset_review/core.js");
const root = path.join(__dirname, "..");
const read = p => fs.readFileSync(path.join(root, p), "utf8");
const jsonl = p => read(p).trim().split(/\r?\n/).map(JSON.parse);
const sourcePath = "data/audit_release_20261118/human_review_150/";
const labels = new Map(jsonl(sourcePath + "model_labels.jsonl").map(r => [r.review_id, r]));
const translations = JSON.parse(read("tools/dataset_review/translations.zh-CN.json")).tasks;
const data = {version:1, dataset_hash:crypto.createHash("sha256").update(read(sourcePath + "blinded_tasks.jsonl")).digest("hex"), tasks:jsonl(sourcePath + "blinded_tasks.jsonl").map(t => ({...t, model:labels.get(t.review_id), translation:translations[t.review_id].text, search_text:JSON.stringify(t).toLowerCase()}))};

function harness(storage = new Map(), packetData = data) {
  const nodes = [], timers = new Map(), downloads = [], blobs = new Map(); let sequence = 0;
  class Element {
    constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.handlers = {}; this.dataset = {}; this.value = ""; this.textContent = ""; this.hidden = false; this.className = ""; this.attrs = {}; this.classList = {toggle:() => {}}; nodes.push(this); }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    get firstChild() { return this.children[0]; }
    setAttribute(k, v) { this.attrs[k] = v; }
    addEventListener(name, fn) { (this.handlers[name] ||= []).push(fn); }
    fire(name, target = this) { return Promise.all((this.handlers[name] || []).map(fn => fn({target, preventDefault(){}}))); }
    click() { if (this.tagName === "A") downloads.push({name:this.download, blob:blobs.get(this.href)}); return this.fire("click"); }
    remove() {}
    scrollIntoView() {}
    showModal() { this.open = true; }
    close() { this.open = false; }
  }
  for (const match of read("tools/dataset_review/index.template.html").matchAll(/<([a-z][\w-]*)\b([^>]*?)>/g)) {
    const n = new Element(match[1]);
    for (const a of match[2].matchAll(/([\w-]+)="([^"]*)"/g)) {
      if (a[1].startsWith("data-")) n.dataset[a[1].slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = a[2];
      else n[a[1]] = a[2];
    }
    if (/\bhidden\b/.test(match[2])) n.hidden = true;
  }
  const get = id => nodes.find(n => n.id === id);
  get("review-data").textContent = JSON.stringify(packetData);
  const doc = {
    getElementById:get, createElement:tag => new Element(tag), body:nodes.find(n => n.tagName === "BODY"),
    addEventListener(){},
    querySelectorAll(selector) {
      if (selector === "[data-tab]") return nodes.filter(n => n.dataset.tab);
      if (selector === "[data-filter]") return nodes.filter(n => n.dataset.filter);
      if (selector === 'input[name="human_verdict"]') return nodes.filter(n => n.tagName === "INPUT" && n.name === "human_verdict");
      throw new Error(`Unsupported test selector: ${selector}`);
    },
    querySelector() { return null; }
  };
  const window = {ReviewCore:C, addEventListener(){}};
  const localStorage = {getItem:k => storage.get(k) || null, setItem:(k,v) => storage.set(k,v), removeItem:k => storage.delete(k)};
  vm.runInNewContext(read("tools/dataset_review/app.js"), {window, document:doc, localStorage, Blob, URL:{createObjectURL(blob){const key=`blob:${++sequence}`;blobs.set(key,blob);return key;}, revokeObjectURL(){}}, setTimeout(fn){timers.set(++sequence,fn);return sequence;}, clearTimeout(id){timers.delete(id);}}, {timeout:5000});
  return {get, storage, downloads,
    flush(){for (const [key,fn] of [...timers]) {timers.delete(key);fn();}},
    async fill(field,value){const el=get(field);el.value=value;await get("annotation-form").fire(el.tagName === "SELECT" ? "change" : "input", el);},
    async verdict(value){const radio=nodes.find(n => n.tagName === "INPUT" && n.name === "human_verdict" && n.value === value);radio.checked=true;await get("annotation-form").fire("change",radio);},
    state(){return JSON.parse(storage.get(`sct-human-review-v1:${packetData.dataset_hash}`));}
  };
}

test("实际页面脚本能初始化150题，默认不显示机器标签", () => {
  const h = harness();
  assert.equal(h.get("task-list").children.length, 150);
  assert.equal(h.get("model-content").hidden, true);
  assert.equal(h.get("task-title").textContent, "prepare_event_details");
  assert.equal(h.get("overall-count").textContent, "0 / 150");
});

test("真实表单事件：三项证据门控、保存快照、核对、完成和恢复", async () => {
  const h = harness();
  await h.get("reveal-button").click();
  assert.equal(h.get("model-content").hidden, true);
  assert.equal(h.get("validation-errors").hidden, false);
  await h.fill("annotator", "测试标注人"); await h.verdict("有缺陷");
  await h.fill("human_defect_type", labels.get("HR-001").defect_type);
  for (const f of ["assertion_or_call", "missing_requirement", "why_not_inferable"]) await h.fill(f, `测试证据 ${f}`);
  await h.fill("human_test_integrity", "完整"); await h.fill("human_test_quality", "充分"); await h.fill("confidence", "高");
  await h.get("reveal-button").click();
  assert.equal(h.get("model-content").hidden, false);
  assert.equal(h.state().rows["HR-001"]._independent.fields.type_consistency, "");
  await h.fill("type_consistency", "一致"); await h.get("complete-button").click();
  assert.equal(h.get("overall-count").textContent, "1 / 150");
  assert.equal(h.state().current, "HR-002");
  const restored = harness(h.storage);
  assert.equal(restored.get("task-title").textContent, "build_employee_summary");
  assert.equal(restored.get("overall-count").textContent, "1 / 150");
  assert.ok(restored.state().rows["HR-001"]._independent);
});

test("实际导出按钮生成无损多行CSV；空记录保持13列", async () => {
  const h = harness(); await h.fill("notes", '测试中文, "引号"\n下一行');
  await h.get("export-all").click();
  const rows = C.parseCSV(await h.downloads[0].blob.text());
  assert.equal(rows.length, 150); assert.equal(rows[0].notes, '测试中文, "引号"\n下一行');
  assert.deepEqual(rows[149], C.blank("HR-150"));
});

test("不可读的浏览器旧进度不会被页面初始化或保存覆盖", async () => {
  const key = `sct-human-review-v1:${data.dataset_hash}`, storage = new Map([[key, "invalid-json"]]);
  const h = harness(storage); await h.fill("notes", "暂存新标注"); h.flush();
  await h.get("export-all").click();
  assert.equal(storage.get(key), "invalid-json"); assert.equal(h.get("storage-warning").hidden, false);
  assert.equal(C.parseCSV(await h.downloads[0].blob.text())[0].notes, "暂存新标注");
});

test("合格复核题包支持实际独立判断、确认原合格及存储隔离", async () => {
  const task = {...data.tasks[0], review_id:"QR-001",
    model:{verdict:"合格", defect_type:null, review_kind:"qualified_risk",
      risk_level:"中", risk_type:"接口契约", history:{joint_rate:0}, judgments:[]}};
  const h = harness(new Map(), {...data, dataset_hash:"qualified-test", review_kind:"qualified_risk", tasks:[task]});
  assert.equal(h.get("overall-count").textContent, "0 / 1");
  assert.equal(h.get("model-content").hidden, true);
  await h.fill("annotator", "复核员"); await h.verdict("合格");
  await h.fill("human_test_integrity", "完整"); await h.fill("human_test_quality", "无法判定"); await h.fill("confidence", "高");
  await h.get("reveal-button").click();
  assert.equal(h.get("model-content").hidden, false);
  await h.fill("type_consistency", "确认原合格"); await h.get("complete-button").click();
  assert.equal(h.get("overall-count").textContent, "1 / 1");
  assert.equal(h.state().rows["QR-001"]._independent.fields.human_verdict, "合格");
  assert.equal(h.storage.has(`sct-human-review-v1:${data.dataset_hash}`), false);
});
