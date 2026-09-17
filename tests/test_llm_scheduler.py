"""LLM 任务选择器单元测试：验证 prompt 构造、JSON 解析、越界过滤与去重。

语义：模型返回的 selected_ids 是任务的 task_id（即 index），不是列表序号。
"""
import json
import re
import unittest

from methods.sct_lifecycle_replay.llm_scheduler import (
    build_selection_prompt,
    select_tasks_hybrid,
    select_tasks_with_llm,
)


class _FakeRequester:
    """可编程的假请求器：返回预设内容，用于离线测试解析逻辑。"""

    def __init__(self, content: str):
        self.content = content

    def __call__(self, prompt: str):
        return {"choices": [{"message": {"content": self.content}}]}


def _task(index: int, cwe: str = "22", desc: str = "read file path"):
    return {
        "index": index,
        "CWE_ID": cwe,
        "task_description": {"function_name": "read_file", "description": desc, "security_policy": "path must stay in root"},
    }


class LLMSchedulerTests(unittest.TestCase):
    def test_prompt_includes_task_descriptions_and_cwe(self):
        tasks = [_task(1, "22", "path traversal"), _task(2, "78", "command injection")]
        prompt = build_selection_prompt(tasks, 1, seeds=[])
        self.assertIn("CWE=22", prompt)
        self.assertIn("read_file", prompt)
        self.assertIn("path traversal", prompt)
        self.assertIn("selected_ids", prompt)
        self.assertIn("[task_id=1]", prompt)

    def test_prompt_does_not_leak_ground_truth(self):
        # 提示必须不含漏洞/补丁代码或隐藏测试；只给契约描述。
        tasks = [
            {
                "index": 1,
                "CWE_ID": "22",
                "task_description": {"function_name": "read_file", "description": "read file", "security_policy": "safe"},
                "ground_truth": {"vulnerable_code": "open(path)", "patched_code": "check(path)"},
                "unittest": {"testcases": "testcases = {'capability': [...secret...]}"},
            }
        ]
        prompt = build_selection_prompt(tasks, 1, seeds=[])
        self.assertNotIn("open(path)", prompt)
        self.assertNotIn("vulnerable_code", prompt)
        self.assertNotIn("patched_code", prompt)
        self.assertNotIn("secret", prompt)

    def test_select_parses_json_and_returns_chosen_tasks(self):
        tasks = [_task(10), _task(11), _task(12)]
        response = json.dumps({"selected_ids": [10, 12], "reasons": {"10": "new cwe", "12": "high risk"}})
        result = select_tasks_with_llm(tasks, 2, _FakeRequester(response))
        self.assertIsNone(result["error"])
        self.assertEqual([t["index"] for t in result["selected"]], [10, 12])
        # reasons 的 key 是任务 task_id（供 replay_decisions.jsonl 按 task_id 记录理由）。
        self.assertEqual(result["reasons"]["10"], "new cwe")
        self.assertEqual(result["reasons"]["12"], "high risk")

    def test_select_filters_out_of_range_ids_and_dedupes(self):
        tasks = [_task(10), _task(11), _task(12)]
        response = json.dumps({"selected_ids": [10, 10, 999, 11, -1], "reasons": {}})
        result = select_tasks_with_llm(tasks, 5, _FakeRequester(response))
        self.assertIsNone(result["error"])
        self.assertEqual([t["index"] for t in result["selected"]], [10, 11])

    def test_select_respects_limit(self):
        tasks = [_task(10), _task(11), _task(12)]
        response = json.dumps({"selected_ids": [10, 11, 12], "reasons": {}})
        result = select_tasks_with_llm(tasks, 2, _FakeRequester(response))
        self.assertEqual(len(result["selected"]), 2)

    def test_select_tolerates_markdown_fence(self):
        tasks = [_task(10), _task(11)]
        response = '```json\n{"selected_ids": [11], "reasons": {"11": "coverage"}}\n```'
        result = select_tasks_with_llm(tasks, 1, _FakeRequester(response))
        self.assertEqual([t["index"] for t in result["selected"]], [11])

    def test_select_returns_empty_on_garbage_response(self):
        tasks = [_task(10), _task(11)]
        result = select_tasks_with_llm(tasks, 1, _FakeRequester("not json at all"))
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["selected"], [])

    def test_hybrid_fills_limit_with_rule_fallback(self):
        # 模型只选了 1 个，混合调度必须用规则补足到 limit。
        tasks = [_task(10, "22"), _task(11, "78"), _task(12, "95")]
        response = json.dumps({"selected_ids": [11], "reasons": {"11": "high risk"}})
        result = select_tasks_hybrid(tasks, 3, _FakeRequester(response))
        self.assertEqual(len(result["selected"]), 3)
        self.assertEqual(result["selected_by"]["11"], "llm")
        # 补足的任务标记为 rule_fallback。
        fallbacks = [k for k, v in result["selected_by"].items() if v == "rule_fallback"]
        self.assertEqual(len(fallbacks), 2)
        # 全部选中，无重复。
        indexes = [t["index"] for t in result["selected"]]
        self.assertEqual(len(set(indexes)), 3)

    def test_hybrid_batches_large_candidate_pool(self):
        # 候选很多时按 batch_size 分批选择：每个假响应只认自己 batch 内的
        # task_id，验证分批合并、去重、满额与无越界。
        tasks = [_task(i, cwe=str(20 + i)) for i in range(1, 51)]  # 50 个候选

        class _BatchRequester:
            def __init__(self):
                self.calls = 0

            def __call__(self, prompt):
                self.calls += 1
                # 每个响应选中该批第一个任务（task_id 是 1..50 的子集）。
                first = re.search(r"\[task_id=(\d+)\]", prompt)
                tid = int(first.group(1)) if first else 1
                return {
                    "choices": [{"message": {"content": json.dumps({"selected_ids": [tid], "reasons": {str(tid): "r"}})}}]
                }

        requester = _BatchRequester()
        result = select_tasks_hybrid(tasks, 10, requester, batch_size=8)
        self.assertEqual(len(result["selected"]), 10)  # 满额
        self.assertEqual(len(set(t["index"] for t in result["selected"])), 10)  # 去重
        # 分批触发多次 LLM 调用（>1），且选中的都来自候选池。
        self.assertGreater(requester.calls, 1)
        self.assertTrue(all(1 <= t["index"] <= 50 for t in result["selected"]))


if __name__ == "__main__":
    unittest.main()
