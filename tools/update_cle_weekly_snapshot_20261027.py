"""Create the requested two weekly report revisions from a real-time snapshot."""
from datetime import datetime
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'docs/research/reports'
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
PERIODS = [('20261014-20261021', '第一周'), ('20261022-20261028', '第二周')]


def latest(name):
    path = sorted((RUN / name).glob('segment_*/summary.json'))[-1]
    return path, json.loads(path.read_text(encoding='utf-8'))


def replace(text, old, new):
    if old not in text:
        raise ValueError('Missing expected report text: ' + old[:80])
    return text.replace(old, new, 1)


def figure(path, labels, groups, title, denominator):
    image = Image.new('RGB', (1400, 560), 'white')
    draw = ImageDraw.Draw(image)
    zh = ImageFont.truetype('C:/Windows/Fonts/simsun.ttc', 26)
    small = ImageFont.truetype('C:/Windows/Fonts/simsun.ttc', 22)
    num = ImageFont.truetype('C:/Windows/Fonts/times.ttf', 24)
    def mixed(text, center, y, size):
        chinese = ImageFont.truetype('C:/Windows/Fonts/simsun.ttc', size)
        latin = ImageFont.truetype('C:/Windows/Fonts/times.ttf', size)
        parts = [(c, latin if ord(c) < 128 else chinese) for c in text]
        x = center - sum(draw.textlength(c, font=font) for c, font in parts) / 2
        for c, font in parts:
            draw.text((x, y), c, font=font, fill='black')
            x += draw.textlength(c, font=font)
    mixed(title + '（' + denominator + '）', 700, 20, 26)
    top, bottom, left, right = 110, 440, 110, 1360
    maxv = max(max(values) for _, values in groups) * 1.2 + 1
    draw.line((left, top, left, bottom, right, bottom), fill='#66717c', width=2)
    for tick in range(5):
        y = bottom - (bottom-top)*tick/4
        draw.line((left, y, right, y), fill='#e0e4e8', width=1)
        draw.text((left-12, y), str(round(maxv*tick/4)), font=num, fill='black', anchor='rm')
    width = (right-left)/len(labels)
    colors = ['#64748b', '#648ba8']
    for i, label in enumerate(labels):
        center = left + width*(i+.5)
        for j, (name, values) in enumerate(groups):
            value = values[i]; x = center + (j-(len(groups)-1)/2)*65
            y = bottom-(bottom-top)*value/maxv
            draw.rectangle((x-26, y, x+26, bottom), fill=colors[j % len(colors)])
            draw.text((x, y-8), str(value), font=num, fill='black', anchor='ms')
        mixed(label, center, bottom+12, 22)
    if len(groups)>1:
        for j, (name, _) in enumerate(groups):
            x = 490 + j*220
            draw.rectangle((x, 515, x+20, 535), fill=colors[j % len(colors)])
            draw.text((x+30, 510), name, font=small, fill='black')
    image.save(path, dpi=(190,190))


def main():
    stamp = datetime.now().strftime('%Y年%m月%d日%H:%M（北京时间）')
    qp, q = latest('FQ_LEARN/K0')
    fp, f = latest('FFS')
    outputs = []
    for period, _ in PERIODS:
        stem = 'CLE-RPT-' + period + '-weekly-'
        src, dst = REPORTS / (stem + 'v05'), REPORTS / (stem + 'v06')
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src / 'figures', dst / 'figures', dirs_exist_ok=True)
        md = dst / (stem + 'v06.md')
        text = (src / (stem + 'v05.md')).read_text(encoding='utf-8')
        if period.startswith('20261014'):
            text = replace(text, '一次大规模比较中还有2题缺测，不能当作已测失败。', '')
            text = replace(text, '但旧Q在完整评价名单上没有表现出稳定优势。', '但旧Q在评价题对照中没有表现出稳定优势。')
            text = replace(text, '本周最后一条在线强化链已完成D_init全303题和D_grow的23/273题', '本周最后一条在线强化链已完成D_init全303题，并完成D_grow的23/273题')
        else:
            d = q['completed']; qf = q['first']; ql = q['final']; fcount = f['completed']; arms = f['arms']
            ev = dst / 'evidence'; ev.mkdir(exist_ok=True)
            (ev / 'd_init_snapshot.json').write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding='utf-8')
            (ev / 'function_security_snapshot.json').write_text(json.dumps(f, ensure_ascii=False, indent=2), encoding='utf-8')
            (ev / 'snapshot_sources.json').write_text(json.dumps({'captured_at':stamp,'q_source':str(qp),'ffs_source':str(fp)}, ensure_ascii=False, indent=2), encoding='utf-8')
            figure(dst/'figures/a9_q_learning.png', ['功能F','安全S','联合Joint'],
                   [('首次生成',[qf['functional'],qf['security'],qf['joint']]),('最终交付',[ql['functional'],ql['security'],ql['joint']])], 'D_init Q学习阶段的代码通过数', f'{d}题')
            figure(dst/'figures/a10_fs_progress.png', ['无卡','混合卡','功能视图','安全视图','分栏组合'],
                   [('已通过',[arms[k]['joint'] for k in ('B0','BM','BF','BS','BFS')])], '功能与安全全量对照的阶段Joint', f'{fcount}个已完成单元')
            text = text.replace('2026年10月27日15:56（北京时间）', stamp).replace('10月27日15:56', stamp.replace('2026年','').replace('（北京时间）',''))
            text = text.replace('D_init的63/303题', f'D_init的{d}/303题')
            text = replace(text, '；本周报告只登记计划，不自动派发。', '；已启动的项目持续执行，尚未启动的项目保留待做状态。')
            text = replace(text, 'Q学习已开始，D_init完成63/303题；题437的缺失选卡步骤已获直接补跑授权，仍等待允许的调用时段。旧失败和未知用量保留。', f'Q学习正在进行，D_init已完成{d}/303题；此前连接中断的请求已按授权从已保存位置恢复。旧失败及未知用量继续保留。')
            text = replace(text, '全298题五条件两重复的执行入口和分析已准备；真实代码实验尚未开始。', f'全298题五条件两重复的代码对照正在进行，已完成{fcount}/2980个实验单元，阶段读数见[【A10】](#a10)。')
            text = replace(text, 'v3.2可用接入和Base/Plus原验证环境仍需核对', 'v3.2已不可用，跨模型部分等待接入恢复；Base/Plus等待原验证环境')
            text = replace(text, 'Q学习、冻结回测、功能安全与五档等包已分别落实接线和预算。其余包仍待落实，旧结果的正式逐格抵扣仍未确认。', 'Q学习与功能安全全量对照已启动；冻结回测和五档等包已落实接线及预算。其余包仍待落实，旧结果的正式逐格抵扣仍未确认。')
            start = text.index('#### 目前看到了什么', text.index('<a id="a9"></a>'))
            end = text.index('[返回要求二](#r2)', start)
            pct = 100*q['Q_covered_cards']/q['card_count']
            update = f'''#### 目前看到了什么\n\n![图9 已完成{d}题的首次与最终代码通过数](figures/a9_q_learning.png)\n\n| 统计项目 | 已保存结果 |\n| --- | --- |\n| D_init完成题数 | {d}/303 |\n| 首次生成：F / S / Joint | {qf['functional']} / {qf['security']} / {qf['joint']}，完整测量{qf['measured']}题 |\n| 最终交付：F / S / Joint | {ql['functional']} / {ql['security']} / {ql['joint']}，完整测量{ql['measured']}题 |\n| 获得Q反馈的卡 | {q['Q_covered_cards']}/{q['card_count']}，{pct:.2f}% |\n| 有效反馈事件 / 声明采用卡位置 | {q['credited_events']} / {q['adopted_positions']} |\n| 已报告Token / 物理HTTP | {q['known_reported_tokens']:,} / {q['physical_HTTP']:,} |\n| 用量未知或在途HTTP | {q['unknown_or_inflight_HTTP']}，其中可能包含尚在处理的请求 |\n\n#### 这些结果说明什么\n\n这{d}题说明新模型已经在固定卡库上积累反馈：最终交付同时通过功能与安全测试{ql['joint']}题，{q['Q_covered_cards']}张卡获得反馈。首次和最终成绩用于观察本轮修复前后的变化，不能用于判断Q带来的收益，因为没有同题无Q对照。D_init尚未完成，D_grow三轮、冻结回测和D_gate四组对照尚未开始，不能据此判断最终迁移效果。\n\n数据来源：[D_init阶段摘要快照](evidence/d_init_snapshot.json)、[本周执行记录](../../CLE-RUN-20261027-full-requirements-v01.md)。\n\n'''
            text = text[:start] + update + text[end:]
            entries=[]
            for name,key in [('无卡','B0'),('原混合卡','BM'),('功能视图','BF'),('安全视图','BS'),('分栏组合','BFS')]:
                a=arms[key]; entries.append(f"| {name} | {a['completed']} | {a['measured']} | {a['functional']} | {a['security']} | {a['joint']} |")
            rows='\n'.join(entries)
            text += f'''\n\n<a id="a10"></a>\n### 【A10】功能与安全经验的全量对照进展\n\n#### 为什么做这项实验\n\n完整评价比较无卡、原混合卡、功能视图、安全视图和分栏组合，回答安全经验能否在保持功能的同时帮助通过安全测试。本轮固定298题，每组两次重复，共2980个实验单元。\n\n#### 怎样做\n\n1. 对每题准备相同公开题面和首次分析，带卡条件先使用同一组经验，再按条件呈现。\n2. 五组独立生成代码并接受原功能与安全验证；每个条件各做两次重复。\n3. 记录实际采用、代码落实、各项结果和调用成本，完成全部单元后按同题配对分析。\n\n#### 目前看到了什么\n\n![图10 功能与安全全量对照已完成单元的Joint通过数](figures/a10_fs_progress.png)\n\n| 条件 | 已完成单元 | 完整测量 | F通过 | S通过 | Joint通过 |\n| --- | --- | --- | --- | --- | --- |\n{rows}\n\n截至{stamp}，共完成{fcount}/2980个单元，已报告{f['known_reported_tokens']:,} Token、{f['physical_HTTP']:,}次物理HTTP；这些是该对照账本的累计口径，不能与其他可能重叠的账本直接相加。\n\n#### 这些结果说明什么\n\n图10展示的是执行中的阶段读数，各组完成和完整测量数量尚不完全相同，因此不能直接用当前通过数判断哪种经验更好。实验已经产生功能、安全和联合测试记录；完成全量后，重点检查功能损失是否伴随安全改善，并结合逐题代码解释原因。\n\n数据来源：[功能安全阶段摘要快照](evidence/function_security_snapshot.json)。\n\n[返回要求三](#r3)　[返回本周实验主线](#main)　[返回实验导航](#experiments)\n'''
            text = replace(text, '实际代码还显示，改写现有白名单等问题可能破坏功能，需要逐题区分原因。[【A3】](#a3) [【A6】](#a6)', f'实际代码还显示，改写现有白名单等问题可能破坏功能，需要逐题区分原因。全量对照已完成{fcount}个单元，仍在执行。[【A3】](#a3) [【A6】](#a6) [【A10】](#a10)')
        md.write_text(text, encoding='utf-8')
        outputs.append(str(md))
    print(json.dumps({'snapshot':stamp,'q_completed':q['completed'],'ffs_completed':f['completed'],'outputs':outputs}, ensure_ascii=True))


if __name__ == '__main__':
    main()
