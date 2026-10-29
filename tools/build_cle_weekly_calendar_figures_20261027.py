"""Figures for the calendar correction, from already reported measured counts."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT=Path(__file__).resolve().parents[1]/'docs/research/reports'
OLD=ROOT/'CLE-RPT-20261014-20261021-weekly-v01/figures'
NEW=ROOT/'CLE-RPT-20261022-20261028-weekly-v01/figures'
OLD.mkdir(exist_ok=True);NEW.mkdir(exist_ok=True)
font=Path('C:/Windows/Fonts/msyh.ttc')
font_manager.fontManager.addfont(str(font))
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),
                    'font.size':11,'axes.unicode_minus':False,'text.color':'black'})


def style(ax):
    ax.spines[['top','right']].set_visible(False)
    ax.yaxis.grid(True,color='#E5E7EB',linewidth=.6);ax.set_axisbelow(True)


def save(fig,path):
    fig.tight_layout(pad=.8);fig.savefig(path,dpi=190,facecolor='white');plt.close(fig)


fig,ax=plt.subplots(figsize=(7.1,3))
counts=[466,416,436,669,926,967,972]
labels=['早期\nD_grow','资格\n清理后','补32题\n后','D_init\n限三卡','D_init\n不限三卡','在线\nD_init','在线\nD_grow前23题']
bars=ax.bar(labels,[c/1939*100 for c in counts],color='#648BA8',width=.6)
for b,c in zip(bars,counts):ax.text(b.get_x()+b.get_width()/2,b.get_height()+2,f'{c}\n{c/1939:.2%}',ha='center',fontsize=9)
ax.set_ylim(0,70);ax.set_ylabel('有反馈卡占1939卡的比例（%）');style(ax);save(fig,OLD/'a1_coverage.png')

fig,ax=plt.subplots(figsize=(7.1,2.8))
vals=[97,104,102,100]
bars=ax.bar(['Q0 原CLE','Q1 相似度','Q2 学习Q','Q3 打乱Q'],[v/298*100 for v in vals],color=['#64748B','#648BA8','#648BA8','#94A3B8'],width=.55)
for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,b.get_height()+2,f'{v}/298\n{v/298:.2%}',ha='center')
ax.set_ylim(0,100);ax.set_ylabel('Joint通过率（%）');style(ax);save(fig,OLD/'a2_gate.png')

fig,axs=plt.subplots(1,2,figsize=(7.1,2.8))
for ax,labels,vals in [(axs[0],['成员变化','成员不变'],[281,15]),(axs[1],['救回','损失'],[16,9])]:
    bars=ax.bar(labels,vals,color=['#648BA8','#94A3B8'],width=.5)
    for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+.02*max(vals),str(v),ha='center')
    ax.set_ylim(0,max(vals)*1.25);ax.set_ylabel('题数');style(ax)
axs[0].set_title('可比较的296题');axs[1].set_title('采用新增卡的225题子集')
save(fig,OLD/'a3_selection.png')

fig,ax=plt.subplots(figsize=(7.1,2.8))
vals=[13,2,2,1];bars=ax.bar(['重定义已有配置','公开契约缺失','资源策略','网络'],vals,color='#648BA8',width=.55)
for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+.3,str(v),ha='center')
ax.set_ylim(0,16);ax.set_ylabel('损失题数');style(ax);save(fig,OLD/'a4_losses.png')

fig,ax=plt.subplots(figsize=(7.1,2.8))
vals=[89,385,285,153,2];bars=ax.bar(['直接适用','有条件适用','无关','冲突','信息不足'],vals,color='#648BA8',width=.55)
for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+8,str(v),ha='center')
ax.set_ylim(0,460);ax.set_ylabel('AI标注题卡对数');style(ax);save(fig,OLD/'a5_labels.png')

fig,axs=plt.subplots(1,2,figsize=(7.1,3))
for ax,labels,vals,n,title in [(axs[0],['P3 无经验'],[96],298,'P3完整PLT'),(axs[1],['P7空卡','P7旧卡'],[7,8],24,'P7局部迁移 两次重复')]:
    bars=ax.bar(labels,[v/n*100 for v in vals],color=['#64748B','#648BA8'][:len(vals)],width=.5)
    for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,b.get_height()+3,f'{v}/{n}\n{v/n:.2%}',ha='center')
    ax.set_ylim(0,100);ax.set_title(title);ax.set_ylabel('Joint通过率（%）');style(ax)
save(fig,NEW/'a8_baselines.png')
