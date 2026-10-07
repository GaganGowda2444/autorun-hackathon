# Transactional Repair and Replay for Reproducible Python Test Environments

## A Lightweight Docker-Based Approach Inspired by Repo2Run

**Author:** [Your Name]  
**Department/Institution:** [Your Department and University]  
**Course:** [Final-Year Major Project]  
**Date:** [Month Year]  
**Document status:** Base manuscript draft; experimental results are intentionally left as `TBD`

---

## Abstract

Constructing an executable test environment for an unfamiliar software repository is a repetitive and failure-prone task. A developer must select a compatible runtime, discover dependency files, install packages, configure environment variables, resolve version conflicts, and repeatedly run the test suite. These steps are difficult to reproduce because a failed installation or command can leave the environment in a partially modified state.

Repo2Run demonstrates an LLM-based approach that iteratively builds a Docker environment, observes failures, rolls back unsuccessful actions, and synthesizes a Dockerfile from the successful trajectory. This project studies a narrower and independently implementable version of that problem. We propose a constrained, transactional environment-repair system for Python repositories. The system uses a persistent Docker workspace, a strictly validated action interface, bounded action observations, Python-version switching, and pytest collection as the environment verifier. Every state-changing action is treated as a transaction: a checkpoint is created before execution, and a failed action is rejected and rolled back. Successful events are recorded and deterministically converted into a reusable Dockerfile and dependency lockfile. The final artifact is independently rebuilt in a clean container and validated again, making reproducibility an explicit part of the result rather than an assumed property of the interactive session.

The planned evaluation uses a frozen benchmark of public Python repositories and compares a fixed heuristic baseline, one-shot LLM Dockerfile generation, iterative repair without rollback, and the proposed transactional repair system. A secondary ablation studies whether semantic-action checkpoints reduce storage and time overhead compared with command-level checkpoints. The contribution of this project is not a claim to reproduce all of Repo2Run; it is a controlled study of transactional repair, checkpoint granularity, and clean replay for a bounded class of Python repositories.

**Keywords:** executable environments, Docker, repository setup, dependency resolution, LLM agents, rollback, reproducibility, pytest

---

## 1. Introduction

Modern software engineering systems increasingly depend on executable test environments. Before a patch can be evaluated, a model or developer needs a working Python interpreter, compatible third-party packages, system libraries, environment variables, and a correctly configured source path. In practice, creating this environment is still a manual and iterative process. A repository may contain several dependency files, use a non-default source layout, target a specific Python version, or rely on system packages that are not mentioned in its README.

The problem becomes more important at scale. Manually configuring hundreds of repositories is slow, expensive, and dependent on developer experience. A configuration that works on one machine may fail on another because the operating system, package versions, environment variables, or build tools differ. A failed command is also not necessarily harmless: package managers may install some transitive dependencies before returning an error, and a partially executed file operation may leave the environment inconsistent.

Repo2Run [1] frames executable environment construction as a state-transition problem. Given a repository `R`, a base image `B`, and a sequence of commands `P`, the system searches for a state in which the repository's tests can be executed. The paper combines an LLM agent, an internal Docker environment, an external event-processing environment, rollback of failed actions, dependency management, and a Dockerfile synthesizer. Its evaluation reports Dockerfile generation success rate (DGSR) and environment building success rate (EBSR) on 420 Python repositories.

This project is inspired by Repo2Run, but its scope is deliberately smaller and its contribution is more focused. The goal is not to build a general-purpose coding agent or to reproduce the complete Repo2Run system. Instead, we investigate the following question:

> Can a constrained, transactional repair loop generate a Python test environment that can be independently rebuilt and verified, while rejecting failed state changes before they contaminate later actions?

The distinction between **running an application** and **building a test environment** is essential. An application may start successfully even when its test suite cannot be collected. Conversely, a test suite may contain genuine product defects that should not be confused with an environment-building failure. Therefore, this project uses pytest collection as the primary verification checkpoint and reports test outcomes separately.

### 1.1 Contributions

This project is designed to make the following contributions:

1. **A precise success contract for environment building.** We distinguish Dockerfile build success, pytest collection success, clean replay success, and optional application smoke-test success.
2. **A constrained transactional repair architecture.** An LLM or other policy proposes only validated actions. Mutating actions are checkpointed, and failed actions are rolled back before further reasoning occurs.
3. **A replayable artifact pipeline.** Successful events are converted deterministically into a Dockerfile and exact dependency lockfile, which are rebuilt in a clean container.
4. **A checkpoint-granularity study.** We compare command-level snapshots with semantic-action snapshots to measure whether less frequent, semantically meaningful checkpoints preserve reliability while reducing overhead.
5. **A reproducible evaluation design.** A frozen Python benchmark, paired baselines, DGSR/EBSR metrics, replay validation, timing data, and a failure taxonomy provide evidence for the claims.

These contributions are proposals and implementation targets. This draft does not report experimental results that have not yet been collected.

---

## 2. Background and Related Work

### 2.1 Repo2Run

Repo2Run is the primary reference for this project. It addresses two challenges that are also visible in the current prototype:

- an LLM must discover a valid sequence of environment-building actions;
- a failed action must not make later reasoning and Dockerfile synthesis unreliable.

Repo2Run uses a dual-environment design. The internal environment is a Docker container in which actions are executed. The external environment receives observations, maintains the action history, and coordinates actions such as base-image changes and rollback. Its specialized actions include environment monitoring, dependency installation, test running, code editing, and shell commands. The resulting successful trajectory is processed by a Dockerfile synthesizer.

The paper also identifies practical failure categories. A base image can be incompatible with the repository, dependencies can conflict, environment variables can be missing, source code can contain syntax errors, and installation or test execution can exceed the available time. The paper's ablation results indicate that the dual-environment architecture, rollback, and Dockerfile synthesis each contribute to the final success rate.

Our project adopts the general state-transition and trajectory ideas but makes three simplifications:

1. only Python 3.10 and 3.11 are initially supported;
2. only `requirements.txt` and a documented subset of `pyproject.toml` are accepted;
3. arbitrary source editing and arbitrary persistent shell sessions are excluded from the first study.

These restrictions make the experiment reproducible and keep the evaluation focused on environment construction rather than general code repair.

### 2.2 LLM-based software-engineering agents

ReAct-style agents alternate between reasoning, actions, and observations [2]. SWE-agent and related systems expose tools for inspecting and modifying repositories [3]. Such agents can be flexible, but a general agent may produce commands that are difficult to replay or may modify tests in order to make a run appear successful.

This project uses a constrained action interface rather than unrestricted code generation. The language model may select among typed actions, but the runtime validates the action name, arguments, paths, package specifications, and resource budget before execution. Source and test files are read-only in the initial study. This reduces the action space and makes the experiment easier to audit.

### 2.3 Dependency inference and container generation

Tools such as `pipreqs` infer Python dependencies from imports [4]. They are useful baselines but can miss dynamic imports, optional dependencies, local packages, system libraries, and runtime environment variables. Template-based Dockerfile generators and LLM generators can use README information, but they may produce a Dockerfile that builds syntactically and fails when replayed.

The proposed system therefore treats dependency installation as an observed transaction. The final Dockerfile is not trusted merely because it looks reasonable; it must be built again in a clean context and pass the collection verifier.

### 2.4 Reproducible containers

Docker provides a practical execution boundary for the project, but it is not automatically a complete security boundary. Package installation can execute build scripts, repository-provided Dockerfiles can execute arbitrary build instructions, and a container can consume unbounded resources if no quotas are configured. The proposed implementation therefore uses a separate build context, rejects conflicting repository build files, applies time and resource limits, and runs research evaluations with Docker-only execution.

---

## 3. Problem Definition

### 3.1 State-transition formulation

Let:

- `R` be a source repository at a fixed commit;
- `B` be a selected base image;
- `C` be a finite sequence of validated actions;
- `δ(B, C)` be the environment state after executing `C`;
- `ε(R, S)` be an environment verifier.

The objective is to find an action sequence `P` such that:

```text
S = δ(B, P)
ε(R, S) = success
```

Unlike a general application runner, the verifier is primarily concerned with whether the repository's test environment is executable. The first verifier is:

```bash
python -m pytest --collect-only -q
```

An environment is considered collectable when the command exits with status zero and reports at least one collected test. The project records collection errors separately from test assertion failures.

### 3.2 Status definitions

The result schema uses independent statuses:

- **Build status:** whether the generated Dockerfile builds from a clean context.
- **Install status:** whether all selected dependency actions completed successfully.
- **Collect status:** whether pytest collection succeeds.
- **Replay status:** whether the saved Dockerfile builds and collection succeeds again in a fresh container.
- **Smoke status:** an optional application-level check that is not used as the main environment metric.
- **Test outcome:** the number of passed, failed, skipped, and errored tests after collection.

This separation prevents a running web server or a zero-exit placeholder command from being reported as a valid test environment.

### 3.3 Success metrics

Following Repo2Run, the primary aggregate metrics are:

```text
DGSR = successful Dockerfile builds / total attempts
EBSR = successful clean builds with successful pytest collection / total attempts
```

The project additionally reports:

- clean replay rate;
- test pass rate among collectable environments;
- median and total build time;
- number of actions and rejected actions;
- number and size of snapshots;
- LLM token and monetary cost, if an LLM is used;
- failure category.

DGSR and EBSR must be computed from saved artifacts and logs, not from console messages alone.

---

## 4. Proposed Method

### 4.1 System overview

The proposed pipeline is:

```text
Repository URL/path
        |
        v
Frozen checkout and metadata collection
        |
        v
Manifest and project-type detection
        |
        v
Persistent Docker repair environment
        |
        +--> inspect / install / configure / verify actions
        |
        +--> checkpoint before mutations
        |
        +--> rollback failed mutations
        |
        v
Successful trajectory and verifier result
        |
        v
Deterministic Dockerfile + lockfile synthesis
        |
        v
Clean rebuild and independent replay
        |
        v
Structured report and evaluation record
```

The current repository already provides useful building blocks for the first and last stages: `src/cloner.py` can acquire repositories, and `src/reporter.py` can write reports. The current one-shot application runner in `src/sandbox.py` must be refactored into a persistent environment with a controller.

### 4.2 Repository preparation

Before any repair action, the system records:

- repository URL or local source;
- commit SHA and branch, when available;
- repository size and file count;
- detected project type;
- supported dependency manifests;
- base-image candidates;
- whether the repository requires GPU, private credentials, external services, or interactive input.

The checkout is immutable during an experiment. A benchmark entry is accepted or rejected according to criteria declared before observing system results. This prevents selective reporting based on which repositories happen to succeed.

### 4.3 Typed action interface

The initial action vocabulary is intentionally small:

```text
inspect_files(paths)
show_python()
list_packages()
install_requirements(path)
install_package(specification)
set_env(name, value)
set_python(version)
run_collect(path)
```

A policy returns structured JSON rather than arbitrary shell text:

```json
{
  "thought": "The collection error requires Python 3.11",
  "action": "set_python",
  "arguments": {
    "version": "3.11"
  },
  "reason": "The repository imports enum.StrEnum"
}
```

The runtime rejects unknown actions, unsupported Python versions, unsafe paths, invalid environment-variable names, and package specifications outside the declared policy. Arbitrary bash execution and source/test editing are not enabled in the first evaluated version.

The action interface allows the LLM to be replaced by a deterministic policy for ablation or debugging. This is useful for separating the effect of the language model from the effect of transactional execution and Dockerfile synthesis.

### 4.4 Persistent internal environment

The internal environment is a long-lived Docker container for one repository attempt. Unlike the current application runner, the container remains available after an action so that the next action can inspect or repair the same state.

For each action, the runtime records:

```text
event_id
repository_sha
base_image
action
validated_arguments
working_directory
start_time
end_time
return_code
stdout/stderr byte counts
bounded observation
snapshot_id
status
```

The controller maintains a state machine such as:

```text
INITIALIZING
    -> INSPECTING
    -> BUILDING
    -> VERIFYING
    -> SUCCEEDED
    -> REPAIR_REQUIRED
    -> FAILED
```

A base-image change creates a new clean container and resets prior state-changing events. Monitoring and test events are retained in the event history for diagnosis but are not emitted as Dockerfile `RUN` instructions.

### 4.5 Transactional actions and rollback

Every action is classified as one of:

- **read-only:** inspection, version display, package listing;
- **state-changing:** dependency installation, environment configuration, or approved code setup;
- **verification:** pytest collection;
- **base-image-changing:** Python version switch.

Before a state-changing action, the runtime creates a checkpoint. The initial implementation may use a temporary Docker image created from the current container state. The action is then executed with a wall-clock timeout and resource limits.

If the action returns zero, the new state is retained and a success event is recorded. If it returns non-zero, times out, or violates policy:

1. the action is marked `rejected`;
2. the possibly contaminated container is stopped;
3. a replacement container is created from the last valid checkpoint;
4. the failure observation is passed to the policy;
5. the next action begins from the restored state.

This is the central difference from simply running a sequence of shell commands. A failed action is not allowed to silently become part of the future environment.

#### Command-level versus semantic-action checkpoints

The planned ablation compares two checkpoint policies:

- **Command-level:** create a checkpoint before each command or shell operation.
- **Semantic-action:** create a checkpoint before each validated high-level action, such as installing a dependency file or changing the Python version.

Semantic checkpoints may reduce image commits and storage overhead, but they require careful action boundaries. A semantic action that contains multiple commands can partially mutate state before failing. The study therefore records whether a semantic action is atomic enough for reliable restoration and treats this as an empirical question rather than assuming that fewer snapshots are always better.

### 4.6 Bounded result processing

Long output can overflow pipes or an LLM context. The runtime drains stdout and stderr continuously into separate temporary files or bounded streams. Each event records:

- total byte count;
- a head excerpt;
- a tail excerpt;
- an error summary;
- a hash of the full log.

The full log is archived for reproducibility, while the policy receives a bounded observation. This preserves diagnostic information without allowing a repository to produce unbounded memory growth or an unusable prompt.

### 4.7 Verification

The default verifier is:

```bash
python -m pytest --collect-only -q
```

The verifier is run after dependency and configuration actions. Its result contains:

- exit status;
- collected-test count;
- collection errors;
- duration;
- Python version;
- installed package inventory;
- bounded stdout/stderr excerpts.

A full test run is optional and is reported separately. This follows the Repo2Run distinction between environment-building success and test-pass outcomes.

### 4.8 Deterministic Dockerfile synthesis

The final Dockerfile is generated from the event log, not from a second unconstrained LLM request. The synthesis rules are:

1. Begin with the final selected `FROM` image.
2. Add `WORKDIR /repo`.
3. Copy the frozen repository into a fixed path.
4. Emit `ENV` instructions for approved persistent variables.
5. Emit `RUN` instructions only for successful state-changing actions.
6. Omit read-only inspection and verification actions.
7. Exclude rejected or failed actions.
8. Reset the generated history when the base image changes.
9. Replace unconstrained package specifications with exact versions observed after successful installation.
10. Save the generated Dockerfile and lockfile as first-class artifacts.

The synthesizer must be deterministic: the same accepted event sequence and package inventory should produce the same Dockerfile text.

### 4.9 Independent replay

Interactive success is not sufficient. The saved Dockerfile is built in a clean context, a new container is created, runtime networking is disabled where possible, and the collection verifier is run again. The replay result includes:

- build status;
- image digest;
- collection status;
- replay time;
- final package versions;
- bounded logs.

A run is considered replayable only if this independent stage succeeds.

### 4.10 Safety and resource policy

The research execution mode uses Docker-only operation. It does not silently fall back to host subprocess execution. The runtime applies declared limits for:

- wall-clock time;
- CPU;
- memory;
- process count;
- disk/output size;
- dependency-install time;
- network access.

The implementation should run in a disposable VM or rootless Docker environment for experiments involving untrusted repositories. Secrets are not injected into containers. Package licenses and repository terms are recorded for the benchmark.

---

## 5. Relationship to the Current Prototype

The current code is useful as an engineering starting point but should be reorganized around the proposed method.

| Current component | Reuse or replacement |
|---|---|
| `src/cloner.py` | Reuse repository acquisition; add fixed commit recording, size limits, and safer URL/path handling. |
| `src/detector.py` | Replace broad framework guessing with a supported Python-manifest detector and explicit project classification. |
| `src/sandbox.py` | Refactor the one-shot app runner into a persistent transactional Docker environment. Remove automatic host fallback in research mode. Move application startup to an optional smoke-test module. |
| `src/main.py` | Replace the linear clone-detect-run flow with the repair state machine and strict termination conditions. |
| `src/reporter.py` | Redesign the result schema to include event, build, collection, replay, and provenance data. |
| `src/config.py` | Pass one resolved, validated configuration through the complete run and record it in the report. |
| `tests/` | Keep unit tests, add real Docker integration tests, rollback tests, replay tests, and adversarial input tests. |

The existing generated reports demonstrate that a Flask application can start, but they do not demonstrate that a test environment was built or that a Dockerfile was replayed.

---

## 6. Research Questions and Hypotheses

### RQ1: Does constrained iterative repair improve environment construction?

**Hypothesis:** A typed, iterative repair loop will achieve a higher EBSR than a one-shot Dockerfile generated directly from README or repository metadata, because it can respond to collection errors while preserving a successful trajectory.

### RQ2: Does rollback improve clean replay?

**Hypothesis:** Rejecting failed state-changing actions will increase the percentage of saved Dockerfiles that build and collect successfully in a clean container, compared with the same repair loop without rollback.

### RQ3: Can semantic checkpoints reduce overhead?

**Hypothesis:** Semantic-action checkpoints will retain most of the replay reliability of command-level checkpoints while requiring fewer snapshots and less checkpoint time. The result may be negative for actions that contain multiple partially mutating commands; that is an informative outcome.

### RQ4: How do failures differ across repository complexity?

**Question:** Which failure categories dominate: missing manifests, dependency conflicts, Python-version mismatches, repository defects, timeouts, or infrastructure limitations?

---

## 7. Experimental Design

### 7.1 Benchmark

The first evaluation will use a frozen benchmark of approximately 20 public Python repositories. Each entry will include a URL, commit SHA, license, project type, supported manifest, and inclusion rationale.

Eligibility criteria will be declared before experiments:

- public repository with a fixed commit;
- pytest-compatible tests;
- no GPU, paid API, private registry, or interactive credentials;
- no required external database or service for collection;
- supported Python version and dependency manifest;
- license suitable for research use.

The benchmark will include simple and complex projects, with the complexity distribution recorded rather than hidden.

### 7.2 Experimental conditions

| Condition | Description |
|---|---|
| C0: Heuristic baseline | Manifest-based installation and a fixed Dockerfile template, similar to the current prototype. |
| C1: One-shot LLM | The model reads repository metadata/README and produces a Dockerfile in one pass. |
| C2: Iterative repair without rollback | Typed actions and pytest feedback are enabled, but failed mutations are not restored. |
| C3: Transactional repair | Typed actions, semantic checkpoints, rollback, deterministic synthesis, and clean replay are enabled. |
| C4: Checkpoint ablation | On a subset, compare command-level and semantic-action checkpoints. |

Each main condition should be run twice on each repository using the same frozen commit. Model version, prompt, limits, and configuration must be recorded.

### 7.3 Metrics

Primary metrics:

- DGSR;
- EBSR;
- clean replay rate.

Secondary metrics:

- test pass rate among collectable environments;
- collected-test count;
- total and phase-specific time;
- action count;
- rejected-action count;
- snapshot count, time, and estimated storage;
- image size and digest;
- Dockerfile lint warnings;
- LLM tokens and cost, if applicable;
- failure category.

### 7.4 Analysis

Because all conditions are evaluated on the same repositories, comparisons should be paired. Report counts and percentages, but also provide uncertainty. For binary outcomes, Wilson intervals and an exact paired test such as McNemar's test can be used. For time and cost, paired bootstrap intervals are appropriate.

The sample size is modest, so the project should emphasize effect sizes and failure analysis rather than claiming statistical significance from a small number of repositories.

### 7.5 Results table template

No values are inserted until the experiments are completed.

| Condition | DGSR | EBSR | Clean replay | Median time | Failed actions | Infrastructure failures |
|---|---:|---:|---:|---:|---:|---:|
| C0 | TBD | TBD | TBD | TBD | TBD | TBD |
| C1 | TBD | TBD | TBD | TBD | TBD | TBD |
| C2 | TBD | TBD | TBD | TBD | TBD | TBD |
| C3 | TBD | TBD | TBD | TBD | TBD | TBD |

A separate table will report the command-level versus semantic-checkpoint ablation.

---

## 8. Failure Taxonomy

Every failed attempt will be assigned one primary category and optional secondary tags:

1. **Unsupported manifest:** no supported dependency declaration.
2. **Dependency conflict:** incompatible package constraints.
3. **Python-version mismatch:** syntax or standard-library incompatibility.
4. **Missing system dependency:** compiler, library, or operating-system package.
5. **Source-layout issue:** local module or `PYTHONPATH` problem.
6. **Repository defect:** syntax error, missing module referenced by tests, or invalid test.
7. **Test timeout:** collection or test execution exceeds the declared budget.
8. **Dependency timeout or hardware insufficiency:** external resource limitation.
9. **LLM/action-limit failure:** no valid action or action budget exhausted.
10. **Infrastructure failure:** Docker daemon, network, disk, or runtime failure.

This taxonomy prevents a failed repository from being incorrectly attributed to the proposed repair algorithm.

---

## 9. Limitations and Threats to Validity

The following limitations are expected and will be reported honestly:

- A benchmark of approximately 20 repositories is smaller than the 420-repository benchmark in Repo2Run.
- Public repositories may contain external services, credentials, hardware assumptions, or outdated dependencies.
- LLM output can vary with model version, provider, temperature, and prompt formatting.
- Docker resource limits may exclude repositories that require more memory or disk than the study permits.
- The first version does not edit source or test files, so some repository defects cannot be repaired.
- The study evaluates collection success rather than requiring all tests to pass.
- The project does not reproduce SWE-agent or the full Repo2Run tool suite.
- Results from one operating system and Docker version may not generalize to every platform.
- A failed package installation can have external side effects even inside a container; experiments should use disposable environments and restricted credentials.

The paper itself reports hardware insufficiency, dependency timeout, and test timeout as important failure categories and notes that complex environments may require manual intervention. The proposed project will make these limitations measurable rather than hiding them inside a single success/fail value.

---

## 10. Ethics, Security, and Reproducibility

The system executes untrusted repository code and package installation code. The research implementation must therefore:

- use Docker-only execution for repository experiments;
- avoid injecting personal credentials, API keys, or cloud tokens;
- restrict network access where the experiment does not require it;
- apply CPU, memory, process, disk, and wall-time limits;
- remove temporary containers and images according to a documented cleanup policy;
- avoid running repositories that are not permitted by their license or terms;
- publish commit identifiers and benchmark inclusion rules;
- archive prompts, model identifiers, tool versions, event logs, generated Dockerfiles, lockfiles, and analysis scripts.

No human-subject study is required for this project. If a small manual usability study is added later, it should receive institutional approval and appropriate consent.

---

## 11. Implementation Roadmap

### Milestone 1 — Valid environment contract

- Define result statuses and metrics.
- Add fixed-commit metadata.
- Make Docker-only research mode explicit.
- Add real Docker integration tests.

### Milestone 2 — Transactional environment

- Implement persistent container management.
- Add typed actions and strict validation.
- Add bounded output capture.
- Implement checkpoint and rollback.
- Add Python 3.10/3.11 switching.

### Milestone 3 — Replayable artifact

- Add pytest collection verifier.
- Persist event logs.
- Generate deterministic Dockerfile and lockfile.
- Rebuild and validate from a clean context.

### Milestone 4 — Controlled evaluation

- Freeze the benchmark manifest.
- Run the heuristic and one-shot baselines.
- Run iterative repair with and without rollback.
- Run the checkpoint-granularity ablation.
- Produce paired statistics and failure analysis.

### Milestone 5 — Documentation and presentation

- Write the final paper.
- Document installation, Docker requirements, model configuration, and limitations.
- Prepare a reproducible demonstration repository.
- Release anonymized or license-compatible evaluation artifacts where possible.

---

## 12. Conclusion

Repo2Run demonstrates that executable environment construction can be treated as an iterative state-transition problem rather than a one-time Dockerfile-writing task. This project focuses on the central mechanisms that make such a process reliable: constrained actions, persistent Docker state, transactional rollback, test-based verification, deterministic synthesis, and clean replay.

The proposed contribution is not a claim that rollback or Docker-based LLM agents are new in isolation. Rather, it is a controlled study of how these mechanisms behave in a bounded Python environment-building system, with an explicit comparison of checkpoint granularity and an independently verified artifact. The final outcome will be judged by whether the system can produce an auditable, reproducible environment for a declared benchmark—not by whether every repository or every test succeeds.

---

## Appendix A: Example Event Record

```json
{
  "event_id": "event-0007",
  "repository_sha": "<fixed-commit>",
  "base_image": "python:3.11-slim",
  "action": "install_requirements",
  "arguments": {
    "path": "requirements.txt"
  },
  "working_directory": "/repo",
  "return_code": 0,
  "status": "success",
  "stdout_bytes": 1842,
  "stderr_bytes": 320,
  "observation_head": "Collecting ...",
  "observation_tail": "Successfully installed ...",
  "snapshot_id": "snapshot-0006",
  "duration_seconds": 18.4
}
```

## Appendix B: Example Dockerfile Synthesis

```dockerfile
FROM python:3.11-slim
WORKDIR /repo
COPY repository/ /repo/
ENV PYTHONPATH=/repo/src
RUN python -m pip install --no-cache-dir Flask==3.1.3
```

The exact Dockerfile will be generated from accepted events and verified by a clean rebuild. The example is illustrative and is not an experimental result.

## Appendix C: Relationship Between This Project and Repo2Run

| Repo2Run idea | This project's planned treatment |
|---|---|
| Dual environment | Persistent internal Docker environment plus a typed external controller. |
| Rollback | Transactional checkpoints before state-changing actions. |
| Dependency management | Restricted Python manifests, explicit package actions, exact version capture, and failure classification. |
| Test running | `pytest --collect-only` as the primary checkpoint; full test results are secondary. |
| Dockerfile synthesizer | Deterministic event-to-Dockerfile conversion, not a second free-form LLM generation. |
| LLM agent | Optional replaceable policy within a strict action schema. |
| Large benchmark | Frozen 20-repository benchmark for a final-year project. |
| Code editing | Excluded from the initial study to protect tests and keep scope bounded. |

## References

[1] R. Hu, C. Peng, X. Wang, J. Xu, and C. Gao, “Repo2Run: Automated Building Executable Environment for Code Repository at Scale,” arXiv:2502.13681v4, 2025.

[2] S. Yao et al., “ReAct: Synergizing Reasoning and Acting in Language Models,” in *International Conference on Learning Representations*, 2023.

[3] J. Yang et al., “SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering,” arXiv:2405.15793, 2024.

[4] bndr, “pipreqs: Generate pip requirements.txt file based on imports of any project.”

[5] Docker documentation, “Dockerfile reference” and “Resource constraints,” Docker Inc.

[6] Python Software Foundation, “pytest documentation,” 2024.

[7] GitPython documentation, “GitPython: GitPython is a Python library for interacting with Git repositories.”
