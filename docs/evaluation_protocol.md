# Evaluation Protocol

## Primary Outcome

The main result is `Function+Secure`: a generated Secure implementation counts
as successful only when it passes both the functional test and the security
test in the target-language environment.

`Function` and `Secure` remain separate explanatory metrics. PRCS and EQS are
engineering-quality supplements, not replacements for the primary outcome.

## Data Isolation

Experience preparation, development feedback, and gating must be separated
from final evaluation. Base and Plus are final evaluation sets only. Their
failures cannot update prompts, memory, micro gates, or future rules.

## Required Run Metadata

Every run records dataset manifest, commit, model, temperature, max tokens,
retries, workers, timeout, Docker image names, method identity, and output
schema version.

## Required Tables

Report separately by Base/Plus, language, and method group:

- Function pass count and rate.
- Secure pass count and rate.
- Function+Secure count and rate.
- Generation/API errors.
- Average tokens, time, and retries.
- PRCS and EQS with the exact warning and growth settings.

## SCT-Agent Rounds

```text
R0 initial memory -> gate -> freeze -> final evaluation
R1 candidate rules from training/development failures -> gate -> freeze -> final evaluation
R2 same protocol
R3 same protocol
```

The final report must show every round. A partial micro-gate run or a run that
feeds Base/Plus failures back into memory is diagnostic-only.
