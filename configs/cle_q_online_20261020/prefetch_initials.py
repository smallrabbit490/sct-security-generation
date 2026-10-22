"""提前生成与Q无关的D_grow首次初析；正式P7与逐题Q更新顺序保持不变。"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from methods.cle_ablation import run_memory_q_online as study


def run(workers=4, limit=None):
    """只消费公开契约，使用原请求预算和原生initial格式，不读取或更新经验/Q。"""
    meta = study.verify()
    assert meta['status'] == 'running_D_init', 'prefetch_only_while_D_init_runs'
    manifest = study.read(study.OUT / 'manifest.json')
    tasks = study.read(study.OUT / 'tasks_D_grow.json')
    ids = manifest['D_grow'][:limit] if limit else manifest['D_grow']
    wanted = [i for i in ids if not (study.OUT / 'D_grow/initials' / (i + '.json')).exists()]
    status_path = study.OUT / 'D_grow/initial_prefetch_status.json'
    status = {'status': 'running', 'workers': workers, 'planned_missing': len(wanted),
              'saved': 0, 'protocol': study.PROTOCOL, 'Q_updated': False,
              'same_initial_function_prompt_model_parameters': True}
    study.write(status_path, status)
    if not wanted:
        status['status'] = 'completed'
        study.write(status_path, status)
        return status
    api, p7 = study.Requests('D_grow', workers), study.frozen_runner()
    started = perf_counter()

    def job(identifier):
        request, tracker = api.bind(identifier, 'initial')
        initial = study.prepare_initial_analysis(
            {'task_description': p7.plt_contract(tasks[identifier])}, request)
        study.write(study.OUT / 'D_grow/initials' / (identifier + '.json'),
            {'task_id': identifier, 'initial_analysis': initial, 'error_type': None,
             'accounting': tracker.snapshot()['total'], 'reused_initial': False})
        return identifier

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for offset in range(0, len(wanted), workers):
                assert study.read(study.OUT / 'run_metadata.json')['status'] == 'running_D_init', 'main_stage_changed'
                pending = [pool.submit(job, i) for i in wanted[offset:offset + workers]]
                for future in as_completed(pending):
                    identifier = future.result()
                    status['saved'] += 1
                    status['last_saved_task'] = identifier
                    status['elapsed_seconds'] = perf_counter() - started
                    study.write(status_path, status)
                    print({'saved': status['saved'], 'planned': len(wanted), 'task': identifier}, flush=True)
        status['status'] = 'completed'
    except Exception as exc:
        status.update(status='stopped_technical', error_type=type(exc).__name__)
        raise
    finally:
        status['elapsed_seconds'] = perf_counter() - started
        study.write(status_path, status)
    return status


if __name__ == '__main__':
    run()
