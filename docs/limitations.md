# Limitations

- Java and JavaScript Docker images are not yet fixed for full reproduction.
- C++ and Go workflow runs are adaptations of Python/CodeSecEval-oriented
  workflows and must not be described as official original-language reruns.
- Historical results come from multiple stages of the project and are labelled
  by protocol; they are not automatically comparable.
- The repository contains benchmark-derived data. Upstream licensing and
  redistribution rules still apply.
- API-backed experiments require a user-provided key and are intentionally not
  run during repository packaging.
## Runtime validation scope

The public dataset contains the translated C++ and Go programs, but the
original per-task native harness directories are generated runtime artifacts
and are not redistributed. A fresh Docker validation of C++/Go therefore
requires either the original harness archive or a separately generated native
harness set. Python tests are stored directly in the dataset and can be run
from the public snapshot.
