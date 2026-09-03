# External Datasets

This directory contains external security-code data that is useful for
experience extraction or supplementary experiments. It is separate from the
`SecEvoBasePlus` evaluation set.

| Directory | Contents | Intended role |
|---|---|---|
| `secodeplt/secodeplt/` | 1,411 vulnerable/patched Python pairs | Primary experience source |
| `secodeplt/juliet/` | 263 Java autocomplete records | Java supplementary data |
| `secodeplt/cyber_sec_eval/` | SeCodePLT cybersecurity task files | Supplementary security data |
| `secodeplt/redcode/` | RedCode examples and metadata | Negative/security analysis material |
| `cweval/benchmark/` | CWEval multi-language benchmark tasks and tests | Supplementary evaluation material |
| `cweval/autosafecoder/` | 121 AutoSafeCoder Python negative examples | Negative examples for experience analysis |

These files are copied from the local source packages documented in
`docs/external_dataset_provenance.md`. They must not be mixed into the formal
`SecEvoBasePlus` score unless a separate split and protocol are recorded.

Secrets and machine-specific paths are redacted in this repository copy.
