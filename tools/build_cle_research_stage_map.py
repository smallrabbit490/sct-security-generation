"""从实验清单与只读运行快照生成可跳转SVG、draw.io源图和状态清单。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
import html
import json
import math
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/research/diagrams'
RUN=Path('E:/ResearchRuns/CLE/20261027_full_requirements')
INVENTORY=ROOT/'docs/research/reports/CLE-RPT-20261028-experiment-inventory-v02/CLE已做与未做实验清单_20261028_v02.docx'
BOARD='CLE_课题线索阶段与实验总图_v1.0'
LIST='CLE_实验状态与阶段说明清单_v1.0'
FONT='Times New Roman, SimSun, serif'
STATES={
 'done':('已完成','#166534','#dcfce7','#f0fdf4'),
 'running':('运行中','#c2410c','#ffedd5','#fff7ed'),
 'recovering':('自动恢复','#b45309','#fef3c7','#fffbeb'),
 'todo':('待做','#1d4ed8','#dbeafe','#eff6ff'),
 'conditional':('条件触发','#7e22ce','#f3e8ff','#faf5ff'),
 'external':('外部待办','#be123c','#ffe4e6','#fff1f2'),
 'ended':('已结束','#64748b','#e2e8f0','#f1f5f9')}
EXECUTORS={'API':('#1d4ed8','#dbeafe'),'Codex分析':('#7e22ce','#f3e8ff'),
           '人工复核':('#92400e','#fef3c7'),'原验证环境':('#475569','#e2e8f0')}
PHASES=[
 ('S0','提出研究问题','把想法写成能检验的问题'),
 ('S1','固定方案与离线核对','名单、对照、契约、预算与验证器'),
 ('S2','技术与机制探针','流程可用、干预是否真正发生'),
 ('S3','抽样探索','定位机制、筛选表达、形成标签'),
 ('S4','完整学习或建库','积累反馈并冻结可用资产'),
 ('S5','冻结全量对照','同题比较，回答主要研究问题'),
 ('S6','分析与结论','复算、读代码、判定并交付')]
TRACKS=[
 ('Q','Q评分能否提高正确率？','先确认改选，再检验同题收益与跨题族迁移。','#2563eb'),
 ('FS','怎样兼顾功能与安全？','分别检查接口保持、安全修复及两者共同通过。','#0f766e'),
 ('GR','题目需要哪种记忆程度？','用真实档位结果训练简单路由，再与固定策略比较。','#7c3aed'),
 ('FR','检索到的卡是否适用？','共同候选池逐卡标注，区分召回、终选与适用性。','#c2410c'),
 ('CROSS','模型与经验来源怎样配合？','固定生成模型，比较无卡、旧库和新库。','#be185d')]

# 编号沿用用户已确认的37项实验清单；阶段表示其主要证据用途。
META={
 'A01':('Q',4,'不限三卡的增长学习与回测','273题学习＋273题冻结回测',[],['API','Codex分析']),
 'A02':('Q',4,'初始化集两种上限学习','303题初始化集；两种上限',[],['API','Codex分析']),
 'A03':('Q',5,'旧模型全审计集Q四臂','298题×4臂；历史单重复',['A01','A02'],['API','Codex分析']),
 'A04':('Q',2,'重复选卡与实际采纳复盘','重复选卡；核对具体卡号',['A03'],['API','Codex分析']),
 'A05':('FS',6,'十八道损失题代码复盘','18道损失题；逐题读代码',['A03'],['Codex分析']),
 'A06':('FR',3,'历史检索与公开契约修复','199道检索任务；914对AI标签',[],['API','Codex分析']),
 'A07':('CROSS',5,'新模型P3无经验基线','298题全部交付；297题可测',[],['API','Codex分析']),
 'A08':('CROSS',2,'旧1939卡迁移探针','12题×2条件×2次＝48次',['A07'],['API','Codex分析']),
 'A09':('FS',2,'文件与签名关系提醒','8次共享生成起点对照',['A08'],['API','Codex分析']),
 'A10':('FS',3,'功能安全五组小对照','12题×5条件×2次＝120次',['A09'],['API','Codex分析']),
 'A11':('FS',3,'接口保护与来源经验','24题×2次＝48次',['A08'],['API','Codex分析']),
 'A12':('FS',3,'生成阶段功能保持提醒','72次生成提醒对照',['A11'],['API','Codex分析']),
 'A13':('FS',3,'公开要求自生成检查','192次公开契约消费者对照',['A09'],['API','Codex分析']),
 'A14':('GR',3,'五档经验详细程度比较','48题×5档×2次＝480次',['A08'],['API','Codex分析']),
 'A15':('GR',3,'真实标签分类器小对照','24题×3策略×2次＝144逻辑格',['A14'],['API','Codex分析']),
 'A16':('Q',2,'Q四臂五次重复选卡','8题×4臂×5次＝160选卡单元',['A08'],['API','Codex分析']),
 'A17':('Q',3,'新模型消费旧Q','24题×4臂×2次＝192次',['A16'],['API','Codex分析']),
 'A18':('FS',3,'同一代码的反事实编辑','24次共享代码起点编辑',['A10'],['API','Codex分析']),
 'A19':('FS',3,'来源经验保留题确认','24题×2条件×2次＝96次',['A11'],['API','Codex分析']),
 'A20':('Q',4,'初始化全量Q学习K0','303题；Q从零开始',['A17'],['API','Codex分析']),
 'A21':('Q',4,'增长第一轮Q学习K1','273题；从K0顺序接续',['A20'],['API','Codex分析']),
 'B01':('Q',4,'增长第二轮Q学习K2','273题；从K1接续',['A21'],['API','Codex分析']),
 'B02':('FS',5,'全量功能安全五组对照','298题×5条件×2次＝2980次',['A10','A18'],['API','Codex分析']),
 'C01':('Q',4,'增长第三轮Q学习K3','273题；从K2接续',['B01'],['API','Codex分析']),
 'C02':('Q',5,'冻结Q同题回测','1416次；主比较273题，中间54题',['C01'],['API','Codex分析']),
 'C03':('Q',5,'最终Q全量迁移四臂','298题×4臂×2次＝2384次',['C02'],['API','Codex分析']),
 'C04':('GR',3,'五档记忆首批82题','82题×5档×2次＝820次',['B02'],['API','Codex分析']),
 'C05':('GR',4,'分类器训练与冻结','82题或164题标签；离线训练',['C04'],['Codex分析']),
 'C06':('GR',5,'全量记忆路由三策略','298题×3策略×2次＝1788逻辑格',['C05'],['API','Codex分析']),
 'C07':('FR',3,'检索首批57题AI盲标','增长27题＋审计30题',['C04','B02','C10'],['API','Codex分析']),
 'C08':('FR',6,'人工复核与正式指标','逐题完整候选池；人工确认',['C07'],['人工复核','Codex分析']),
 'C09':('CROSS',4,'v4.1从空库完整建卡','原CLE三轮、主动回放及门控',['C06'],['API','Codex分析']),
 'C10':('CROSS',5,'v4.1无卡、旧库、新库','298题×3条件×2次＝1788逻辑格',['C09','B02'],['API','Codex分析']),
 'C11':('CROSS',5,'Base与Plus卡库外部验证','115＋140题；v4.1三库两重复',['C09'],['API','原验证环境']),
 'C12':('CROSS',5,'Base与Plus无经验P3','115＋140题；原P3流程',['A07'],['API','原验证环境']),
 'D01':('Q',6,'旧模型在线强化剩余项','旧模型已停用；不再派发',['A01','A02'],['API']),
 'D02':('CROSS',6,'旧模型反向卡库交叉','v3.2不可用；不替换模型',['C09'],['API'])}


def read_inventory():
    with zipfile.ZipFile(INVENTORY) as z:
        root=ET.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    entries={};current=None
    for paragraph in root.findall('.//w:p',ns):
        value=''.join(n.text or '' for n in paragraph.findall('.//w:t',ns))
        if value.startswith('名称：'):
            current=value[3:6];entries[current]={'full_name':value[7:]}
        elif current and '：' in value:
            name,text=value.split('：',1)
            if name in ('目的','实验步骤','结果分析','预测结果分析'):
                entries[current][name]=text
    if set(entries)!=set(META):
        raise ValueError('inventory_mapping_must_cover_all37_once')
    return entries


def status_snapshot(path=None):
    if path:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    with urllib.request.urlopen('http://127.0.0.1:8772/api/status',timeout=20) as response:
        raw=json.load(response)
    if not raw.get('packages'):
        raise ValueError('workbench_initializing_retry_after_first_collection')
    return {'time':raw['time'],'workers':raw['workers'],
        'packages':[{k:p.get(k) for k in ('key','status','completed','planned','stages')} for p in raw['packages']],
        'tasks':[{k:t.get(k) for k in ('id','status','reason','execution')} for t in raw.get('autonomy',{}).get('tasks',[])]}


def build_items(snapshot):
    entries=read_inventory()
    packages={p['key']:p for p in snapshot['packages']}
    tasks={t['id']:t for t in snapshot.get('tasks',[])}
    items=[]
    special={
      'C02':('FQ_RETEST','Q.retest'),'C03':('FQ_GATE','Q.gate'),
      'C04':('FG_LABELS','GR.labels'),'C05':('FG_TRAIN','GR.train'),
      'C06':('FG_GATE','GR.gate'),'C07':('FR','FR.run'),
      'C09':('BUILD_C41','BUILD.run'),'C10':('FX_GATE','CROSS.v41'),
      'C11':('FX_EXTERNAL','EXTERNAL.v41'),'C12':('P3_EXTERNAL','P3.external')}
    for identity,meta in META.items():
        track,phase,title,scale,depends,actors=meta
        item={**entries[identity],'id':identity,'track':track,'phase':phase,'title':title,
            'scale':scale,'depends':depends,'actors':actors,'core':True,
            'state':'done' if identity.startswith('A') else 'ended' if identity.startswith('D') else 'todo',
            'detail':entries[identity].get('结果分析') or entries[identity].get('预测结果分析',''),
            'href':LIST+'.svg#'+identity,'evidence':'../reports/CLE-RPT-20261028-experiment-inventory-v02/'+INVENTORY.name,
            'next':'保存原记录，作为后续对照与原因复盘的依据。'}
        if identity in ('A20','A21','B01','C01'):
            stage={'A20':'K0','A21':'K1','B01':'K2','C01':'K3'}[identity]
            current=packages.get('FQ_LEARN',{}).get('stages',{}).get(stage,{})
            count=current.get('completed',0);planned=303 if stage=='K0' else 273
            item['progress']=f'{count}/{planned}题次'
            item['state']='done' if current.get('status')=='completed' and count==planned else 'recovering' if count and current.get('status') in ('needs_technical_recovery','interrupted') else 'running' if count else 'todo'
            item['detail']=(f"已执行{count}/{planned}题次；Joint {current.get('final',{}).get('joint',0)}；Q反馈卡{current.get('Q_covered_cards',0)}/1939。学习过程成绩不替代冻结对照。" if count else '等待前轮完成并冻结；按原顺序继续第三轮。')
            item['evidence']='../CLE-TODO-20261022-20261028-v04.md'
            item['next']='完成本轮全部题目，冻结Q，零API回放并阅读案例。'
        if identity=='B02':
            p=packages['FFS'];item.update(progress=f"{p['completed']}/{p['planned']}次",state='done' if p['status']=='completed' else 'recovering' if p['status'] in ('needs_technical_recovery','interrupted') else 'running' if p['completed'] else 'todo',
                detail='无卡、混合、功能、安全、功能安全分栏五条件；同题两重复。已完成部分保留，继续补齐固定矩阵。',
                next='完成2980次后回放，比较Joint、功能损失与安全救回。',evidence='../CLE-TODO-20261022-20261028-v04.md')
        if identity in special:
            package,task=special[identity];p=packages.get(package,{});t=tasks.get(task,{})
            item['task_id']=task
            if p.get('completed'):item['progress']=f"{p['completed']}/{p.get('planned') or '按原协议'}"
            elif item['state']=='todo':item['progress']='尚未开始'
            if t.get('status')=='completed':item['state']='done'
            if t.get('status')=='running' or p.get('status')=='running':item['state']='running'
            if t.get('execution')=='not_required_by_protocol':item['state']='ended';item['detail']='工程扩大条件未满足，按减量协议结束此分支；未生成实验成绩。'
            item['evidence']='../../../configs/cle_weekly_reduced_20261028/README.md'
        if identity=='C02':item.update(detail='Q1及最终K3各273题，中间K0/K1/K2同54题，各两重复，共1416次；冻结Q只读。',
            next='K0—K3学习、回放与分析齐备后运行；中间轮不自动扩大。')
        if identity=='C03':item['next']='同题回测完整回放分析后，执行全298题四臂；Q2对Q1/Q3作主要比较。'
        if identity=='C04':item.update(next='有多档差异但训练条件不足才追加82题；就绪后训练与全量验证。',
            detail='首批82题、820次。训练标签需覆盖30个family，至少两类各5个训练family，分类器非常量且开发路由至少两档。')
        if identity=='C05':item.update(next='先按预登记规则判断82或164题标签是否就绪，再离线训练并冻结。',
            detail='只使用本轮真实标签；训练与开发按family隔离。标签不就绪时结束该分支，不伪造分类器成绩。')
        if identity=='C06':item['next']='新分类器就绪并冻结后全量评价；未就绪则按协议不执行。'
        if identity=='C07':item.update(next='缺主要CWE覆盖或区间过宽时追加57题；累计114题后结束扩大。',
            detail='首批增长27题、审计30题；三查询候选联集加随机16，逐题完整池盲标。AI只作模型辅助估计。')
        if identity=='C08':item.update(state='external',progress='人工确认待做',next='AI复核材料齐备后人工逐对确认，导入后复算候选池正式指标。',
            detail='AI标签与人工标签独立保存；人工未确认不代签，整库召回率不由抽样推定。')
        if identity in ('C11','C12'):
            item.update(state='external',progress='等待原验证镜像',next='原镜像及正向校准就绪后执行；隐藏反馈不回传训练。',
                evidence='../CLE-TODO-20261022-20261028-v04.md')
        if identity=='C09':item['next']='按既定队列等待前序分析；从空库完成原CLE三轮、回放和全局门控。'
        if identity=='C10':item['next']='新库与来源分析完成后执行v4.1三条件；精确匹配格复用，v3.2臂结束。'
        if identity.startswith('D'):item['next']='v3.2已停用，保留历史结果；本轮不再派发。'
        items.append(item)
    for identity,parent,track,phase,title,scale,task,detail in [
        ('C04E','C04','GR',3,'条件扩展：再加82题','再820次；累计164题','GR.extra','有至少两种首选档且存在干预，但训练工程条件不足时扩大；只扩大一次。'),
        ('C07E','C07','FR',3,'条件扩展：再加57题','累计114题；不重标首批','FR.extra','主要CWE未覆盖，或任一召回区间半宽>0.10、有效正类任务<20时扩大；只扩大一次。')]:
        t=tasks.get(task,{})
        state='conditional'
        if t.get('execution')=='not_required_by_protocol':state='ended'
        elif t.get('status')=='running':state='running'
        elif t.get('status')=='completed':state='done'
        items.append({'id':identity,'parent':parent,'full_name':title,'title':title,'track':track,'phase':phase,'scale':scale,
            'state':state,'depends':[parent],'actors':['API','Codex分析'],'core':False,'detail':detail,
            '目的':'仅在预登记条件满足时增加信息；不重做首批。','实验步骤':'首批完成→回放和案例分析→零API规则判断→必要时只运行新增名单。',
            'next':detail,'href':LIST+'.svg#'+identity,'evidence':'../../../configs/cle_weekly_reduced_20261028/README.md'})
    return items


def length(text,size):
    return sum(size if ord(ch)>255 else size*.53 for ch in text)


def wrap(text,width,size,max_lines=None):
    lines=[];line=''
    for ch in str(text):
        if ch=='\n' or length(line+ch,size)>width:
            lines.append(line);line='' if ch=='\n' else ch
        else:line+=ch
    if line:lines.append(line)
    if max_lines and len(lines)>max_lines:
        lines=lines[:max_lines]
        while length(lines[-1]+'…',size)>width:lines[-1]=lines[-1][:-1]
        lines[-1]+='…'
    return lines


class Diagram:
    """同一几何模型先写原生draw.io，再导出含可编辑模型的纯SVG。"""
    def __init__(self,width,height,name):
        self.width,self.height,self.name=width,height,name
        self.nodes=[];self.links=[];self.counter=0;self.bounds=[]

    def rect(self,x,y,w,h,fill='#fff',stroke='none',rx=8,id=None,dash=False,href=None,title=None):
        self.nodes.append(dict(kind='rect',x=x,y=y,w=w,h=h,fill=fill,stroke=stroke,rx=rx,id=id,dash=dash,href=href,title=title))

    def text(self,x,y,value,size=20,color='#0f172a',bold=False,width=None,lines=None,href=None,id=None):
        parts=wrap(value,width,size,lines) if width else str(value).split('\n')
        for i,part in enumerate(parts):
            self.nodes.append(dict(kind='text',x=x,y=y+i*size*1.35,text=part,size=size,color=color,bold=bold,href=href,id=id if i==0 else None))
        return len(parts)*size*1.35

    def line(self,points,color='#94a3b8',dash=False,source=None,target=None):
        self.links.append(dict(kind='line',points=points,color=color,dash=dash,source=source,target=target))

    def badge(self,x,y,text,state=None,actor=None,width=None):
        if state:label,color,fill,_=STATES[state];text=text or label
        else:color,fill=EXECUTORS[actor]
        w=width or length(text,17)+22
        self.rect(x,y,w,25,fill,color,4)
        self.text(x+10,y+18,text,17,color,True)
        return w

    def export(self,stem):
        mx=ET.Element('mxfile',host='drawio',version='26.0.0')
        page=ET.SubElement(mx,'diagram',id='cle-research',name=self.name)
        model=ET.SubElement(page,'mxGraphModel',page='1',pageScale='1',pageWidth=str(self.width),pageHeight=str(self.height),grid='0')
        root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
        geometries={};rectangles=[]
        for index,n in enumerate(self.nodes):
            identity=n.get('id') or f'n{index}'
            if n['kind']=='rect':
                style=f"rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor={n['fill']};strokeColor={n['stroke']};dashed={int(n['dash'])};container=1;collapsible=0;"
                value='';x,y,w,h=n['x'],n['y'],n['w'],n['h']
            else:
                style=f"text;html=1;align=left;verticalAlign=middle;spacing=0;fontFamily=SimSun;fontSize={n['size']};fontColor={n['color']};fontStyle={1 if n['bold'] else 0};"
                value=n['text'];x,y=n['x'],n['y']-n['size'];w,h=length(value,n['size'])+5,n['size']*1.25
            containing=[r for r in rectangles if r[1]<=x+.1 and r[2]<=y+.1 and r[1]+r[3]>=x+w-.1 and r[2]+r[4]>=y+h-.1]
            parent=min(containing,key=lambda r:r[3]*r[4]) if containing else None
            attributes={'id':identity,'parent':parent[0] if parent else '1','vertex':'1','value':value,'style':style}
            if n.get('href'):attributes['link']=n['href']
            cell=ET.SubElement(root,'mxCell',attributes)
            ET.SubElement(cell,'mxGeometry',x=str(x-parent[1] if parent else x),y=str(y-parent[2] if parent else y),width=str(w),height=str(h),attrib={'as':'geometry'})
            geometries[identity]=(x,y,w,h)
            if n['kind']=='rect':rectangles.append((identity,x,y,w,h))
        for index,n in enumerate(self.links):
            points=n['points'];attrs={'id':f'edge{index}','parent':'1','edge':'1','style':f"edgeStyle=orthogonalEdgeStyle;html=1;endArrow=classic;strokeColor={n['color']};dashed={int(n['dash'])};"}
            if n.get('source'):attrs['source']=n['source']
            if n.get('target'):attrs['target']=n['target']
            for side,point,prefix in [('source',points[0],'exit'),('target',points[-1],'entry')]:
                if n.get(side) in geometries:
                    bx,by,bw,bh=geometries[n[side]]
                    fx=min(1,max(0,(point[0]-bx)/bw));fy=min(1,max(0,(point[1]-by)/bh))
                    attrs['style']+=f'{prefix}X={fx};{prefix}Y={fy};{prefix}Perimeter=0;'
            cell=ET.SubElement(root,'mxCell',attrs)
            geometry=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'})
            ET.SubElement(geometry,'mxPoint',x=str(points[0][0]),y=str(points[0][1]),attrib={'as':'sourcePoint'})
            ET.SubElement(geometry,'mxPoint',x=str(points[-1][0]),y=str(points[-1][1]),attrib={'as':'targetPoint'})
            if len(points)>2:
                array=ET.SubElement(geometry,'Array',attrib={'as':'points'})
                for x,y in points[1:-1]:ET.SubElement(array,'mxPoint',x=str(x),y=str(y))
        source=ET.tostring(mx,encoding='unicode')
        (OUT/(stem+'.drawio')).write_text(source,encoding='utf-8')
        svg=ET.Element('svg',xmlns='http://www.w3.org/2000/svg',width=str(self.width),height=str(self.height),viewBox=f'0 0 {self.width} {self.height}',content=source,role='img')
        ET.SubElement(svg,'title').text=self.name
        ET.SubElement(svg,'desc').text='七阶段研究流程与实验状态。绿色完成，橙色运行，蓝色待做，紫色条件扩展，红色外部待办，灰色结束。点击编号查看对应实验。'
        defs=ET.SubElement(svg,'defs');marker=ET.SubElement(defs,'marker',id='arrow',viewBox='0 0 10 10',refX='9',refY='5',markerWidth='7',markerHeight='7',orient='auto-start-reverse')
        ET.SubElement(marker,'path',d='M 0 0 L 10 5 L 0 10 z',fill='#94a3b8')
        # 背景先绘；连线置于文字与卡片下方，避免覆盖内容。
        def add(n):
            parent=svg
            if n.get('href'):parent=ET.SubElement(parent,'a',href=urllib.parse.quote(n['href'],safe='/#:.?=&'),target='_blank' if n['href'].endswith(('.md','.docx')) else '_self')
            if n['kind']=='rect':
                attrs={'x':str(n['x']),'y':str(n['y']),'width':str(n['w']),'height':str(n['h']),'rx':str(n['rx']),'fill':n['fill'],'stroke':n['stroke'],'stroke-width':'1.5'}
                if n['dash']:attrs['stroke-dasharray']='7 5'
                if n.get('id'):attrs['id']=n['id']
                element=ET.SubElement(parent,'rect',attrs)
                if n.get('title'):ET.SubElement(element,'title').text=n['title']
            else:
                attrs={'x':str(n['x']),'y':str(n['y']),'font-size':str(n['size']),'fill':n['color'],'font-family':FONT,'font-weight':'700' if n['bold'] else '400'}
                if n.get('id'):attrs['id']=n['id']
                ET.SubElement(parent,'text',attrs).text=n['text']
        # 前十几个背景之后插入线路；其余卡片绘制在上层。
        backgrounds=[n for n in self.nodes if n.get('background')]
        for n in backgrounds:add(n)
        for n in self.links:
            path='M '+' L '.join(f'{x} {y}' for x,y in n['points'])
            attrs={'d':path,'fill':'none','stroke':n['color'],'stroke-width':'2','marker-end':'url(#arrow)','opacity':'.55'}
            if n['dash']:attrs['stroke-dasharray']='7 5'
            ET.SubElement(svg,'path',attrs)
        for n in self.nodes:
            if not n.get('background'):add(n)
        ET.indent(svg)
        (OUT/(stem+'.svg')).write_text(ET.tostring(svg,encoding='unicode'),encoding='utf-8')
        return svg

    def background(self,*args,**kwargs):
        self.rect(*args,**kwargs);self.nodes[-1]['background']=True


def legend(diagram,x,y,counts):
    for state in STATES:
        name=STATES[state][0];w=diagram.badge(x,y,f'{name} {counts.get(state,0)}',state=state)
        x+=w+16


def draw_card(d,item,x,y,w,h=174):
    state=item['state'];label,color,fill,bg=STATES[state]
    text=f"{item['id']} {item['full_name']}\n目的：{item.get('目的','')}\n规模：{item['scale']}\n{item['detail']}\n下一步：{item['next']}"
    d.rect(x,y,w,h,bg,color,8,id=item['id'],dash=state in ('conditional','external','ended'),href=item['href'],title=text)
    d.rect(x,y,5,h,color,color,2)
    d.text(x+14,y+25,item['id'],19,color,True,href=item['href'])
    badge_width=length(label,17)+22;d.badge(x+w-badge_width-12,y+9,label,state=state)
    d.text(x+14,y+55,item['title'],23,'#0f172a',True,width=w-28,lines=2)
    progress=(item['progress']+' · '+item['scale']) if item.get('progress') else item['scale']
    d.text(x+14,y+103,progress,18,'#334155',width=w-28,lines=2)
    ax=x+14
    for actor in item['actors']:
        ax+=d.badge(ax,y+h-52,actor,actor=actor)+9
    d.text(x+14,y+h-10,'前置：'+(' / '.join(item['depends']) or '已登记研究要求'),16,'#64748b',width=w-28,lines=1)
    d.bounds.append((item['id'],x,y,w,h))


def board(items,snapshot):
    widths=[360,430,470,550,550,600,530];gap=20;margin=34
    xs=[];x=margin
    for width in widths:xs.append(x);x+=width+gap
    width=x-gap+margin
    order={name:i for i,(name,*_) in enumerate(TRACKS)}
    grouped={phase:sorted([i for i in items if i['phase']==phase],key=lambda i:(order[i['track']],i['id'])) for phase in range(2,7)}
    stride=190;rows_top=414
    height=rows_top+max(len(v) for v in grouped.values())*stride+390
    d=Diagram(width,height,'CLE研究线索、阶段与实验状态')
    d.background(0,0,width,height,'#f8fafc',rx=0)
    d.background(margin-8,274,xs[4]-margin+3,height-620,'#eaf2ff',rx=14)
    d.background(xs[4]-8,274,widths[4]+widths[5]+gap+16,height-620,'#fff3d6',rx=14)
    d.background(xs[6]-8,274,widths[6]+16,height-620,'#e9f8ee',rx=14)
    d.text(36,57,'CLE｜从研究线索到全量验证',44,bold=True)
    d.text(38,98,'沿七阶段积累证据：先提出问题与固定方案，再探索、学习、全量比较，最后分析结论。',25,'#475569')
    d.text(38,137,f"状态截至 {snapshot['time'].replace('T',' ')}  ·  37项核心实验＋2个条件扩展  ·  点击实验编号跳转清单",23,'#475569')
    legend(d,38,159,Counter(i['state'] for i in items))
    d.text(38,226,'执行标签',21,'#475569',True);lx=150
    for actor in EXECUTORS:lx+=d.badge(lx,205,actor,actor=actor)+14
    d.text(38,264,'颜色表示状态，Q / FS / GR / FR / CROSS表示研究线索；前置条件与执行队列决定何时开展。',22,'#475569')
    for index,(code,name,explanation) in enumerate(PHASES):
        d.rect(xs[index],292,widths[index],80,'#0f172a',rx=9)
        d.text(xs[index]+16,326,code+' · '+name,26,'#fff',True,width=widths[index]-26,lines=1)
        d.text(xs[index]+16,354,explanation,19,'#cbd5e1',width=widths[index]-26,lines=1)
        if index<6:d.line([(xs[index]+widths[index]+2,328),(xs[index+1]-4,328)])
    d.text(40,402,'已完成包含正结果与负结果；“待做”与“条件触发”不代表实验失败。主要路径用细线连接，全部前置写在卡片中。',23,'#475569')
    specs={
      'Q':['固定1939卡正文、Q从零','初始化303＋增长273×3轮','最终Q对相似度及打乱Q'],
      'FS':['同题同候选，五种表达','功能、安全与Joint分别报告','完整298题、两次独立重复'],
      'GR':['五档共用1924张合格卡','训练/开发按family隔离','首批82题，最多扩到164题'],
      'FR':['三查询Top24＋词面Top8','每题补随机16张未召回卡','首批57题，最多扩到114题'],
      'CROSS':['新旧库各自记录来源','同一P7比较无卡/旧库/新库','v3.2结束；外部集等原镜像']}
    judgments={
      'Q':'已确认Q改变卡号与采用；最终新Q的同题和迁移收益，等待冻结比较。',
      'FS':'小范围分栏未提高Joint；当前完成全量五条件，检验功能损失与安全救回。',
      'GR':'旧分类器未超过固定提醒；先形成有效标签，再检验新路由是否提高Joint。',
      'FR':'已有AI初标和契约修复；首批57题提供样本估计，正式指标需要人工确认。',
      'CROSS':'旧卡向新模型的迁移已小测；新库尚待建立，旧模型反向比较已结束。'}
    locations={}
    for n,(track,question,why,color) in enumerate(TRACKS):
        yy=rows_top+n*260
        d.rect(xs[0]+8,yy,widths[0]-16,215,'#fff',color,9,id='question-'+track)
        d.text(xs[0]+23,yy+35,track+' · 研究问题',23,color,True)
        d.text(xs[0]+23,yy+78,question,27,color,True,width=widths[0]-46,lines=2)
        d.text(xs[0]+23,yy+148,why,21,'#475569',width=widths[0]-46,lines=2)
        d.rect(xs[1]+8,yy,widths[1]-16,215,'#fff',color,9,id='spec-'+track)
        d.text(xs[1]+23,yy+35,track+' · 怎样验证？',24,color,True)
        for k,value in enumerate(specs[track]):d.text(xs[1]+23,yy+80+k*42,f'{k+1}. '+value,22,'#334155',width=widths[1]-46,lines=1)
        d.rect(xs[6]+8,yy,widths[6]-16,215,'#fff',color,9,id='judgment-'+track)
        d.text(xs[6]+23,yy+35,track+' · 当前证据',24,color,True)
        d.text(xs[6]+23,yy+80,judgments[track],24,'#334155',width=widths[6]-46,lines=4)
        d.line([(xs[0]+widths[0]-6,yy+100),(xs[1]+4,yy+100)],color,source='question-'+track,target='spec-'+track)
        locations['spec-'+track]=(xs[1]+8,yy,widths[1]-16,215)
        locations['judgment-'+track]=(xs[6]+8,yy,widths[6]-16,215)
    for phase in range(2,7):
        offset=5*260+15 if phase==6 else 0
        for n,item in enumerate(grouped[phase]):
            yy=rows_top+offset+n*stride
            draw_card(d,item,xs[phase]+8,yy,widths[phase]-16,184)
            d.text(xs[phase]+78,yy+25,item['track'],17,'#475569',True)
            locations[item['id']]=(xs[phase]+8,yy,widths[phase]-16,184)
    paths=[('A16','A17'),('A17','A20'),('A20','A21'),('A21','B01'),('B01','C01'),('C01','C02'),('C02','C03'),
           ('A09','A10'),('A10','B02'),('A14','A15'),('A15','C04'),('C04','C04E'),('C04','C05'),('C05','C06'),
           ('A06','C07'),('C07','C07E'),('C07','C08'),('A08','C09'),('C09','C10'),
           ('spec-Q','A16'),('spec-FS','A09'),('spec-GR','A14'),('spec-FR','A06'),('spec-CROSS','A08'),
           ('C03','judgment-Q'),('B02','judgment-FS'),('C06','judgment-GR'),('C10','judgment-CROSS')]
    for a,b in paths:
        sx,sy,sw,sh=locations[a];tx,ty,tw,th=locations[b]
        if sx==tx:points=[(sx+sw*.90,sy+sh+1),(tx+tw*.90,ty-2)]
        elif tx-sx < sw+gap+30:
            gutter=(sx+sw+tx)/2
            points=[(sx+sw+2,sy+sh/2),(gutter,sy+sh/2),(gutter,ty+th/2),(tx-3,ty+th/2)]
        else:
            # 跨多列时从中间列卡片下方绕行，保持文字与任务框不被线路穿越。
            intermediate=[box[1]+box[3] for box in locations.values() if sx<box[0]<tx]
            lane=max([sy+sh/2,ty+th/2]+intermediate)+14
            left,right=sx+sw+gap/2,tx-gap/2
            points=[(sx+sw+2,sy+sh/2),(left,sy+sh/2),(left,lane),(right,lane),(right,ty+th/2),(tx-3,ty+th/2)]
        d.line(points,'#a78bfa' if b.endswith('E') else '#94a3b8',b.endswith('E'),a,b)
    footer=height-330
    panels=[('G1｜从探针进入正式执行','离线链路、契约、对照与预算就绪。技术探针验证流程；主要全量问题不因几道题的低分取消。','#eaf2ff'),
      ('G2｜何时扩大抽样？','记忆：有多档差异但工程标签不足，扩到164题。检索：覆盖或区间不足，扩到114题。只扩大一次。','#faf5ff'),
      ('G3｜何时算阶段完成？','补齐固定名单和独立重复，做原生回放、配对统计与代码复盘，再接下一项。未执行不记失败。','#e9f8ee')]
    panelw=(width-2*margin-36)/3
    for i,(title,text,fill) in enumerate(panels):
        px=margin+i*(panelw+18);d.rect(px,footer,panelw,166,fill,'#cbd5e1',9)
        d.text(px+20,footer+39,title,28,bold=True)
        d.text(px+20,footer+82,text,24,'#334155',width=panelw-40,lines=3)
    d.text(margin,footer+210,'读图：点击实验编号进入对应清单；鼠标停在卡片上可查看目的、当前证据与下一条件。',24,'#334155')
    d.text(margin,footer+250,'C04E与C07E是条件扩展，不计作新增核心研究。旧模型历史结果与新模型成绩分别保留。',23,'#475569')
    d.text(margin,footer+292,'完整状态与推进条件 → '+LIST+'.svg',23,'#1d4ed8',href=LIST+'.svg')
    d.export(BOARD)
    return d


def status_list(items,snapshot):
    width=2220;rowh=148;header=326;height=header+len(items)*rowh+230
    d=Diagram(width,height,'CLE实验状态、阶段与推进条件清单')
    d.background(0,0,width,height,'#f8fafc',rx=0)
    d.text(36,56,'CLE｜实验状态、阶段与推进条件',40,bold=True)
    d.text(38,94,'37项核心实验沿用原清单编号；新增2个条件扩展支路。每一项都有阶段、执行人、进度和推进条件。',22,'#475569')
    d.text(38,130,'状态截至 '+snapshot['time'].replace('T',' ')+'；历史完成项保留其原测量范围。',21,'#475569')
    legend(d,38,154,Counter(i['state'] for i in items))
    d.rect(34,203,width-68,62,'#eaf2ff',rx=9)
    d.text(52,240,'返回阶段总图 → 研究问题、七阶段与主要依赖路径',23,'#1d4ed8',True,href=BOARD+'.svg')
    columns=[38,595,790,1100,1618]
    for x,title in zip(columns,['实验名称与阶段','状态 / 执行人','规模 / 当前进度','结果或下一推进条件','查看依据']):
        d.text(x,300,title,23,'#334155',True)
    order={name:i for i,(name,*_) in enumerate(TRACKS)}
    ordered=sorted(items,key=lambda v:(order[v['track']],v['phase'],v['id']))
    for index,item in enumerate(ordered):
        y=header+index*rowh
        label,color,fill,bg=STATES[item['state']]
        d.rect(30,y,width-60,rowh-7,bg,'#dbe3ed',4,id=item['id'])
        d.rect(30,y,5,rowh-7,color,color,1)
        d.text(columns[0]+12,y+32,item['id']+'  '+item['title'],24,color,True,width=530,lines=2,href=BOARD+'.svg#'+item['id'])
        d.text(columns[0]+12,y+104,f"{item['track']} · {PHASES[item['phase']][0]} {PHASES[item['phase']][1]}",20,'#475569')
        d.badge(columns[1],y+14,label,state=item['state'])
        for k,actor in enumerate(item['actors']):d.badge(columns[1],y+52+k*32,actor,actor=actor)
        d.text(columns[2],y+34,item.get('progress') or item['scale'],22,'#334155',width=280,lines=3)
        if item.get('progress'):d.text(columns[2],y+111,item['scale'],16,'#64748b',width=280,lines=1)
        text=item['detail'] if item['state']=='done' else item['next']
        d.text(columns[3],y+32,text,20,'#334155',width=485,lines=4)
        d.text(columns[4],y+32,'原报告 / 当前协议 ↗',21,'#1d4ed8',href=item['evidence'])
        d.text(columns[4],y+70,'前置：'+(' / '.join(item['depends']) or '已登记要求'),18,'#475569',width=520,lines=2)
        d.text(columns[4],y+115,'阶段位置 ↗',19,'#1d4ed8',href=BOARD+'.svg#'+item['id'])
    y=height-188
    d.rect(32,y,width-64,155,'#fff','#cbd5e1',9)
    d.text(50,y+38,'状态解释',25,bold=True)
    d.text(50,y+75,'已完成：该实验已执行并形成记录，结果可以正向或反向。运行中：已有保存结果并继续执行。待做：尚未达到派发条件。',21,'#334155')
    d.text(50,y+110,'条件触发：按固定规则决定是否增加样本。外部待办：需要人工或原验证环境。已结束：旧模型停用，或扩大分支按协议关闭。',21,'#334155')
    d.export(LIST)
    return d


def validate(diagrams,items):
    for d,stem in zip(diagrams,[BOARD,LIST]):
        svg=ET.parse(OUT/(stem+'.svg')).getroot();native=ET.parse(OUT/(stem+'.drawio')).getroot()
        identifiers=[e.get('id') for e in svg.iter() if e.get('id')]
        if len(identifiers)!=len(set(identifiers)):raise ValueError('duplicate_SVG_id')
        for item in items:
            if identifiers.count(item['id'])!=1:raise ValueError('missing_or_duplicate_experiment:'+item['id'])
        ids=[c.get('id') for c in native.findall('.//mxCell')]
        if len(ids)!=len(set(ids)):raise ValueError('duplicate_drawio_cell_id')
        for n in d.nodes:
            if n['kind']=='rect' and (n['x']<0 or n['y']<0 or n['x']+n['w']>d.width+1 or n['y']+n['h']>d.height+1):
                raise ValueError('rectangle_outside_page')
        for a in svg.iter():
            href=urllib.parse.unquote(a.get('href',''))
            if not href:continue
            file,_,anchor=href.partition('#')
            target=OUT/file if file else OUT/(stem+'.svg')
            if not target.exists():raise ValueError('missing_link_target:'+href)
            if anchor:
                targetids={n.get('id') for n in ET.parse(target).getroot().iter()}
                if anchor not in targetids:raise ValueError('missing_anchor:'+href)
        for i,a in enumerate(d.bounds):
            for b in d.bounds[i+1:]:
                if min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1]) and min(a[2]+a[4],b[2]+b[4])>max(a[2],b[2]):
                    raise ValueError('overlapping_experiment_cards:'+a[0]+'/'+b[0])
    return {'status':'passed','core_experiments':37,'conditional_branches':2,
        'all_experiment_anchors_present':True,'all_local_links_and_anchors_resolved':True,
        'overlapping_experiment_cards':0,'new_experiment_API_calls':0}


def render_previews():
    """使用已配置的本地Sharp渲染预览，不安装依赖或启动浏览器窗口。"""
    runtime=Path('C:/Users/fujunye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node')
    code='''const sharp=require(process.argv[1]),path=require('path');
    (async()=>{for(const [name,out,width] of JSON.parse(process.argv[3])) {
      await sharp(path.join(process.argv[2],name),{limitInputPixels:false}).resize({width}).png().toFile(path.join(process.argv[2],out));
    }})().catch(e=>{console.error(e.message);process.exit(1)});'''
    files=[[BOARD+'.svg','cle-stage-map-preview.png',1900],[LIST+'.svg','cle-stage-list-preview.png',1350]]
    subprocess.run([str(runtime/'bin/node.exe'),'-e',code,str(runtime/'node_modules/sharp'),str(OUT),json.dumps(files)],check=True,capture_output=True,text=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    snapshot=status_snapshot(args.snapshot);items=build_items(snapshot)
    # 下次刷新只读取当前状态；不写回实验、守护或任务控制文件。
    (OUT/'CLE_阶段实验图_数据_v1.0.json').write_text(json.dumps({'snapshot':snapshot,'experiments':items},ensure_ascii=False,indent=2),encoding='utf-8')
    diagrams=[board(items,snapshot),status_list(items,snapshot)]
    validation=validate(diagrams,items)
    render_previews()
    validation.update(snapshot_time=snapshot['time'],states=dict(Counter(i['state'] for i in items if i['core'])))
    (OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(validation,ensure_ascii=False))


if __name__=='__main__':main()
