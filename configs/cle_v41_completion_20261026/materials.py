"""迁移包的只读经验呈现材料；只引用卡片原文及目标公开契约，不更新经验/Q。"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from methods.sct_trajectory.agent_pipeline import _content, _extract_json
from methods.sct_trajectory.memory_views import source_projection, draft_view, render_view, _leaves, METADATA_FIELDS
from methods.sct_trajectory.memory_granularity import public_task, reviewed_binding, source_quote
from methods.sct_trajectory.context_pipeline import JSON_FORMAT_POLICY
from methods.sct_trajectory.replay_journal import write_json


class Materials:
    """同源分区由来源卡独立生成并缓存；AI审核方式单列，不冒充人工相关性标签。"""
    def __init__(self, root, request_for):
        self.root, self.request_for = Path(root), request_for
        self.root.mkdir(parents=True, exist_ok=True)
        self.examples = None

    def _ask(self, identity, prompt, validate):
        request = self.request_for(identity)
        errors = []
        for attempt in range(2):
            response = request(prompt + ('\nFORMAT RETRY: Return valid JSON and preserve exact source text.' if attempt else ''))
            try:
                value = _extract_json(_content(response))
                validate(value)
                return value
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                errors.append(type(exc).__name__)
        raise ValueError('material_format_failed:' + ','.join(errors))

    def view_specs(self, cards):
        result = {}
        for card in cards:
            source = source_projection(card)
            identity = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()[:20]
            path = self.root / 'views' / (identity + '.json')
            if path.exists():
                spec = json.loads(path.read_text(encoding='utf-8'))
            else:
                leaves = list(_leaves({k: v for k, v in source.items() if k not in METADATA_FIELDS}))
                payload = [{'path': list(p), 'text': t} for p, t in leaves]
                prompt = ('Partition each SOURCE text into consecutive exact text parts. Assign functional '
                    '(valid behavior/interface preservation), security (attack prevention/check/action), or context '
                    '(applicability, exclusions, source conditions). Do not rewrite, omit or add any character. '
                    'Mixed texts may have multiple parts. Return JSON {"items":[{"path":["field"],'
                    '"parts":[{"text":"exact source text","role":"context"}]}]}. '
                    + JSON_FORMAT_POLICY + '\nSOURCE:\n' + json.dumps(payload, ensure_ascii=False))
                def convert(value):
                    segments = []
                    by_path = {tuple(item['path']): item['parts'] for item in value['items']}
                    for leaf, text in leaves:
                        parts = by_path[leaf]
                        if ''.join(part['text'] for part in parts) != text:
                            raise ValueError('not_exact_partition')
                        cursor = 0
                        for part in parts:
                            end = cursor + len(part['text'])
                            segments.append({'path': list(leaf), 'start': cursor, 'end': end, 'role': part['role']})
                            cursor = end
                    spec = {'card_id': card['invariant_id'], 'review_status': 'reviewed',
                        'reviewer': 'v4.1 source-only annotation with exact coverage validation',
                        'annotation_method': 'AI_source_only_not_human_gold', 'segments': segments}
                    render_view(source, spec, 'BFS')
                    return spec
                try:
                    spec = convert(self._ask('material_view_' + identity, prompt, convert))
                except ValueError as exc:
                    # 用户允许基础比较完成：使用预先公开的字段规则分区，明确记其不确定性。
                    spec = draft_view(card)
                    for part in spec['segments']:
                        field = part['path'][0]
                        part['role'] = ('context' if field in ('applicability','exclusion_conditions','language_leaf')
                                        else 'functional' if field == 'negative_guardrail' else 'security')
                    spec.update(review_status='reviewed', reviewer='predeclared field-role rule',
                        annotation_method='rule_partition_after_AI_format_failure', annotation_error=str(exc),
                        semantic_partition_uncertainty=True)
                    render_view(source, spec, 'BFS')
                write_json(path, spec)
            result[card['invariant_id']] = spec
        return result

    def level_materials(self, cards, task, level):
        specs, bindings = {}, {}
        public = public_task(task)
        for card in cards:
            source = source_projection(card)
            candidates = [(path, text) for path, text in _leaves(source)
                if path[0] in ('high_level_invariant','negative_guardrail','positive_principle') and text.strip()]
            if not candidates:
                candidates = list(_leaves({k:v for k,v in source.items() if k not in METADATA_FIELDS}))
            path, text = candidates[0]
            quote = text.split(';', 1)[0].strip() or text
            specs[card['invariant_id']] = {'card_id': card['invariant_id'], 'review_status': 'reviewed',
                'reviewer': 'fixed first source clause; exact source check', 'reminder': {'path': list(path), 'quote': quote}}
            source_quote(source, specs[card['invariant_id']]['reminder'])
            if level == 'L3':
                key = hashlib.sha256(json.dumps([source, public], sort_keys=True).encode()).hexdigest()[:20]
                target = self.root / 'bindings' / (key + '.json')
                if target.exists():
                    binding = json.loads(target.read_text(encoding='utf-8'))
                else:
                    prompt = ('Map the SOURCE experience to the PUBLIC TARGET without inventing requirements. '
                        'Return JSON with operations:[{action,card_evidence:[{path:["field"],quote}],'
                        'public_evidence:[{field,quote}]}], bound_elements:[{role,name,public_field}], '
                        'unbound_source_details:[{detail,status}]. Quotes must be exact substrings; bound names '
                        'must appear in the named public field. Preserve unknown data layouts/APIs as unknown. '
                        'Never use source example constants or add restrictions not stated by the target. '
                        + JSON_FORMAT_POLICY + '\nSOURCE:' + json.dumps(source, ensure_ascii=False)
                        + '\nPUBLIC TARGET:' + json.dumps(public, ensure_ascii=False))
                    def enrich(value):
                        value = {**value, 'card_id': card['invariant_id'], 'public_task': public,
                                 'review_status': 'reviewed', 'reviewer': 'AI public-source mapping; not correctness certification'}
                        reviewed_binding(card, task, value)
                        return value
                    try:
                        binding = enrich(self._ask('material_binding_' + key, prompt, enrich))
                    except ValueError as exc:
                        field = next(k for k in ('description','security_policy','arguments','context') if public.get(k))
                        binding = enrich({'operations': [{'action': 'Apply this source principle only where compatible with the stated target behavior: ' + quote,
                            'card_evidence': [{'path':list(path),'quote':quote}],
                            'public_evidence':[{'field':field,'quote':public[field]}]}],
                            'bound_elements':[], 'unbound_source_details':[{'detail':'source-specific APIs and storage assumptions',
                                'status':'not bound; target public contract governs'}],
                            'annotation_method':'literal_source_public_rule_after_AI_format_failure','annotation_error':str(exc)})
                    write_json(target, binding)
                bindings[card['invariant_id']] = binding
        if level == 'L4' and self.examples is None:
            from configs.cle_memory_mechanisms_20261023.prepare_granularity_views import load_materials
            self.examples = load_materials()[2]
        return {'card_specs': specs, 'bindings': bindings, 'examples': self.examples or {}}
