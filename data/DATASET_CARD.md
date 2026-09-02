# Dataset Card

## Contents

`SecEvoBasePlus` contains Secure/Insecure paired records translated or
prepared for Python, C++, Go, Java, and JavaScript. The formal public evaluation
track is Secure-only. Insecure fields are retained only as provenance and
training-side security-difference material.

## Counts

| Split | Python | C++ | Go | Java | JavaScript |
|---|---:|---:|---:|---:|---:|
| Base | 115 | 115 | 115 | 116 | 116 |
| Plus | 140 | 140 | 140 | 140 | 140 |

## Provenance

- Python: CodeSecEval/SecEvaBase and Plus sources.
- C++ and Go: translated and checked project outputs.
- Java and JavaScript: prepared dataset archive outputs; final Docker
  reproducibility is pending.

## Privacy and Reproducibility Cleaning

The public copy must not contain API keys or machine-specific paths. Use
`tools/sanitize_dataset.py` to replace local absolute paths with portable
placeholders. The sanitizer preserves the JSON structure and does not alter
code, task descriptions, or test semantics.

## Limitations

The data files contain upstream benchmark material. Users must check upstream
licenses and redistribution terms independently. Passing a historical
validator report does not prove that every method in this repository has been
re-run under the current protocol.
