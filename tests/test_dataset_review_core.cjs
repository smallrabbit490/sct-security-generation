/* Node 内置测试覆盖真实 CSV 往返、人工判定校验和导入边界。 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const C = require("../tools/dataset_review/core.js");
const model = {verdict: "有缺陷", defect_type: "接口契约"};
function valid() {
  return {...C.blank("HR-001"), annotator:"复核员甲", human_verdict:"有缺陷", human_defect_type:"接口契约", assertion_or_call:'tests.testcases[0]\nassert call("a,b") == "中文"', missing_requirement:"参数名未公开", why_not_inferable:"原文只写类型", human_test_integrity:"完整", human_test_quality:"安全组偏弱", confidence:"高", type_consistency:"一致"};
}
test("CSV 13 列顺序与原始模板一致", () => {
  const header = fs.readFileSync(path.join(__dirname, "../data/audit_release_20261118/human_review_150/annotation_template.csv"), "utf8").replace(/^\uFEFF/, "").split(/\r?\n/)[0];
  assert.equal(C.FIELDS.join(","), header);
});
test("中文、引号、逗号和多行证据能无损 CSV 往返", () => {
  const r = valid(); r.notes = '首行\r\n第二行含 "引号", 逗号\n最后一行';
  const output = C.csv([r]);
  assert.ok(output.startsWith("\uFEFF"));
  assert.deepEqual(C.parseCSV(output), [r]);
  assert.deepEqual(C.parseCSV(C.csv([C.blank("HR-150")]))[0], C.blank("HR-150"));
});
test("拒绝错误表头、截断引号和异常列数", () => {
  assert.throws(() => C.parseCSV("review_id,notes\nHR-001,a"), /表头/);
  assert.throws(() => C.parseCSV(C.FIELDS.join(",") + '\n"HR-001'), /未闭合/);
  assert.throws(() => C.parseCSV(C.FIELDS.join(",") + "\nHR-001,too,few"), /列数/);
});
test("独立判断不要求机器一致性；缺陷举证三项全部必填", () => {
  const r = valid(); r.type_consistency = "";
  assert.deepEqual(C.validate(r, model, "blind"), []);
  assert.ok(C.validate(r, model).some(e => e.includes("一致性")));
  for (const f of ["assertion_or_call", "missing_requirement", "why_not_inferable"]) assert.ok(C.validate({...r, [f]: ""}, model, "blind").length);
});
test("测试损坏单列，未知结论必须说明材料缺口", () => {
  assert.ok(C.validate({...valid(), human_test_integrity:"不完整或语法错误"}, model).some(e => e.includes("测试质量")));
  const r = {...valid(), human_verdict:"无法判定", human_defect_type:"", type_consistency:"无法判定", notes:"缺少上下文"};
  assert.deepEqual(C.validate(r, model), []);
  assert.ok(C.validate({...r, notes:""}, model).some(e => e.includes("补充说明")));
});
test("判合格留空类型；改类和否定机器必须说明理由", () => {
  const qualified = {...valid(), human_verdict:"合格", human_defect_type:"", type_consistency:"不适用_人工判合格", disagreement_reason:"公开签名已完整给出参数名"};
  assert.deepEqual(C.validate(qualified, model), []);
  assert.ok(C.validate({...qualified, disagreement_reason:""}, model).length);
  const changed = {...valid(), human_defect_type:"题面与测试冲突", type_consistency:"类型不一致", disagreement_reason:"题面明确要求了相反行为"};
  assert.deepEqual(C.validate(changed, model), []);
  assert.ok(C.validate({...changed, type_consistency:"一致"}, model).length);
});
test("导入必须使用当前题包的唯一编号，空模板不会覆盖工作", () => {
  assert.throws(() => C.importRows([C.blank("other")], ["HR-001"]), /不属于/);
  assert.throws(() => C.importRows([valid(), valid()], ["HR-001"]), /重复/);
  assert.deepEqual(C.importRows([C.blank("HR-001")], ["HR-001"]), []);
  assert.throws(() => C.parseCSV(C.csv([{...valid(), confidence:"伪造选项"}])), /选项无效/);
});
test("填写草稿、已查看标签和最终完成分开统计", () => {
  assert.equal(C.status(C.blank("HR-001"), model), "empty");
  assert.equal(C.status(valid(), model), "draft");
  assert.equal(C.status({...valid(), _revealed:true}, model), "comparison");
  assert.equal(C.status({...valid(), _revealed:true, _completed:true}, model), "completed");
  assert.notEqual(C.status({...valid(), _completed:true, assertion_or_call:""}, model), "completed");
});
