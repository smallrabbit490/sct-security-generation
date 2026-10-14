"""A7 数据/选择协议：隐藏评分与部署选择分离，冻结确认禁止反向学习。"""
from __future__ import annotations
import hashlib
from pathlib import Path
from methods.direction_screening.protocol import public_task, sample_families, outcome, summarize

ARCHITECTURES=('protect','check','choose')
MEMORIES=('none','m1','m4')
ARMS=tuple(a+'_'+m for a in ARCHITECTURES for m in MEMORIES)
NAMES={'protect':'接口保护后生成','check':'实际检查后修复','choose':'两份候选再选择',
       'none':'无记忆','m1':'质量验证与来源上下文 M1','m4':'分架构反例调整 M4'}


def eligible_cards(task,bank):
    """召回前按 patched 实测质量与 family 隔离过滤；不使用目标答案，不写库。"""
    return [c for c in bank if str(c['family_id'])!=str(task['family_id'])
            and str(c['cwe'])==str(task['CWE_ID'])
            and c.get('source_evidence',{}).get('patched',{}).get('joint') is True
            and c.get('source_evidence',{}).get('patched',{}).get('measured') is True]


def classify_exception(name,phase):
    """内部检查区分候选语法、断言与缺依赖；未确认运行异常不作为修复证据。"""
    if phase=='candidate_compile':
        return 'syntax_error',True
    if name in ('NameError','ModuleNotFoundError','ImportError'):
        return 'unsupported_context',False
    if name=='AssertionError' and phase=='check':
        return 'fail',True
    return 'unconfirmed_runtime_error',False


def passed_ids(candidate):
    return {r['id'] for r in candidate.get('checks',{}).get('cases',[]) if r.get('status')=='pass'}


def rank(candidate):
    """只比较公开 AST 与相同公开测试；同分保留先生成候选，官方分数不可见。"""
    cases=candidate.get('checks',{}).get('cases',[])
    return (-len(candidate.get('issues',[])),len(passed_ids(candidate)),
            -sum(r.get('status')=='fail' for r in cases),sum(r.get('measured',False) for r in cases))


def choose(candidates):
    if not candidates:
        raise ValueError('empty_candidates')
    selected=0
    for i in range(1,len(candidates)):
        if improves(candidates[selected],candidates[i]): selected=i
    return selected


def improves(before,after):
    """修复必须严格改善公开证据且保留原已过用例；缺测不能冒充修复通过。"""
    if not passed_ids(before)<=passed_ids(after):
        return False
    after_cases={r['id']:r for r in after.get('checks',{}).get('cases',[])}
    for case in before.get('checks',{}).get('cases',[]):
        if case.get('measured') and not after_cases.get(case['id'],{}).get('measured'):
            return False
    return rank(after)>rank(before)


def check_groups(groups):
    """分组阶段拒绝跨组 family 重叠及组内重复；不消费任何目标评分。"""
    seen=set()
    for group in groups.values():
        families=[str(r['family_id']) for r in group]
        if len(set(families))!=len(families) or seen.intersection(families):
            raise ValueError('family_overlap')
        seen.update(families)


def hash_files(paths):
    return {str(Path(p).resolve()):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}


def check_frozen(frozen):
    """确认入口校验源码/记忆/数据/策略哈希；冲突拒绝而非静默继续。"""
    if hash_files(frozen)!=frozen:
        raise ValueError('frozen_configuration_changed')
