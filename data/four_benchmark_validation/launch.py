import json, sys, uuid, shutil
from dataclasses import asdict
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root))
from translation_pipeline.persistent_container import (
    ContainerPool,
    ContainerSpec,
    cleanup_stale_containers,
)

work = root / "translation_work/validation_runs/four_benchmark_20261124"
java = root / "translation_work/validation_runs/candidates_20261118/inputs/java"
shutil.copy2(Path(__file__).with_name("worker_replay.py"), work / "worker_replay.py")
cleanup_stale_containers(prefix="safecoder-pool-fourcwe-")
spec = ContainerSpec(
    image="cle-four-bank-go:20261124",
    mounts=((str(work), "/work"),),
    readonly_mounts=((str(java), "/java"),),
    network="none",
    memory="4g",
    cpus="2",
    env=(
        ("PYTHONPATH", "/work/cweval"),
        ("PYTHONDONTWRITEBYTECODE", "1"),
        ("GOCACHE", "/work/go-cache"),
        ("GOPROXY", "off"),
        ("GOMODCACHE", "/work/go-mod"),
        ("REPLAY_OUTPUT", "replay.jsonl"),
        ("GOFLAGS", "-mod=readonly"),
    ),
    tmpfs=("/tmp:rw,nosuid,nodev,size=512m",),
)
with ContainerPool(
    spec, size=1, prefix="safecoder-pool-fourcwe-", run_tag=uuid.uuid4().hex[:8]
) as pool:
    with pool.acquire() as container:
        probe = container.exec_argv(
            ["test", "-x", "/opt/audit/bin/python"], timeout=20, container_timeout=15
        )
        if probe.returncode:
            raise SystemExit("Environment probe failed")
        result = container.exec_argv(
            ["/opt/audit/bin/python", "/work/worker_replay.py", *sys.argv[1:]],
            timeout=9600,
            container_timeout=9500,
            output_limit=10000,
        )
        (work / "replay_execution.json").write_text(
            json.dumps(asdict(result), indent=2), encoding="utf8"
        )
        print(result.stdout, flush=True)
        raise SystemExit(result.returncode if result.returncode is not None else 1)
