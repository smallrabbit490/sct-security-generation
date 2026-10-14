"""训练选择门控：用户允许净提升，但安全退步需审核；不写正式长期经验库。"""
from .metrics import compare


def decide(before, after):
    """完整同题训练对照→门控决定；独立确认/正式H_pass不进入此函数。

    净Joint提升可以容忍功能退步并保留证据。安全退步转人工审核，缺测/清单
    不一致保持探索状态，绝不以缺测归零掩盖失败。这是训练选择，不是独立证明。
    """
    paired = compare(before, after)
    if paired['measured_pairs'] != len(before) or len(before) != len(after):
        status, reason = 'incomplete_evidence', '清单不一致或存在缺测，不能自动晋升'
    elif paired['security_harms']:
        status, reason = 'needs_safety_review', '出现安全退步，按用户要求单独审核'
    elif paired['net_joint'] > 0:
        status, reason = 'accepted', '同题Joint净提升，保留并突出全部退步'
    else:
        status, reason = 'exploration_branch', '未取得净提升，保留分支及失败证据'
    return {'status': status, 'reason': reason, 'paired': paired,
            'independent_confirmation': False, 'writes_long_term_memory': False}
