"""仅为三条旧初析失败的D_init题补生成一次初析，记录真实成本，不重跑代码。"""
import shutil
from pathlib import Path

from methods.cle_ablation import run_memory_q_dinit_card_cap as study
from methods.cle_ablation.run_memory_q import prepare_shared_initial
from methods.sct_trajectory.run_closed_loop import _requester


def main():
    if (study.ROOT / 'translation_work/diagnostics/20261020/cle_dinit_card_cap_v2/recovery.json').exists():
        from configs.cle_dinit_card_cap_20261020.continue_after_prompt_budget import configure
        configure()
    study.core.OUT = study.OUT
    study.core.STAGES = {'full': (303, 'full303')}
    meta = study.verify()
    path = Path(__file__).resolve()
    meta['identity'][str(path.relative_to(study.ROOT))] = study.core.digest(path)
    target = study.OUT / 'source_snapshot' / path.relative_to(study.ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    study.write(study.OUT / 'run_metadata.json', meta)
    protocol = study.read(study.OUT / 'protocol.json')
    tasks = study.read(study.OUT / 'tasks.json')
    budget = study.core.Budget(protocol, 'full', _requester('deepseek-v3.2', 120,
        max_tokens=4096, max_inflight=1, thinking='disabled'))
    for identifier in study.read(study.OUT / 'manifest.json')['learning']:
        dest = study.OUT / 'initials' / (identifier + '.json')
        if dest.exists():
            continue
        request, tracker = budget.bind(identifier, 'shared_initial')
        initial = prepare_shared_initial(tasks[identifier], request)
        initial.update(reused_initial=False, accounting=tracker.snapshot()['total'])
        study.write(dest, initial)
        print({'new_initial': identifier, 'error_type': initial['error_type']}, flush=True)
        if initial['error_type']:
            raise RuntimeError('new_initial_failed_no_retry:' + identifier)


if __name__ == '__main__':
    main()
