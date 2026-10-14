"""可审阅起点图及自主探索示例；示例不带实验成绩，不假冒模型生成结果。"""


def node(identifier, label, operation, inputs, description='', **kwargs):
    return {'id': identifier, 'label': label, 'operation': operation, 'inputs': inputs,
            'description': description, **kwargs}


def edge(source, target, label='', **kwargs):
    return {'source': source, 'target': target, 'label': label, **kwargs}


def initial_graph():
    """独立MASE起点：公开接口、合格M1、生成及选择；可被设计员拆改。"""
    return {'schema': 'mase-graph-v1', 'nodes': [
        node('memory', '来源记忆与适用判断', 'memory', ['public_task', 'memory_bank'], '其他训练family、来源质量合格；可以拒用'),
        node('generate', '按公开接口生成', 'llm', ['public_task', 'contract', 'memory'], '生成代码；不见官方评分',
             output='candidate', prompt='实现公开需求，保留接口和调用方对象，仅迁移兼容的安全机制。'),
        node('inspect', '公开接口检查', 'inspect', ['generate', 'contract'], '有限AST证据，不等于功能或安全证明'),
        node('repair', '有明确接口问题才修复', 'repeat', ['inspect','public_task','contract','memory'],
             '保留原候选；严格改善公开证据才继续，重复或停滞停止', only_on_problem=True,
             graph={'schema':'mase-graph-v1','nodes':[
                 node('fix','按具体违约修复','llm',['public_task','contract','iteration_candidate'],
                      output='candidate',prompt='Fix only confirmed interface/check issues of iteration_candidate. Preserve correct behavior and caller globals. Use compatible training memory if provided.'),
                 node('recheck','同组接口复查','inspect',['fix','contract']),
                 node('done','返回本轮候选','finish',['recheck'])],
                    'edges':[edge('fix','recheck'),edge('recheck','done')]}),
        node('finish', '固定最终代码', 'finish', ['repair'], '输出之后才允许官方事后评分')],
        'edges': [edge('memory', 'generate', '训练示例/拒用'), edge('generate', 'inspect', '候选代码'),
                  edge('inspect','repair','问题与原候选'),edge('memory','repair','修复时可用记忆'),
                  edge('repair', 'finish', '保留或修复后的代码')]}


def exploratory_graph():
    """人工设计草案展示更自由的图；没有声称此结构已经取得收益。"""
    return {'schema': 'mase-graph-v1', 'nodes': [
        node('analysis', '拆解公开需求', 'llm', ['public_task', 'contract'], '列出允许行为、输入与敏感操作', output='message'),
        node('plain', '独立无记忆生成员', 'llm', ['public_task', 'contract', 'analysis'], '作为可保留候选', output='candidate'),
        node('memory', '条件召回训练记忆', 'memory', ['public_task', 'memory_bank', 'analysis'], '匹配输入/操作而非只匹配CWE'),
        node('guided', '有记忆生成员', 'llm', ['public_task', 'contract', 'analysis', 'memory'], '仅迁移兼容机制', output='candidate'),
        node('plain_check', '共享公开检查 A', 'inspect', ['plain', 'contract', 'public_suite'], '实际运行相同检查'),
        node('guided_check', '共享公开检查 B', 'inspect', ['guided', 'contract', 'public_suite'], '与A使用相同证据'),
        node('select', '证据比较与保留', 'select', ['plain_check', 'guided_check'], '公开证据不足时保留原候选，不见官方分数'),
        node('finish', '固定最终输出', 'finish', ['select'], '统一评分器在旁路事后评估')],
        'edges': [edge('analysis','plain','需求'), edge('analysis','memory','敏感操作'), edge('analysis','guided','需求'),
                  edge('memory','guided','来源机制'), edge('plain','plain_check','代码A'), edge('guided','guided_check','代码B'),
                  edge('plain_check','select','相同检查A'), edge('guided_check','select','相同检查B'), edge('select','finish','选择与理由')]}


def historical_graph(architecture, memory):
    """从旧A7手写实现重建图用于浏览，明确不是自主设计或逐题完整执行日志。"""
    nodes = [node('memory','训练记忆：'+memory,'memory',['public_task','memory_bank'], '历史来源质量与适用判断；none时空记忆')]
    edges = []
    if architecture == 'choose':
        nodes.extend([
            node('plain','无记忆候选','llm',['public_task','contract'],output='candidate'),
            node('guided','第二份候选','llm',['public_task','contract','memory'],output='candidate'),
            node('a','接口修复与检查 A','inspect',['plain','contract'],description='旧实现内含接口修复循环'),
            node('b','接口修复与检查 B','inspect',['guided','contract'],description='旧实现内含接口修复循环'),
            node('select','同组公开证据选择','select',['a','b']),
            node('finish','固定输出','finish',['select'])])
        edges = [edge('memory','guided','训练示例'),edge('plain','a','代码'),edge('guided','b','代码'),
                 edge('a','select','候选A'),edge('b','select','候选B'),edge('select','finish','所选代码')]
    else:
        nodes.extend([
            node('generate','按公开接口生成','llm',['public_task','contract','memory'],output='candidate'),
            node('inspect','接口检查'+(' + 实际公开测试' if architecture == 'check' else ''),'inspect',['generate','contract'],
                 description='公开问题才触发修复，循环尝试存在历史public_attempts'),
            node('finish','固定输出','finish',['inspect'])])
        edges = [edge('memory','generate','训练示例/拒用'),edge('generate','inspect','候选'),edge('inspect','finish','检查/修复后的代码')]
    return {'schema':'mase-graph-v1','nodes':nodes,'edges':edges,'origin':'旧手写代码重建示意；调用trace仅阶段级'}
