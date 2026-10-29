"""九图的真实依赖、题数与新增零API分析接续检查。"""
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools import build_cle_horizontal_ideas as g
from tools.cle_live_workbench.autonomy import AutonomousPlan
from configs.cle_scientific_review_20261028.diagram_review import update_plan


class IdeaAuditTests(unittest.TestCase):
    def test_all_nine_have_mapped_text_and_experiments(self):
        specs = g.specifications()
        self.assertEqual(len(specs), 9)
        nodes = [n for s in specs for n in g.walk(s['root'])]
        self.assertEqual({n.key for n in nodes}, set(g.TASK_TEXT))
        self.assertEqual({e for n in nodes for e in n.experiments}, set(g.CARD_TEXT))

    def test_historical_and_current_evidence_are_separate(self):
        nodes = {n.key:n for s in g.specifications() for n in g.walk(s['root'])}
        self.assertEqual(nodes['f3'].experiments, ['A10'])
        self.assertEqual(nodes['f-interface'].experiments, ['A11'])
        self.assertEqual(nodes['f-confirm'].experiments, ['A19'])
        self.assertNotIn('A05', [e for n in g.walk(nodes['m5']) for e in n.experiments])
        self.assertEqual(nodes['m6'].experiments, ['R01'])
        self.assertEqual(nodes['s-human'].experiments, ['C08'])
        self.assertEqual(nodes['s-human'].children[0].key, 's6')
        self.assertEqual(nodes['t5'].children[0].key, 't5-gate')
        self.assertEqual(nodes['x5-external'].children[0].key, 'x6-external')

    def test_counts_and_layout(self):
        self.assertIn('12题×2种方式×2次',g.CARD_TEXT['A11'][2])
        self.assertIn('6题×2种方式×2次',g.CARD_TEXT['A18'][2])
        items = {k:dict(title=t, meaning=m, scale=s) for k,(t,m,s) in g.CARD_TEXT.items()}
        for spec in g.specifications():
            for n in g.walk(spec['root']):
                n.title,*n.text=g.TASK_TEXT[n.key]
            g.measure(spec['root'],items)
            xs=[];x=g.MARGIN
            for w in g.WIDTHS:
                xs.append(x);x+=w+g.GAP
            g.place(spec['root'],xs,312)
            g.verify(spec['root'])

    def test_narrative_anchors_and_unified_running_badges(self):
        narrative=(g.ROOT/'docs/research/CLE-STORY-20261028-nine-ideas.md').read_text(encoding='utf-8')
        self.assertEqual(len(g.STORY_LINES),9)
        self.assertEqual(g.base.STATES['running'],g.base.STATES['recovering'])
        self.assertEqual(g.base.STATES['running'][0],'正在运行')
        ns={'s':'http://www.w3.org/2000/svg'}
        for i,spec in enumerate(g.specifications(),1):
            anchor=f'idea{i:02d}'
            self.assertIn(f'id="{anchor}"',narrative)
            svg=ET.parse(g.OUT/(spec['stem']+'.svg')).getroot()
            links=[a.get('href') for a in svg.findall('.//s:a',ns)]
            self.assertIn(g.NARRATIVE+'#'+anchor,links)
            visible=''.join(t.text or '' for t in svg.findall('.//s:text',ns))
            self.assertNotIn('自动恢复',visible)
            self.assertNotIn('正在恢复',visible)
            self.assertNotIn('运行中',visible)

    def test_queue_keeps_active_experiments_and_adds_only_local_review(self):
        root=Path(__file__).resolve().parents[1]
        plan=json.loads((root/'tools/cle_live_workbench/autonomy_plan.json').read_text(encoding='utf-8'))
        updated=update_plan(plan)
        old={t['id']:t for t in plan['tasks']};new={t['id']:t for t in updated['tasks']}
        for key in ('Q.run','FS.run','Q.K0.analysis','Q.K1.analysis','BUILD.prepare','CROSS.prepare'):
            self.assertEqual(old[key],new[key])
        task=new['FS.single_edit']
        self.assertEqual(task['depends'],['FS.analysis'])
        self.assertEqual(task['kind'],'custom')
        self.assertEqual(task['diagram_review']['model_api_calls'],0)
        self.assertEqual(task['diagram_review']['max_local_validations'],12)
        self.assertIn('FS.single_edit',new['CLOSEOUT']['depends'])
        self.assertEqual(new['Q.retest.analysis']['narrative']['sections'],['idea02'])
        self.assertEqual(new['FS.analysis']['narrative']['sections'],['idea04','idea09'])
        self.assertEqual(updated,update_plan(updated))
        with tempfile.TemporaryDirectory() as temp:
            AutonomousPlan(temp,updated)


if __name__=='__main__':
    unittest.main()
