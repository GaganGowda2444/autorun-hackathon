# Master Implementation Plan: EnvRun CLI

## A transactional, replayable repository runner with configurable workloads

**Project:** `autorun-hackathon`  
**Plan status:** Implementation blueprint; no source code changes are implied by this document  
**Literature checked:** 24 September 2026  
**Primary reference:** Repo2Run, arXiv:2502.13681v4 / NeurIPS 2025

---

## 1. Executive decision

The recommended product is:

> **A CLI tool that accepts a repository plus a declared workload, automatically constructs or repairs an isolated execution environment, runs the workload with user-provided inputs, collects outputs, and saves a replayable environment recipe.**

The tool must not claim that it can run every repository without qualification. “Almost any input” is implemented as a **typed, extensible workload contract**, not as unrestricted command execution.

The first supported class will be:

- public or local repositories;
- Python projects on Linux containers;
- command-line applications, test environments, and selected web services;
- files, directories, URLs, environment variables, and CLI arguments as workload inputs;
- declared output files/directories and readiness checks.

A repository that requires an unsupported service, credential, GPU, or proprietary interface should return an explicit status such as `needs_adapter` or `needs_human_configuration`; it must never be reported as successful merely because a placeholder command exited with code zero.

### One-sentence research claim

> For a bounded class of Python repositories, a typed action controller with transactional Docker checkpoints, deterministic verification, and clean Dockerfile replay reduces user setup effort and improves the reliability of environment construction compared with one-shot setup scripts.

This extends the ideas of Repo2Run and related work without claiming to reproduce their full systems or their benchmark results.

---

## 2. Scope and non-goals

### In scope for the first release

- Git clone for GitHub and compatible Git URLs.
- Local repository input.
- Fixed commit/branch recording.
- Python 3.10 and 3.11 base images.
- `requirements.txt` and a documented subset of `pyproject.toml`.
- Docker-based execution with no automatic host fallback.
- Persistent internal environment for setup and repair.
- Typed setup actions and bounded LLM assistance.
- Dependency installation and conflict diagnosis.
- Python-version switching.
- Pytest collection as the environment verifier.
- Deterministic Dockerfile and lockfile generation.
- Clean rebuild and replay.
- Workload profiles for CLI, test, and basic web applications.
- Files, directories, URLs, environment variables, and argument inputs.
- Output collection, checksums, logs, and structured reports.
- Resource limits, cleanup, and a local-only default.

### Explicitly deferred

- General GUI/browser interaction.
- Arbitrary desktop applications.
- GPU/CUDA setup as a default capability.
- Private registries and production credentials.
- Full multi-language support in the research branch.
- Unrestricted source or test-file editing.
- Nested Docker-in-Docker workloads.
- Long-running distributed services by default.
- Automatic support for every package manager and every repository layout.
- A claim of universal repository compatibility.
- Training a new foundation model.

These are not permanently excluded. They are kept outside the first measurable release so that the core system can be completed and evaluated.

---

## 3. What the literature says and what remains open

The following is a focused review of primary papers, preprints, and official artifacts relevant to this project. It is not a claim of an exhaustive systematic review.

| Work | Main contribution | Gap relevant to this project | Selected response |
|---|---|---|---|
| [Repo2Run](https://arxiv.org/abs/2502.13681) | LLM-driven Python environment construction, dual environments, rollback, base-image switching, dependency actions, and Dockerfile synthesis. | Python-focused; interaction and rollback are expensive; success definition is narrow; no general workload input/output contract; generated artifact and user handoff need stronger validation. | Use its transaction/event model, but add a deterministic verifier, bounded typed actions, output artifacts, replay, and user-facing profiles. |
| [Installamatic](https://arxiv.org/abs/2412.06294) | Searches repository documentation, then writes and repairs a Dockerfile in a VM. | Documentation discovery and missing extra test dependencies are major failure sources; only 40 Python repositories; average installation success was much lower than the best-attempt rate. | Extract README, CONTRIBUTING, CI, and manifest evidence into a structured repository profile; require a deterministic collection check. |
| [ExecutionAgent](https://arxiv.org/abs/2412.10133) | Multi-language agent that uses meta-prompting, tools, and iterative feedback to run tests; 33/50 projects in its evaluation. | Long runtime, broad command space, expensive retries, and dependence on manual ground-truth test interpretation. | Use a typed action interface, fixed budgets, output summarization, structured test results, and optional LLM guidance instead of unrestricted shell reasoning. |
| [EnvBench](https://arxiv.org/abs/2503.14443) | 994 Python/JVM repositories and static/compile-based setup metrics. | Excludes projects requiring Docker, uses proxy metrics that miss runtime failures, and best Python setup success is low. | Combine static inspection, build status, collection status, and a small runtime smoke check; report each independently. |
| [SetupAgent](https://arxiv.org/abs/2503.07701) | Extracts historical install/test commands, iterates on failures, and validates generated commands. | Filters out difficult cases; success is tied to benchmark construction; Docker-in-Docker and multi-link documentation remain difficult. | Preserve historical commit/package information, support explicit service profiles, and distinguish unsupported cases from failures. |
| [PLLM](https://arxiv.org/abs/2501.16191) | RAG-assisted iterative Python dependency repair using PyPI metadata and runtime errors. | LLM guesses versions independently, can ignore pip constraints, and parallel Python-version trials waste work. | Use deterministic import/package resolution and constraint parsing first; call the LLM only for missing metadata or ambiguous mappings. |
| [SMT-LLM](https://arxiv.org/abs/2605.11772) | AST analysis, PyPI metadata, Z3 constraints, and selective LLM imputation for dependency resolution. | Evaluated primarily on Python snippets, not full repositories; local-module ambiguity, historical package drift, platform SDKs, and C-extension builds remain difficult. | Adopt the hybrid principle: deterministic analysis and solver before LLM guessing; label platform/local-module cases as unsupported where appropriate. |
| [Multi-Docker-Eval](https://arxiv.org/abs/2512.06915) | Multilingual benchmark with build success, fail-to-pass, resource, and image-size metrics. | Docker-build errors dominate; test-script generation and silent false passes remain major failure modes. | Track build, collection, replay, and workload statuses separately; never use a model’s “commit” decision as proof of success. |
| [DockSmith](https://arxiv.org/abs/2602.00592) | Multi-agent Docker builder with specialized roles, loop detection, trajectory filtering, and cross-task memory. | Requires large-scale trajectory/model infrastructure; aimed at training environments rather than an end-user CLI. | Implement lightweight loop detection, event summaries, and verified profile memory; do not train a new model for this project. |
| [SWE-Factory/SWE-Builder](https://arxiv.org/abs/2506.10954) | Four-agent environment construction, memory pool, test scripts, and exit-code-based validation. | Designed around issue-resolution datasets and ground-truth patches; not a general user workload runner. | Use role separation and exit-code markers, while keeping the user interface independent of issue/patch data. |
| [RepoLaunch](https://arxiv.org/abs/2603.05026) | Cross-language/cross-platform build and test management, rebuild commands, and test-log parsers. | Free-form agent commands are costly and variable; timeouts/OOM and test execution remain major failures. | Use language profiles, deterministic management artifacts, parser registry, and resource budgets; keep the research branch smaller. |
| [SUPER](https://arxiv.org/abs/2409.07440) | End-to-end setup and execution of under-documented research repositories, with outcome and landmark metrics. | Research-task-specific; external services/GPU and some data cases are filtered; proxy execution metrics can be incomplete. | Support a user task descriptor and outcome artifacts; do not claim scientific reproducibility without domain-specific evidence. |
| [CORE-Bench](https://arxiv.org/abs/2409.11363) | Isolated reproducibility tasks with text/image outputs and secure VM evaluation. | CodeOcean-style curated capsules and question-answering tasks are not general repository execution. | Use isolated evaluation and output verification, but keep the CLI focused on running declared workloads. |
| [R2E](https://proceedings.mlr.press/v235/jain24c.html) / [R2E-Gym](https://arxiv.org/abs/2504.07164) | Executable environments and synthetic/equivalence-test generation for agents. | Function-level or synthetic test oracles do not replace real repository test/workload validation. | Use real repository tests when available; treat generated tests as optional diagnostics, never as the sole environment proof. |
| [ReproZip](https://www.reprozip.org/) | Captures provenance and packages dependencies/data for later reproduction. | Requires a prior run and does not repair an unknown repository from scratch; tracing may miss external services. | Consider an optional provenance bundle after successful execution; do not make it the primary setup mechanism. |
| [GitTaskBench](https://arxiv.org/abs/2508.18993) | User-centric, multimodal repository tasks; environment setup is a dominant failure category. | Benchmark tasks are manually curated and do not define a universal repository input interface. | Evaluate real user workflows with declared input/output criteria and report environment failures separately. |

### Main research gap selected for this project

Among the reviewed systems, environment construction, test execution, benchmark generation, and reproducibility are usually separate goals. There is less attention to a single user-facing contract that combines:

1. repository acquisition;
2. environment repair;
3. arbitrary-but-declared workload inputs;
4. application/test execution;
5. output collection;
6. replay;
7. cleanup and security;
8. actionable diagnostics when automation is impossible.

The project will focus on this integration gap while keeping the scientific evaluation centered on environment reliability.

---

## 4. Product definition

### 4.1 User promise

> Given a repository and a workload description, EnvRun will make a best effort to create a clean, replayable environment, run the workload, and return the requested artifacts or a precise explanation of what requires user action.

The words **best effort**, **declared workload**, and **precise explanation** are intentional. The tool must not imply universal success.

### 4.2 Two separate pipelines

The design has two layers:

#### Environment pipeline

```text
repository -> inspect -> install -> configure -> verify -> replay
```

This is the research contribution and is independent of whether the final workload is a test, CLI, server, or media-processing job.

#### Workload pipeline

```text
workload profile + inputs -> environment -> execute -> readiness -> collect outputs
```

This provides the user-facing functionality. It may use a prepared environment or request one from the environment pipeline.

### 4.3 User-level statuses

Every run must use explicit statuses:

```text
unsupported
needs_input
needs_secret
needs_adapter
preflight_failed
clone_failed
inspect_failed
install_failed
verification_failed
replay_failed
workload_failed
timeout
cancelled
completed
```

`completed` requires a declared success condition. It must not be inferred solely from process startup or an exit code of a placeholder command.

---

## 5. CLI contract

### 5.1 Commands

The initial command set should be small and explicit:

```bash
autorun doctor
autorun inspect <repository>
autorun init <repository>
autorun prepare <repository> [--profile profile.yaml]
autorun run <repository> --profile profile.yaml
autorun replay <run-directory>
autorun validate <profile>
autorun clean [--run-id RUN_ID]
autorun benchmark <manifest>
```

### 5.2 `doctor`

Checks:

- Git availability;
- Docker Engine/Desktop availability;
- Docker build/run permissions;
- architecture compatibility;
- optional runtimes and tools;
- available disk, memory, and CPU;
- network/package-index policy;
- LLM provider configuration, if assisted mode is enabled.

It must not silently downgrade to unsafe host execution.

### 5.3 `inspect`

Produces a read-only repository profile containing:

- repository URL/path;
- resolved commit;
- language and project type;
- manifests and lockfiles;
- documentation files;
- CI files;
- candidate entrypoints;
- candidate test commands;
- required environment variables;
- likely inputs and outputs;
- unsupported requirements;
- confidence and evidence for every inferred field.

### 5.4 `init`

Creates a profile skeleton without running the workload:

```bash
autorun init https://github.com/example/project --output project.profile.yaml
```

The user or agent may edit the profile. This is important because automatic inference must be correctable.

### 5.5 `prepare`

Runs the environment pipeline and produces:

- validated environment image or image recipe;
- generated Dockerfile;
- dependency lockfile;
- environment manifest;
- action event log;
- verification report.

### 5.6 `run`

Runs a declared workload using a prepared environment. It accepts input through a profile or command-line convenience options.

### 5.7 `replay`

Rebuilds the saved Dockerfile in a clean context and reruns the environment verifier. It does not trust the interactive container state.

### 5.8 `clean`

Removes containers, temporary contexts, snapshots, and optionally cached images according to a retention policy. It should never remove user source files.

---

## 6. Workload and input specification

### 6.1 Profile format

Use YAML or JSON with a versioned schema. YAML is friendlier for users; JSON should be accepted for automation.

```yaml
schema_version: 1
name: image-demo
repository:
  source: https://github.com/example/project
  ref: main
  commit: optional-commit-sha
  subdirectory: .

environment:
  base_image: python:3.11-slim
  language: python
  working_directory: /repo
  network:
    build: enabled
    runtime: disabled
  resources:
    memory: 2gb
    cpus: 2
    timeout_seconds: 900
    pids: 256
    output_bytes: 1073741824

setup:
  manifests:
    - requirements.txt
  test_command: ["python", "-m", "pytest", "--collect-only", "-q"]

inputs:
  - id: source-image
    type: file
    source: ./data/input.png
    destination: /inputs/input.png
    access: read-only
  - id: config
    type: file
    media_type: application/json
    source: ./data/config.json
    destination: /inputs/config.json
  - id: parameters
    type: env
    values:
      MODE: test

command:
  argv: ["python", "process.py", "--input", "{source-image}"]
  shell: false

readiness:
  type: process
  timeout_seconds: 60

outputs:
  - id: processed
    type: file
    path: /repo/results/output.png
    destination: ./results/output.png
  - id: logs
    type: directory
    path: /repo/results
    destination: ./results

success:
  type: exit_code
  value: 0
```

### 6.2 Supported input types

The first implementation should support:

- local file;
- local directory/archive;
- HTTP(S) URL with allowlist and size checks;
- environment variable;
- command-line argument;
- standard input;
- secret reference resolved by an external secret provider;
- optional GPU/device request, disabled by default.

“Any kind of input” means these categories can be composed in a profile. It does not mean that the tool can understand an undocumented proprietary input format without an adapter.

Placeholders such as `{source-image}` in `command.argv` resolve to the validated container destination of the named input. Substitution happens before process launch and does not invoke shell expansion.

### 6.3 Input safety and normalization

Before execution:

1. Resolve the source to a canonical local path or managed download.
2. Validate type, size, checksum, and filename.
3. Reject path traversal and dangerous symlinks.
4. Copy or mount the input read-only at a controlled destination.
5. Record content hash and provenance in the run manifest.
6. Never place secrets directly in the Dockerfile, event log, or report.
7. Require explicit opt-in for network downloads and external services.

Use a default maximum input size and a separate maximum output size. Values must be configurable, not silently unlimited.

### 6.4 Output specification

Outputs should be declarative:

- file;
- directory;
- glob;
- stdout artifact;
- structured JSON result;
- URL or remote upload, only with explicit opt-in.

Every collected artifact receives:

- source path;
- destination path;
- byte size;
- SHA-256 checksum;
- media/type hint;
- collection status.

A workload that produces files but no declared output paths should return `outputs_undeclared`, not silently discard them.

---

## 7. Repository adapters and profiles

### 7.1 Adapter model

An adapter describes how to interact with a repository family. It contains no arbitrary code; it declares supported manifests, commands, input conventions, output conventions, and readiness checks.

Initial adapters:

1. **Python CLI/library**
2. **Python test suite**
3. **Python web service**
4. **Node.js CLI/test service** as an optional extension
5. **Docker Compose workload** as a later extension, not a default

### 7.2 Generic fallback

When no adapter matches, the generic inspector may infer candidates, but the profile must be marked:

```yaml
inference:
  status: needs_review
  confidence: low
```

The tool can run a low-risk preparation attempt, but it should not invent a workload command without user confirmation.

### 7.3 External services

For repositories requiring a database, Redis, browser, GPU, or cloud API, use a service profile:

```yaml
services:
  - name: redis
    image: redis:7-alpine
    healthcheck: ["redis-cli", "ping"]
  - name: app
    image: ${APP_IMAGE}
    depends_on: [redis]
```

This is not part of the first research MVP, but the profile schema should leave room for it.

---

## 8. Selected architecture

```text
CLI / API
  |
  v
Run Planner and Profile Validator
  |
  +--> Repository Resolver
  +--> Input/Artifact Resolver
  +--> Adapter Resolver
  |
  v
External Repair Controller
  |
  +--> Repository Inspector
  +--> Dependency Planner
  +--> Action Validator
  +--> Event Store
  +--> Loop Detector
  |
  v
Internal Docker Runtime
  |
  +--> Persistent Container
  +--> Checkpoint Manager
  +--> Log/Result Processor
  +--> Verifier
  |
  v
Dockerfile Synthesizer
  |
  v
Clean Replay Validator
  |
  v
Workload Runner and Output Collector
```

### Component responsibilities

#### Repository resolver

Responsible for URL/path validation, cloning, fixed refs, subdirectories, submodules policy, LFS policy, and repository metadata.

#### Repository inspector

Responsible for reading documentation, manifests, CI files, lockfiles, source layout, and candidate commands without executing the workload.

#### Action validator

Responsible for rejecting unknown actions, unsafe paths, arbitrary shell strings, invalid package specifications, unsupported base images, and secret leakage.

#### Repair controller

Responsible for the bounded state machine. It does not execute commands directly.

#### Internal Docker runtime

Responsible for all state-changing execution. The controller must not mutate the host environment.

#### Event store

An append-only JSONL record is the source of truth for setup, repair, and synthesis.

#### Verifier

Runs deterministic checks. The LLM may explain a failure but cannot mark it successful by itself.

#### Dockerfile synthesizer

Generates a Dockerfile deterministically from accepted events and package inventory.

#### Workload runner

Starts the declared application command only after environment verification and collects declared outputs.

---

## 9. Solving Repo2Run gaps

### Gap 1: One-shot application execution instead of environment construction

**Problem:** The current code infers an application startup command and uses text matching to report success.

**Chosen solution:** Separate phases:

```text
inspect -> prepare -> verify -> replay -> run
```

The first release uses `pytest --collect-only` as the environment verifier. Application execution is an optional workload stage.

### Gap 2: Missing LLM/ReAct interaction loop

**Problem:** No model-driven repair loop exists.

**Chosen solution:** A constrained JSON action loop:

```json
{
  "thought": "Python 3.10 cannot import StrEnum",
  "action": "set_python",
  "arguments": {"version": "3.11"},
  "reason": "The collection error indicates a version mismatch"
}
```

Controls:

- fixed model and prompt version;
- strict action schema;
- maximum 10–12 actions;
- maximum token and wall-clock budgets;
- repeated-failure detection;
- no unrestricted source/test edits in the MVP;
- every action recorded and replayable.

### Gap 3: No persistent dual environment

**Problem:** Current Docker execution is a one-shot container.

**Chosen solution:** External controller plus persistent internal Docker session. The controller owns state transitions; the container owns execution state.

### Gap 4: No rollback after pollution

**Problem:** A failed package installation can partially modify a container.

**Chosen solution:** Checkpoint before each mutating action. On failure, discard the contaminated container and restore the last valid snapshot.

Implementation choices:

- Docker commit snapshots for the first implementation;
- semantic-action boundaries rather than one snapshot per raw shell token;
- snapshot labels tied to run ID and action ID;
- cleanup after successful synthesis;
- optional command-level checkpoint mode for ablation.

### Gap 5: No dependency waiting/conflict system

**Problem:** `pip install -r requirements.txt` is too coarse.

**Chosen solution:** Hybrid dependency pipeline:

```text
manifest parse
  -> static import/dependency extraction
  -> import-to-package mapping
  -> PyPI metadata retrieval
  -> native resolver (pip/uv)
  -> structured error classification
  -> bounded repair
  -> exact package inventory
```

Rules:

- LLM does not freely invent package versions when metadata is available.
- Use PyPI metadata and resolver constraints first.
- Use the LLM only for missing metadata, ambiguous import mappings, or unsupported syntax.
- Parse `pip` errors into structured constraints where possible.
- Persist successful package mappings, but revalidate them before reuse.
- Mark deprecation, renamed-package, and platform-SDK failures separately.

The Z3/SMT approach from SMT-LLM is a stretch research extension, not a dependency for the first release.

### Gap 6: Missing base-image adaptation

**Problem:** Current images are hard-coded and old.

**Chosen solution:** Versioned base-image catalog with immutable digests when available. Support Python 3.10/3.11 first. A base-image change starts a new clean session and invalidates previous mutating events.

### Gap 7: Unbounded or unhelpful output

**Problem:** Long logs can block pipes or overwhelm the LLM.

**Chosen solution:** Stream stdout/stderr continuously to files, maintain byte counts, and expose:

- first 2–4 KB;
- last 4–8 KB;
- error summary;
- full-log hash;
- optional full local log path.

The policy receives a bounded observation. The user can inspect the complete log locally.

### Gap 8: No reliable Dockerfile synthesis

**Problem:** The current temporary Dockerfile is not a deliverable.

**Chosen solution:** Deterministic event-to-Dockerfile synthesis:

- final `FROM`;
- fixed `WORKDIR`;
- repository copy;
- approved `ENV` values;
- successful `RUN` actions only;
- exact package versions;
- no test or inspection actions;
- reset after base-image changes;
- saved lockfile;
- clean build and collection replay.

Do not use a second free-form LLM call to rewrite the Dockerfile.

### Gap 9: Host fallback is unsafe

**Problem:** Docker failure silently selects host subprocess execution.

**Chosen solution:** Docker-only default. If Docker is unavailable, return `preflight_failed`. An explicit `--unsafe-host-mode` may exist for trusted local development only, clearly marked and never used in benchmark results.

### Gap 10: Weak provenance and status reporting

**Problem:** Reports do not contain enough information to reproduce or compare runs.

**Chosen solution:** Versioned run manifest containing:

- source URL and commit;
- base-image name/digest;
- resolved configuration;
- profile hash;
- input hashes;
- action/event log;
- package lockfile;
- Dockerfile;
- build and replay statuses;
- output hashes;
- model/prompt version, if used;
- resource usage;
- failure category.

### Gap 11: No workload input/output layer

**Problem:** Environment setup research usually stops at tests and does not answer what a user wants to execute or retrieve.

**Chosen solution:** Add a versioned workload profile and artifact resolver after environment verification. The environment layer remains reusable for CLI, tests, servers, and media workloads.

### Gap 12: No user-facing recovery and cleanup

**Problem:** Failed runs leave containers, images, snapshots, and logs behind.

**Chosen solution:** Labels, retention policies, `autorun clean`, dry-run cleanup, and a `needs_human_configuration` report containing the exact unresolved requirement.

---

## 10. Solutions considered and selected

| Problem | Candidate solutions | Selected choice | Reason |
|---|---|---|---|
| Host execution | Host subprocess, Docker, VM/rootless Docker | Docker default; VM/rootless for high-risk evaluation | Better safety/reproducibility; Docker is practical for a student project |
| Agent commands | Unrestricted bash, typed actions, typed actions plus unsafe escape hatch | Typed actions only in MVP | Limits accidental host damage and makes replay possible |
| Dockerfile creation | Direct LLM Dockerfile, event synthesis, template-only | Event synthesis with deterministic verifier | Avoids hallucinated and non-replayable build steps |
| Dependency repair | LLM guessing, graph lookup, native resolver, hybrid resolver | Native resolver first; LLM only for gaps | Faster, cheaper, and more reproducible |
| LLM role | Fully autonomous agent, summarizer only, bounded controller | Bounded controller with summarizer | Balances repair ability and auditability |
| Checkpointing | No rollback, commit before every command, semantic-action checkpoints | Semantic checkpoints first; command-level ablation | Balances reliability and disk/time overhead |
| State storage | Unbounded conversation, compressed event log, full raw log | Compressed event log plus archived raw logs | Maintains reasoning memory without flooding context |
| Reuse | Re-run from scratch, use repository Dockerfile, use profile memory | Validate repository files, then use verified profile memory | Avoids trusting stale or malicious instructions |
| Input handling | One universal `--input`, format-specific flags, typed profile | Typed profile with convenience flags | Supports heterogeneous inputs without pretending formats are identical |
| Output handling | Print everything, copy entire container, declared artifacts | Declared artifacts plus checksums | Avoids data loss and accidental secret/output exposure |
| Test validation | Exit code only, LLM judgment, exit code plus test parser and collection | Exit code plus parser/collection | Deterministic and auditable |
| Benchmark scale | 420 repositories immediately, 20–30 frozen repositories | 20–30 for project; optional extension | Achievable and statistically honest |
| Model training | Fine-tune model, prompt/controller, use external API | Prompt/controller first | Appropriate for final-year scope and budget |
| Multi-language | All languages immediately, Python first with adapter interface | Python first | Aligns with Repo2Run and current codebase |
| Network | Always enabled, always disabled, policy per profile | Default disabled; explicit build/runtime policy | Supports dependency installation without unrestricted runtime access |

---

## 11. User-perspective feature plan

Each feature below is selected because it removes a repeated manual step, not merely because it is technically possible.

| ID | Feature | User problem solved | Priority | Release |
|---|---|---|---|---|
| U1 | `doctor` | Missing Docker/Git/runtime discovered only after failure | P0 | 1 |
| U2 | Fixed commit and profile generation | Wrong branch or changing repository | P0 | 1 |
| U3 | Documentation/CI/manifest inspection | User must read multiple files manually | P0 | 1 |
| U4 | One-command environment preparation | Repeated install/setup steps | P0 | 1 |
| U5 | Explicit missing-configuration report | Unclear environment variables/secrets | P0 | 1 |
| U6 | Typed input manifest | User does not know where files must be placed | P0 | 2 |
| U7 | Output collection and checksums | Results remain in container or wrong directory | P0 | 2 |
| U8 | Readiness/health checks | Process is running but service is not ready | P0 | 2 |
| U9 | Automatic free-port allocation | Port conflicts | P1 | 2 |
| U10 | Progress and live logs | User cannot tell whether setup is progressing | P1 | 2 |
| U11 | Failure classification and suggested next action | Long raw errors require expert diagnosis | P0 | 2 |
| U12 | Clean replay command | “It worked once” reproducibility problem | P0 | 2 |
| U13 | Profile memory/case-based reuse | Similar repositories are rebuilt from scratch | P1 | 3 |
| U14 | `clean` command | Containers/images/snapshots accumulate | P1 | 3 |
| U15 | External service profiles | Apps requiring Redis/DB/browser cannot run | P2 | 4 |
| U16 | GPU/device profiles | ML/media workloads need hardware | P2 | 4 |
| U17 | Web upload adapter | Browser-only applications cannot use CLI paths | P2 | 4 |
| U18 | Offline/provenance bundle | Re-running later requires network | P2 | 4 |

---

## 12. Research questions and hypotheses

### RQ1: User effort

**Question:** Does the CLI reduce the number of manual commands and time required to reach a first successful workload run?

**Hypothesis:** A profile-driven Docker pipeline will reduce setup time and manual intervention compared with following repository documentation manually.

### RQ2: Environment reliability

**Question:** Does bounded iterative repair outperform a one-shot setup script?

**Metric:** DGSR and EBSR on a frozen benchmark.

### RQ3: Transactional rollback

**Question:** Does rollback improve clean Dockerfile replay?

**Comparison:** Iterative repair with rollback versus iterative repair without rollback.

### RQ4: Checkpoint granularity

**Question:** Can semantic-action checkpoints reduce snapshot overhead without reducing replay reliability?

**Comparison:** Command-level versus semantic-action checkpoints.

### RQ5: Workload generality

**Question:** Can one environment layer support different workload types without repository-specific code changes?

**Workloads:** CLI, pytest, basic web service, and file-processing application.

### RQ6: Determinism versus LLM assistance

**Question:** How much does the LLM improve success over a deterministic profile/inspector baseline?

**Comparison:** Deterministic-only, LLM-assisted, and bounded autonomous modes.

---

## 13. Evaluation plan

### 13.1 Benchmark

Create a frozen manifest of 20–30 public repositories with:

- repository URL;
- commit SHA;
- license;
- primary language;
- project type;
- supported manifest;
- expected setup/test command;
- declared workload profile;
- input fixtures;
- expected output checks;
- inclusion/exclusion reason.

Stratify by:

- simple versus complex dependency setup;
- CLI/test/web project;
- one manifest versus multiple setup files;
- documented versus CI-heavy setup.

Do not add repositories after seeing whether the proposed system succeeds.

### 13.2 Conditions

| Condition | Description |
|---|---|
| C0 | Manual/README-inspired deterministic baseline |
| C1 | One-shot LLM profile/Dockerfile generation |
| C2 | Iterative typed actions without rollback |
| C3 | Full transactional repair with semantic checkpoints |
| C4 | C3 with command-level checkpoints on a subset |

Run each primary condition at least twice per repository where budget permits.

### 13.3 Metrics

#### Environment metrics

- DGSR: saved Dockerfile builds.
- EBSR: saved Dockerfile builds and pytest collection succeeds in a clean container.
- Replay rate: independent rebuild and verification succeeds.
- Test pass rate among collectable environments.
- Build time, dependency-install time, and verification time.
- Number of actions and retries.
- Number of rollbacks and successful recoveries.
- Snapshot count, time, and estimated storage.
- Dockerfile/image size.
- LLM tokens and cost.

#### User-experience metrics

- Number of manual commands.
- Time to first successful run.
- Number of user corrections/adapter edits.
- Percentage of runs requiring `needs_input`, `needs_secret`, or `needs_adapter`.
- Output completeness and checksum verification.
- Error-message usefulness rating.
- Optional small user study comparing manual instructions with the CLI.

#### Safety metrics

- Host execution count: must be zero in research mode.
- Escapes from the declared root.
- Secret exposure incidents.
- Resource-limit violations.
- Network-policy violations.
- Cleanup success.

### 13.4 Statistical analysis

Because the same repositories are evaluated under multiple conditions:

- use paired repository-level comparisons;
- report absolute success differences;
- use Wilson intervals for proportions;
- use an exact paired McNemar test for binary outcomes where appropriate;
- use paired bootstrap intervals for time and cost;
- report negative and inconclusive results honestly.

Do not use a p-value alone as evidence of practical improvement.

### 13.5 Test strategy

#### Unit tests

- profile schema validation;
- repository URL/path validation;
- manifest parsing;
- input path normalization;
- output matching;
- action validation;
- error classification;
- Dockerfile synthesis.

#### Integration tests

- Python CLI project;
- FastAPI/Flask project;
- file-processing project;
- failed dependency install followed by rollback;
- generated Dockerfile clean rebuild;
- pytest collection;
- input mounting and output collection;
- port allocation/readiness.

#### Adversarial/security tests

- repository-controlled Dockerfile;
- malicious filenames and symlinks;
- shell metacharacters in metadata;
- oversized input/output;
- path traversal;
- secret redaction;
- network access attempts;
- process-tree cleanup;
- snapshot cleanup;
- resource exhaustion.

---

## 14. Current-code migration plan

| Current file/module | Migration decision |
|---|---|
| `src/main.py` | Replace linear flow with CLI commands and a run planner. Keep a compatibility command for the old behavior. |
| `src/cloner.py` | Harden URL/ref handling, record commit SHA, support subdirectory/LFS policy, and eliminate destructive default output behavior. |
| `src/detector.py` | Replace framework guessing with repository inspection and adapter selection. Keep as a heuristic helper, not the source of truth. |
| `src/sandbox.py` | Split into Docker runtime, checkpoint manager, bounded log processor, and verifier. Remove automatic host fallback. |
| `src/reporter.py` | Introduce versioned run/environment/workload manifests and deterministic serialization. |
| `src/config.py` | Resolve one immutable run configuration and validate resource/security values. |
| `tests/` | Add profile, action, Docker integration, rollback, replay, artifact, and adversarial tests. Fix the existing reporter contract test. |
| `autorun-output/` | Treat as generated data and add it to `.gitignore`. Do not use it as source-controlled fixtures. |
| `test-repo/` | Replace the empty fixture with small deterministic projects for each adapter. |

No current application-runner heuristic should be used as the environment success criterion.

---

## 15. Implementation phases

### Phase 0 — Freeze the research contract

**Deliverables**

- final scope statement;
- profile schema v1;
- action schema v1;
- status and failure taxonomy;
- benchmark inclusion rules;
- threat model.

**Exit criteria**

A user can read the specification and know exactly what is supported, unsupported, and measured.

### Phase 1 — Deterministic foundation

Implement:

- `doctor`;
- `inspect`;
- repository resolver with fixed commit;
- manifest/CI/documentation inspection;
- profile generation and validation;
- Docker-only preflight;
- structured run manifest;
- basic cleanup.

**Exit criteria**

A supported repository can be inspected and a valid profile generated without executing the workload.

### Phase 2 — Environment preparation

Implement:

- Python base-image catalog;
- requirements/pyproject subset;
- dependency inventory;
- persistent container;
- bounded logs;
- pytest collection;
- Dockerfile and lockfile persistence;
- clean build/replay.

**Exit criteria**

A deterministic profile can produce a Dockerfile that builds and passes collection for simple fixtures.

### Phase 3 — Transactional repair

Implement:

- typed actions;
- external controller;
- pre-action snapshots;
- rollback;
- error classification;
- Python version switching;
- loop detection;
- action/event journal.

**Exit criteria**

A deliberately failing package action is rejected, the previous environment is restored, and the final successful trajectory synthesizes a replayable Dockerfile.

### Phase 4 — Workload execution

Implement:

- profile-based input mounting;
- file/directory/URL/env/argument inputs;
- output collection and checksums;
- CLI workload runner;
- basic web-service runner;
- readiness/health checks;
- port allocation;
- artifact reports.

**Exit criteria**

A user can run at least one CLI workload, one test workload, and one web workload from a profile.

### Phase 5 — Memory and usability

Implement:

- verified profile memory;
- nearest-version retrieval;
- revalidation before reuse;
- progress display;
- `needs_human_configuration` guidance;
- retention and cleanup commands;
- documentation and examples.

**Exit criteria**

Repeated runs are faster without silently trusting stale or unsafe profiles.

### Phase 6 — Evaluation and paper results

Implement:

- frozen benchmark manifest;
- C0–C4 experiment runner;
- metrics and failure reports;
- paired analysis;
- confidence intervals;
- reproducible result tables;
- final paper results.

**Exit criteria**

Every paper claim is backed by a stored artifact, fixed configuration, and reproducible command.

---

## 16. Example implementation timeline

This is an example schedule for a 14–16 week final-year project; adjust it to your academic deadline.

| Period | Focus | Main output |
|---|---|---|
| Week 1 | Scope, schema, threat model | Profile/action specification |
| Week 2 | CLI and repository inspection | `doctor`, `inspect`, `init` |
| Week 3 | Docker runtime and manifests | Deterministic environment build |
| Week 4 | Logs, verifier, artifacts | Simple replayable Python environment |
| Week 5 | Workload profile/input resolver | File and argument execution |
| Week 6 | Output collector/readiness | CLI/test workload support |
| Week 7 | Action controller | Typed LLM/heuristic actions |
| Week 8 | Checkpoints/rollback | Transactional repair |
| Week 9 | Python version/dependency repair | Version switching and conflict recovery |
| Week 10 | Profile memory/cleanup | Reuse and lifecycle management |
| Week 11 | Web adapter/basic services | Additional workload class |
| Week 12 | Adversarial/security tests | Safe failure behavior |
| Week 13 | Benchmark runs | Frozen dataset and raw results |
| Week 14 | Analysis and paper | Results, limitations, final draft |
| Week 15–16 | Buffer and presentation | Reproduction package and demo |

If time is shorter, remove the web adapter, profile memory, and Node support before removing rollback, replay, or the verifier.

---

## 17. Risk register and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| Repository requires an undocumented service | High | High | `needs_adapter`/`needs_human_configuration`; service profiles; never fake success |
| LLM hallucinates a package or command | High | High | Typed actions, PyPI metadata, native resolver, deterministic verifier |
| Failed action contaminates environment | Medium | High | Pre-action checkpoints and rollback |
| Docker build executes malicious code | Medium | High | Disposable/rootless runtime, restricted credentials/network, explicit trust warning |
| Build hangs or consumes resources | High | High | Phase deadlines, memory/CPU/PID/disk limits, process-tree cleanup |
| External package index changes | High | Medium | Lock exact versions, cache metadata, record hashes, optional historical index snapshots |
| Input path escapes container | Medium | High | Canonicalize, reject symlinks/traversal, mount read-only |
| Output data is lost or mixed | Medium | Medium | Explicit output contract, checksums, run directory isolation |
| LLM/provider cost is too high | Medium | Medium | Deterministic mode, small model option, caching, bounded actions, local model adapter |
| Cross-platform behavior differs | High | Medium | Linux-first research branch; Docker Desktop support; defer Windows containers |
| User cannot understand failure | Medium | High | Phase-specific status, plain-language summary, next action, full log link |
| Model success is overestimated | Medium | High | Clean replay, independent verifier, no LLM-only success declaration |
| Licensing or secret leakage | Low/medium | High | License manifest, secret references, redaction, no raw credentials in artifacts |

---

## 18. Definition of done for the final-year project

The project is complete when it can demonstrate all of the following:

1. `autorun doctor` identifies host prerequisites.
2. `autorun inspect` creates an evidence-backed profile.
3. `autorun prepare` creates an isolated environment.
4. A failed state-changing action is rolled back.
5. A successful trajectory produces a deterministic Dockerfile and lockfile.
6. `autorun replay` rebuilds and verifies the environment from scratch.
7. A user can provide files/directories, environment values, and arguments through a profile.
8. The tool collects declared output files with checksums.
9. A basic web workload can report readiness and expose a host URL.
10. Unsupported cases return actionable statuses instead of false success.
11. The benchmark can reproduce DGSR, EBSR, replay, time, action, and failure metrics.
12. Security tests demonstrate no automatic host fallback and no path escape.
13. The final paper clearly distinguishes inspiration from original contribution.
14. A new user can reproduce the demo from the README.

---

## 19. Decisions required before implementation begins

The plan uses safe defaults, but these choices should be confirmed before coding:

1. **Primary language:** Python 3.10/3.11 is recommended.
2. **LLM provider:** a fixed hosted model, local model, or deterministic-only first phase.
3. **Workload classes for the first demo:** CLI, pytest, and one web service are recommended.
4. **Input types for the first demo:** files, directories, environment variables, and CLI arguments are recommended; URLs can follow.
5. **Evaluation budget:** 20 repositories and two runs per condition are recommended for a final-year project.
6. **Host policy:** Docker-only for untrusted repositories; no automatic host fallback.

No implementation should begin with a broader language/input scope until these decisions are fixed.

---

## 20. References

1. R. Hu, C. Peng, X. Wang, J. Xu, and C. Gao, “Repo2Run: Automated Building Executable Environment for Code Repository at Scale,” arXiv:2502.13681v4, 2025.
2. L. Milliken, S. Kang, and S. Yoo, “Beyond pip install: Evaluating LLM Agents for the Automated Installation of Python Projects,” SANER 2025.
3. I. Bouzenia and M. Pradel, “You Name It, I Run It: An LLM Agent to Execute Tests of Arbitrary Projects,” ISSTA 2025.
4. A. Eliseeva et al., “EnvBench: A Benchmark for Automated Environment Setup,” 2025.
5. K. Vergopoulos, M. N. Müller, and M. Vechev, “Automated Benchmark Generation for Repository-Level Coding Tasks,” 2025.
6. A. Bartlett, C. Liem, and A. Panichella, “The Last Dependency Crusade: Solving Python Dependency Conflicts with LLMs,” 2025.
7. K. Chowdhury, D. Banik, and S. I. Shamim, “Breaking the Dependency Chaos: A Constraint-Driven Python Dependency Resolution Strategy with Selective LLM Imputation,” 2026.
8. K. Fu et al., “Multi-Docker-Eval: A ‘Shovel of the Gold Rush’ Benchmark on Automatic Environment Building for Software Engineering,” 2026.
9. J. Zhang et al., “DockSmith: Scaling Reliable Coding Environments via an Agentic Docker Builder,” 2026.
10. L. Guo et al., “SWE-Factory: Your Automated Factory for Issue Resolution Training Data and Evaluation Benchmarks,” 2026.
11. K. Li et al., “RepoLaunch: Automating Build and Management of Code Repositories across Languages and Platforms,” 2026.
12. B. Bogin et al., “SUPER: Evaluating Agents on Setting Up and Executing Tasks from Research Repositories,” EMNLP 2024.
13. Z. Siegel et al., “CORE-Bench: Fostering the Credibility of Published Research Through a Computational Reproducibility Agent Benchmark,” 2024/2026 revision.
14. N. Jain et al., “R2E: Turning any GitHub Repository into a Programming Agent Environment,” ICML 2024.
15. F. Chirigati et al., “ReproZip: Using Provenance to Support Computational Reproducibility,” 2013.
16. Z. Ni et al., “GitTaskBench: A Benchmark for Code Agents Solving Real-World Tasks Through Code Repository Leveraging,” 2025.
