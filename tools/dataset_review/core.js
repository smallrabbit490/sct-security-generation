/* 人工复核的纯数据逻辑：不执行题包代码，CSV 字段与仓库模板保持一致。 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ReviewCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const FIELDS = ["review_id", "annotator", "human_verdict", "human_defect_type", "assertion_or_call", "missing_requirement", "why_not_inferable", "human_test_integrity", "human_test_quality", "type_consistency", "disagreement_reason", "confidence", "notes"];
  const OPTIONS = {
    human_verdict: ["合格", "有缺陷", "无法判定"],
    human_defect_type: ["接口契约", "业务规则或数据", "题面与测试冲突", "环境依赖"],
    human_test_integrity: ["完整", "不完整或语法错误", "未提供", "无法判定"],
    human_test_quality: ["充分", "安全组偏弱", "Joint 可被绕过", "输出格式过严", "缺少正例", "无法判定"],
    type_consistency: ["一致", "类型不一致", "不适用_人工判合格", "无法判定", "确认原合格", "推翻原合格"],
    confidence: ["高", "中", "低"]
  };
  const LABELS = {annotator: "标注人", human_verdict: "题目结论", human_defect_type: "首要缺陷类型", assertion_or_call: "断言或调用证据", missing_requirement: "缺失或冲突的要求", why_not_inferable: "无法推断的理由", human_test_integrity: "测试完整性", human_test_quality: "测试质量", type_consistency: "与机器类型的一致性", disagreement_reason: "分歧理由", confidence: "判断信心", notes: "补充说明"};
  function blank(id) { return Object.fromEntries(FIELDS.map(f => [f, f === "review_id" ? id : ""])); }
  function expectedConsistency(row, model) {
    if (model && model.review_kind === "qualified_risk") {
      if (row.human_verdict === "合格") return "确认原合格";
      if (row.human_verdict === "有缺陷") return "推翻原合格";
      if (row.human_verdict === "无法判定") return "无法判定";
      return "";
    }
    if (row.human_verdict === "合格") return "不适用_人工判合格";
    if (row.human_verdict === "无法判定") return "无法判定";
    if (row.human_verdict === "有缺陷" && row.human_defect_type && model) return row.human_defect_type === model.defect_type ? "一致" : "类型不一致";
    return "";
  }
  function validate(row, model, stage = "final") {
    const errors = [];
    const required = ["annotator", "human_verdict", "human_test_integrity", "human_test_quality", "confidence"];
    if (row.human_verdict === "有缺陷") required.push("human_defect_type", "assertion_or_call", "missing_requirement", "why_not_inferable");
    if (row.human_verdict === "无法判定") required.push("notes");
    for (const f of required) if (!String(row[f] || "").trim()) errors.push(`请填写${LABELS[f]}`);
    for (const [f, values] of Object.entries(OPTIONS)) if (row[f] && !values.includes(row[f])) errors.push(`${LABELS[f]}的选项无效`);
    if (row.human_verdict !== "有缺陷" && row.human_defect_type) errors.push("仅“有缺陷”填写缺陷类型");
    if (["不完整或语法错误", "未提供"].includes(row.human_test_integrity) && row.human_test_quality !== "无法判定") errors.push("测试损坏或未提供时，测试质量应为“无法判定”");
    if (stage === "final") {
      if (!row.type_consistency) errors.push("请先核对机器标签并选择类型一致性");
      const expected = expectedConsistency(row, model);
      if (row.type_consistency && expected && row.type_consistency !== expected) errors.push(`按当前人工结论，一致性应为“${expected}”`);
      if (["类型不一致", "不适用_人工判合格", "推翻原合格"].includes(row.type_consistency) && !String(row.disagreement_reason || "").trim()) errors.push("请填写否定或改类的分歧理由");
    }
    return errors;
  }
  function status(row, model) {
    if (row._completed && validate(row, model).length === 0) return "completed";
    if (row._revealed) return "comparison";
    if (FIELDS.slice(1).some(f => String(row[f] || "").trim())) return "draft";
    return "empty";
  }
  function csv(rows) {
    const quote = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
    return "\uFEFF" + [FIELDS.join(","), ...rows.map(r => FIELDS.map(f => quote(r[f])).join(","))].join("\r\n") + "\r\n";
  }
  function parseCSV(text) {
    const input = String(text).replace(/^\uFEFF/, "");
    const records = []; let row = [], cell = "", quoted = false, afterQuote = false;
    const endCell = () => { row.push(cell); cell = ""; afterQuote = false; };
    const endRow = () => { endCell(); if (row.some(v => v !== "")) records.push(row); row = []; };
    for (let i = 0; i < input.length; i++) {
      const c = input[i];
      if (quoted) {
        if (c === '"' && input[i + 1] === '"') { cell += '"'; i++; }
        else if (c === '"') { quoted = false; afterQuote = true; }
        else cell += c;
      } else if (c === '"' && cell === "" && !afterQuote) quoted = true;
      else if (c === ",") endCell();
      else if (c === "\n" || c === "\r") { if (c === "\r" && input[i + 1] === "\n") i++; endRow(); }
      else if (afterQuote || c === '"') throw new Error("CSV 引号格式无效");
      else cell += c;
    }
    if (quoted) throw new Error("CSV 存在未闭合引号");
    if (cell || row.length || afterQuote) endRow();
    if (!records.length) throw new Error("CSV 为空");
    const headers = records.shift();
    if (headers.length !== FIELDS.length || new Set(headers).size !== FIELDS.length || FIELDS.some(f => !headers.includes(f))) throw new Error("CSV 表头必须与 13 列标注模板一致");
    return records.map((values, i) => {
      if (values.length !== headers.length) throw new Error(`CSV 第 ${i + 2} 行列数错误`);
      const r = Object.fromEntries(headers.map((f, j) => [f, values[j]]));
      for (const [f, choices] of Object.entries(OPTIONS)) if (r[f] && !choices.includes(r[f])) throw new Error(`${r.review_id}：${LABELS[f]}选项无效`);
      return r;
    });
  }
  function importRows(imported, knownIds) {
    const known = new Set(knownIds), seen = new Set();
    for (const r of imported) {
      if (!known.has(r.review_id)) throw new Error(`不属于当前题包的编号：${r.review_id}`);
      if (seen.has(r.review_id)) throw new Error(`重复编号：${r.review_id}`);
      seen.add(r.review_id);
    }
    return imported.filter(r => FIELDS.slice(1).some(f => String(r[f] || "").trim()));
  }
  return {FIELDS, OPTIONS, LABELS, blank, validate, status, expectedConsistency, csv, parseCSV, importRows};
});
