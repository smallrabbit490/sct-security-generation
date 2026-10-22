"""按授权顺序完成两次参与学习和冻结评价；阶段结束写中文报告，失败原样留证。"""
from pathlib import Path
import json
import traceback

from methods.cle_ablation import run_memory_q_online as study


def report():
    """报告只消费已落盘结果；未执行部分显示待执行，不把训练正确率写成迁移收益。"""
    meta = study.read(study.OUT / 'run_metadata.json')
    lines = ['# CLE Q参与式两阶段学习与全D_gate四臂执行报告', '',
        f'当前状态：`{meta["status"]}`。协议：`{study.PROTOCOL}`。', '',
        '起点为D_init不限量观察学习后的926/1939张有反馈卡。先全303题D_init，继承状态后全273题D_grow；Q参与候选排序，原P7最多三张，题后按c0/c1实际采用卡更新。两阶段结束后冻结正文、生命周期及Q，进行全298题D_gate四臂。', '',
        '## 已完成和待执行', '',
        '|阶段|完成/计划|功能通过|安全通过|Joint|完整测量|结束有反馈卡|有效更新|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for stage in ('D_init', 'D_grow'):
        p = study.OUT / stage / 'summary.json'
        if p.exists():
            s = study.read(p); f = s['final']
            lines.append(f'|{stage}|{s["executed"]}/{s["planned"]}|{f["functional"]}|{f["security"]}|{f["joint"]}|{f["measured"]}|{s["visited_after"]}/1939|{s["valid_updates"]}|')
        else:
            lines.append(f'|{stage}|待执行/{303 if stage == "D_init" else 273}|—|—|—|—|—|—|')
    gate_path = study.OUT / 'D_gate/summary.json'
    lines += ['', '## D_gate冻结四臂', '',
        'Q0为原CLE候选顺序；Q1为纯相似度顺序；Q2为两次参与学习后的Q融合顺序；Q3在同CWE内打乱该最终库的(Q,visits)，种子20261015。四臂均由模型最多选三张，首次Joint早停，否则最多一次修复并交付末次。', '',
        'Q0/Q1各298条历史记录通过正文、原P7及依赖核验后复用；不重复计入新增成本。相同公开任务、初析、候选规则、生成参数、原180k选择器长度许可及验证环境保留；新增覆盖分支未被这两臂调用。历史执行时间不同，不能声称排除了后端随机性。']
    if gate_path.exists():
        s = study.read(gate_path)
        lines += ['', '|组|完成|F|S|Joint|Joint/298|完整测量|', '|---|---:|---:|---:|---:|---:|---:|']
        for arm in study.ORDER:
            v = s['arms'][arm]
            lines.append(f'|{arm}|{v["n"]}|{v["functional"]}|{v["security"]}|{v["joint"]}|{v["joint"]/298:.2%}|{v["measured"]}|')
        if 'primary_paired' in s:
            lines += ['', '|主要比较|救回|损失|完整配对差|题族95%区间|Holm校正p|', '|---|---:|---:|---:|---|---:|']
            for p in s['primary_paired']:
                lines.append(f'|{p["target"]}-{p["control"]}|{p["wins"]}|{p["losses"]}|{p["difference"]:.2%}|{p["ci95_family_bootstrap"]}|{p["p_holm"]:.6g}|')
            lines += ['', '三项预定统计比较门：' + ('通过，仍需逐题核对救回的改选—采用—代码落实路径。' if s['supports_stable_Q_benefit'] else '未通过，当前完整对照未建立学习Q的稳定Joint收益；不能据此证明Q普遍无效或与对照等效。')]
        lines.append(f'首轮共同候选核对问题：{len(s["first_candidate_issues"])}项；D_gate Q更新为0。')
    else:
        lines += ['', '尚未开始新Q2/Q3生成；已有历史Q0/Q1对照保留，不提前填写新成绩。']
    lines += ['', '## 新增调用和成本', '', '|阶段|逻辑请求|已返回|错误|已知Token|', '|---|---:|---:|---:|---:|']
    cost = {}
    for stage in ('D_init', 'D_grow', 'D_gate'):
        requests = [study.read(p) for p in (study.OUT / stage / 'requests').glob('*.json')]
        cost[stage] = {'calls': len(requests), 'completed': sum(r['status'] == 'completed' for r in requests),
            'errors': sum(r['status'] == 'error' for r in requests),
            'tokens': sum(r.get('total_tokens', 0) for r in requests),
            'embedding': study.read(study.OUT / stage / 'embedding_usage.json') if (study.OUT / stage / 'embedding_usage.json').exists() else None}
        c = cost[stage]
        lines.append(f'|{stage}|{c["calls"]}|{c["completed"]}|{c["errors"]}|{c["tokens"]:,}|')
    study.write(study.CURATED / 'execution_cost.json', cost)
    lines += ['', '费用按LLM逻辑请求和返回用量计；Embedding另存各阶段用量。原生HTTP重试可能无法完整取得计费Token，人民币实付没有账单依据，记为null。复用初析和旧对照不重复计费。', '',
        '## 结论边界与保留材料', '',
        'D_init/D_grow分数是学习轨迹成绩，不是冻结策略的独立收益。D_grow全273题均执行，只有预先合格的228题允许授信；其余45题的原始问题与记录保留。D_init继承已披露的5题弱安全测试限制。Q是多张声明采用卡共享整份代码的奖励，不是单卡贡献的证明。', '',
        '本轮未重建卡片、未改变生命周期、未训练模型权重、未在D_gate更新Q，也未启动Base/Plus或完整CLE经验演化。D_gate有历史开发暴露，属于开发比较。若出现基础设施或协议问题，原失败保留，不能按成绩覆盖重跑。', '',
        f'分支：`{meta["branch"]}`；提交基线：`{meta["commit"]}`；实际源码见运行区source_snapshot。', '',
        '原生运行区：`translation_work/diagnostics/20261020/cle_q_online_v1/`。精简结果：`results/curated/cle_q_online_20261020/`。无密钥配置：`configs/cle_q_online_20261020/`。', '',
        '各学习题的task_rows含实际读取Q、候选覆盖、改排、选中及声明采用记录；memory_q_events记录逐卡授信；frozen保留阶段末Q。旧数据和旧Q全部未覆盖。']
    text = '\n'.join(lines) + '\n'
    (study.ROOT / 'docs/CLE_Q参与式两阶段学习与全Dgate四臂执行报告_20261020.md').write_text(text, encoding='utf-8')
    study.write(study.CURATED / 'execution_status.json', {'status': meta['status'], 'completed_stages': meta['completed_stages']})


def main():
    report()
    try:
        for stage in ('D_init', 'D_grow'):
            study.learn(stage)
            report()
        study.gate()
    except Exception as exc:
        meta = study.read(study.OUT / 'run_metadata.json')
        meta.update(status='stopped_technical', exception_type=type(exc).__name__)
        study.write(study.OUT / 'run_metadata.json', meta)
        study.write(study.OUT / 'execution_exception.json', {'type': type(exc).__name__, 'traceback': traceback.format_exc()})
        raise
    finally:
        report()


if __name__ == '__main__':
    main()
