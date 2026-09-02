# SCT Security Generation

Reproducible materials for self-evolving security experience transfer and
multilingual secure code generation.

## Scope

This repository evaluates secure-code generation for Python, C++, Go, Java,
and JavaScript. It keeps three kinds of methods separate:

| Group | Methods | Meaning |
|---|---|---|
| Prompt baselines | Greedy, Greedy + Secure Prompt, Chain-of-Thought, CoT + Secure Prompt | One model call with a clearly defined prompt. |
| Workflow baselines | AutoSafeCoder, AgentCoder, RA-Gen function-level, SWE-Agent adapted, SecAwareCoder | Multi-step generation, testing, tool feedback, or repair workflows from the source implementations. |
| Ours | SCT-Agent | Security experience memory, failure analysis, gated promotion, and frozen final evaluation. |

The workflow baselines are not represented by the prompt-only adapters used in
the old unified matrix. Those old adapter results are retained only as
historical evidence under `results/curated/` and are labelled accordingly.

## Repository Layout

```text
data/                         Five-language SecEvoBasePlus data and data card
src/translation_pipeline/     Docker validation and quality metrics
methods/prompting_baselines/  Four direct prompt baselines
methods/workflow_baselines/   Real workflow control-flow runner and notes
methods/sct_agent/            Experience memory and gated evolution runner
methods/legacy_prompt_adapters/ Historical prompt-adapter compatibility code
configs/                      Reproducible model, dataset, and run settings
docker/                       Validator Dockerfiles
results/curated/              Small, labelled summaries only
docs/                         Evaluation and reproduction protocol
tests/                        Offline smoke tests
tools/                        Dataset sanitation and repository checks
```

## Dataset

`data/SecEvoBasePlus/` contains the five-language Base/Plus collection:

| Split | Python | C++ | Go | Java | JavaScript |
|---|---:|---:|---:|---:|---:|
| Base | 115 | 115 | 115 | 116 | 116 |
| Plus | 140 | 140 | 140 | 140 | 140 |

Python, C++, and Go are the currently validated primary languages. Java and
JavaScript are included as prepared data, but their final Docker images and
full reproducibility records remain pending.

The public copy removes machine-specific absolute paths from metadata and
does not include API keys, local virtual environments, caches, Docker VHDX
files, or raw long-running logs. See `data/DATASET_CARD.md` for provenance and
limitations.

## Environment

Use PowerShell on Windows. Docker Desktop must be running for validation.

Install the Python runner dependency in your own environment:

```powershell
python -m pip install -r requirements.txt
```

```powershell
Copy-Item .env.example .env.local
notepad .env.local
. .\.env.local
```

Set only your own key in `.env.local`:

```powershell
$env:ZHIPU_API_KEY = "<your-key>"
$env:ZHIPU_API_BASE = "https://open.bigmodel.cn/api/paas/v4"
```

Never commit `.env.local`.

## Docker

The Python and C++ validators use the original Porta benchmark runtime base
images. Those base images are not redistributed here:

```powershell
docker build -t safecoder-python-validator:local docker/python-validator
docker build -t safecoder-cpp-validator:local docker/cpp-validator
docker pull golang:1.22
```

The validation code uses mounted temporary directories and cache directories,
short timeouts, `--rm`, bounded output, and explicit cleanup to reduce Docker
VHDX growth. Do not delete the VHDX directly.

## Offline Smoke Checks

These checks do not call an API and do not launch a full experiment:

```powershell
python -m compileall src methods tools
python -m unittest discover -s tests -v
python tools/check_repository.py
```

## Prompt Baselines

The four direct baselines are implemented in
`methods/prompting_baselines/prompts.py`. The runner supports an offline
configuration check and an API-backed generation run:

```powershell
python methods/prompting_baselines/run_prompt_baseline.py --check-only
python methods/prompting_baselines/run_prompt_baseline.py `
  --dataset-root data/SecEvoBasePlus `
  --subset Base `
  --language python `
  --limit 2 `
  --model glm-5.1
```

The generated code must be evaluated by the target-language validator; a
successful API response alone is not a passing result.

## Workflow Baselines

The original ZIP audit is in `docs/baseline_fidelity.md`. The runner in
`methods/workflow_baselines/run_true_agent_workflows.py` preserves the main
control-flow ideas:

- AutoSafeCoder: generate, static review, repair, validation feedback.
- AgentCoder: multiple candidates, test design, self-test selection, epochs.
- RA-Gen: planner, searcher, code generation, extraction, validation.
- SWE-Agent: edit, run tests, repair.
- SecAwareCoder: security analysis, test intent, generation, execution, repair.

For C++ and Go these are workflow adaptations connected to the Docker harness;
they are not claims of an official original-language reproduction. Run the
offline import check first:

```powershell
python methods/workflow_baselines/run_true_agent_workflows.py --help
```

Before a full run, use one task per method and inspect the saved trace,
generated code, Docker command, and Function/Secure results.

## SCT-Agent

The SCT-Agent runner uses security experience cards, language-specific memory,
failure analysis, and gated promotion. The formal protocol is documented in
`docs/evaluation_protocol.md`:

```text
experience data -> initial memory R0
training/development failures -> candidate rules
independent gate -> accepted or rejected rules
freeze the round -> Base/Plus final evaluation
```

Base/Plus results never update memory in the formal protocol.

## Results Policy

Only compact, labelled summaries are committed. Results are separated into:

- `prompting_baselines/`: four direct prompt methods.
- `workflow_baselines/`: actual workflow or workflow-adaptation results.
- `sct_agent/`: SCT-Agent rounds and gate records.

Historical results that used a different validator or allowed Base/Plus
feedback are marked `diagnostic_only` and must not be used as formal claims.
The compatibility code under `methods/legacy_prompt_adapters/` is retained
only to replay or inspect old records; it is not one of the formal baselines.

## Reproducibility Checklist

1. Record the Git commit, dataset manifest, model, temperature, token budget,
   retry count, worker count, Docker image names, and timeout.
2. Run offline smoke checks.
3. Run one task per method and inspect traces.
4. Run Base and Plus separately, then each language separately.
5. Keep generated code and validator output in an external ignored output
   directory; commit only compact summaries.
6. Report Function, Secure, Function+Secure, generation errors, tokens, time,
   and engineering-quality metrics with their exact calculation settings.

## License and Data Notice

The repository code is released under MIT. Dataset redistribution and the
licenses of upstream benchmark materials remain subject to their original
sources. See `LICENSE` and `data/DATASET_CARD.md` before redistribution.
