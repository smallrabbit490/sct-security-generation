from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / "src"))
from translation_pipeline.persistent_container import ContainerPool, ContainerSpec

p = Path.cwd() / "translation_work/validation_runs/four_benchmark_20261124"
spec = ContainerSpec(
    image="cle-four-bank-go:20261124",
    mounts=((str(p), "/work"),),
    network=None,
    env=(("GOMODCACHE", "/work/go-mod"),),
)
with ContainerPool(spec, size=1, prefix="fourbank-go-deps-") as pool:
    with pool.acquire() as c:
        r = c.exec_argv(
            ["go", "mod", "download"],
            workdir="/work/cweval",
            container_timeout=90,
            timeout=110,
        )
        print(r.returncode, r.stderr)
        raise SystemExit(r.returncode)
