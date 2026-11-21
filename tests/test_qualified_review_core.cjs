const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../tools/dataset_review/core.js");
const model = {verdict:"合格", defect_type:null, review_kind:"qualified_risk"};
test("合格复核区分确认原标签与推翻原标签，未定义的缺陷类型不强行比较", () => {
  const row = {...C.blank("QR-001"), annotator:"A", human_verdict:"合格",
    human_test_integrity:"完整", human_test_quality:"无法判定", confidence:"高",
    type_consistency:"确认原合格"};
  assert.equal(C.expectedConsistency(row, model), "确认原合格");
  assert.deepEqual(C.validate(row, model), []);
  Object.assign(row, {human_verdict:"有缺陷", human_defect_type:"接口契约",
    assertion_or_call:"f(request={})", missing_requirement:"name",
    why_not_inferable:"dict only", type_consistency:"推翻原合格"});
  assert.equal(C.expectedConsistency(row, model), "推翻原合格");
  assert.ok(C.validate(row, model).some(x => x.includes("分歧理由")));
  row.disagreement_reason = "仅给类型但关键字名未给";
  assert.deepEqual(C.validate(row, model), []);
});
