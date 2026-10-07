# Repo2Run Gap Analysis and Project Strategy

**Status:** Design document for the final-year major project  
**Reference:** Hu et al., *Repo2Run: Automated Building Executable Environment for Code Repository at Scale*, arXiv:2502.13681v4 (2025)  
**Project:** `autorun-hackathon`

## 1. Executive decision

The current code is a useful prototype for cloning a repository, detecting a small set of frameworks, starting an application, and writing a report. It is not yet an implementation of Repo2Run's central method.

The project should be narrowed to the following goal:

> Build a constrained, Docker-based system that repairs and validates Python test environments, records a successful action trajectory, synthesizes a reusable Dockerfile, and verifies that Dockerfile from a clean container.

The primary success criterion should be:

```text
python -m pytest --collect-only -q
```

successfully runs in a fresh container. Test pass rate should be measured separately; environment-building success must not be confused with whether every repository test passes.

## 2. What Repo2Run actually addresses

The paper identifies two central problems:

1. **Finding a valid environment-building trajectory.** A general coding agent may not know how to select a base image, install dependencies, set environment variables, or respond to test-collection errors.
2. **Synthesizing a Dockerfile that still builds.** A failed command can partially modify a container. Replaying that failed command in a Dockerfile produces an unbuildable environment.

Repo2Run addresses these with:

- an LLM/ReAct-style action-observation loop;
- an internal Docker environment and an external controller;
- specialized environment-monitoring, dependency, test, code-editing, and shell actions;
- rollback of failed state-changing actions;
- Python-version changes that reset the build history;
- output truncation;
- deterministic Dockerfile synthesis from successful events;
- DGSR and EBSR evaluation on a frozen Python benchmark.

The paper's DGSR means that the generated Dockerfile builds. Its EBSR means that the Dockerfile builds and pytest can run; test failures caused by repository defects do not necessarily make the environment unsuccessful.

## 3. Gap matrix for the current repository

| ID | Repo2Run capability or limitation | Current implementation | Consequence | Proposed solution | Priority |
|---|---|---|---|---|---|
| G1 | Environment-building task and verifier | `src/main.py:3-5` and `src/main.py:173-200` clone, detect, start an app, and report. `src/sandbox.py:269-329` and `455-535` infer success from process exit or startup text. | A repository can be reported successful even if pytest cannot collect its tests. | Define independent `build`, `collect`, `replay`, and optional `smoke` statuses. Make pytest collection the primary verifier. | P0 |
| G2 | LLM/ReAct action-observation loop | No LLM client, prompt, action parser, controller, or iterative repair loop exists in `src/`. | The system cannot respond to dependency conflicts, Python-version errors, or missing modules. | Add a bounded JSON action loop with a fixed model, strict action schema, action limit, token limit, and termination rules. | P0 |
| G3 | Persistent internal environment plus external controller | `src/sandbox.py:183-335` builds and runs a one-shot container. There is no persistent repair session or external event processor. | A failed action ends the attempt instead of returning to a known state. | Refactor Docker execution into a persistent internal environment controlled by a separate state machine. | P0 |
| G4 | Rollback after failed or polluting actions | No `docker commit` snapshot or restore operation exists. | Partial package/file changes can contaminate later reasoning and make a generated Dockerfile irreproducible. | Snapshot before mutating actions; on failure, discard the container and recreate it from the last valid snapshot. | P0 |
| G5 | Pytest-based checkpoint | Pytest appears only in purpose-inference keyword lists (`src/main.py:118-120`, `src/reporter.py:317-319`). | There is no environment verifier. | Add a test detector and run `python -m pytest --collect-only -q` with a bounded timeout. Store return code, collected count, and complete logs. | P0 |
| G6 | Deterministic Dockerfile synthesis | `src/sandbox.py:218-225` creates a temporary template; it is deleted with the temporary directory. | The main reusable output of Repo2Run is missing. | Record successful state-changing events in JSONL and generate `FROM`, `ENV`, `COPY`, and `RUN` statements deterministically. Save the final Dockerfile and lockfile. | P0 |
| G7 | Dependency waiting list and conflict handling | Docker always runs `pip install -r requirements.txt` (`src/sandbox.py:195-201`); the fallback repeats the same approach. | `pyproject.toml`, Pipenv, Poetry, lockfiles, and version conflicts are not handled consistently. | Restrict the first version to `requirements.txt` and a small `pyproject.toml` subset. Install packages one at a time, record exact versions, and classify conflicts. | P0 |
| G8 | Base-image adaptation | Images are hard-coded to `python:3.9-slim` and `node:16-slim` (`src/sandbox.py:198-205`). | Python-version incompatibilities cannot be repaired. | Support only Python 3.10 and 3.11. A version change starts a new clean container and invalidates prior state-changing events. | P0 |
| G9 | Safe execution of untrusted repositories | Docker initialization failure silently selects host subprocess execution (`src/sandbox.py:27-45`, `163-169`). The fallback installs into the host and uses `shell=True` (`sandbox.py:359-410`). | Repository code can access host files, network, and user privileges. | Make Docker-only the default for research runs. Remove automatic host fallback. Use disposable/rootless Docker, resource limits, restricted networking, and no secrets. | P0 |
| G10 | Repository-controlled Docker build instructions | The generated Dockerfile is written before repository files are copied into the same context (`sandbox.py:218-241`). A repository `Dockerfile` or `.dockerignore` can affect the build. | Repository-controlled build instructions and package lifecycle code execute before runtime limits apply. | Use a separate immutable build context, copy the repository under a fixed subdirectory, reject conflicting build files, and apply build time/resource policy. | P0 |
| G11 | Output processing and bounded observations | Subprocess pipes are filled before `communicate()` is called (`sandbox.py:405-411`, `455-464`); output is not bounded. Docker returns combined logs rather than stdout/stderr. | Long output can block processes, consume memory, or flood an LLM context. | Drain stdout/stderr continuously into files or bounded buffers. Store byte counts and head/tail excerpts for the agent, with full logs archived separately. | P0 |
| G12 | Clean Dockerfile replay | No saved Dockerfile is rebuilt after the interactive process. | Reproducibility cannot be measured. | Build the saved Dockerfile in a clean context, run collection in a new container, and record image digest and replay status. | P0 |
| G13 | Environment monitoring | The system records process metrics but cannot inspect files, Python version, installed packages, or dependency trees. | The agent has little reliable state with which to choose a repair. | Add read-only `inspect_files`, `show_python`, and `list_packages` actions. Capture exact package versions. | P1 |
| G14 | Result provenance and reproducibility | `src/reporter.py:39-53` does not record repository SHA, base image, model/prompt version, action history, Dockerfile, or image digest. | Results cannot be audited or compared reliably. | Use a versioned result schema and store all provenance beside each run. | P1 |
| G15 | Benchmark and aggregate evaluation | No frozen benchmark, DGSR/EBSR script, baseline, or ablation exists. | The project cannot support a research claim. | Create a fixed 20-repository Python benchmark, run paired conditions, and report DGSR, EBSR, replay, time, actions, and failures. | P1 |
| G16 | Language breadth | Node.js heuristics consume implementation time (`src/detector.py:22-35`, `sandbox.py:648-741`) but are not evaluated. | Scope is broader without stronger evidence. | Make Python the evaluated research branch; retain Node only as an optional engineering feature. | P1 |

## 4. Recommended research contribution

Rollback itself should not be presented as novel because Repo2Run already introduces it. A more defensible final-year contribution is:

> **Transactional repair and replay of Python test environments, with an empirical study of command-level versus semantic-action checkpoint granularity.**

The proposed system has three parts:

1. **Constrained repair:** an LLM may choose only validated actions such as inspecting files, installing a package, setting an environment variable, changing between Python 3.10 and 3.11, or running pytest collection.
2. **Transactional environment:** every mutating action is checkpointed. Failed actions are rejected and the environment is restored.
3. **Replayable artifact:** successful events are converted deterministically into a Dockerfile and exact dependency lockfile, which are rebuilt in a clean container.

The research question is whether semantic-action checkpoints retain the reliability of command-level checkpoints while reducing snapshot time and storage overhead.

## 5. Narrow scope for the first evaluated version

To remain achievable for a final-year project, the first study should use:

- Python 3.10 and 3.11 only;
- `pip` as the package manager;
- `requirements.txt` and a documented subset of `pyproject.toml`;
- pytest-compatible public repositories;
- local, public, non-GPU repositories without private credentials;
- Docker-only execution;
- no source or test-file editing;
- a fixed LLM model and prompt version;
- a maximum of 10–12 actions and a declared wall-clock limit per attempt.

Node.js, CUDA, proprietary services, arbitrary shell editing, and large-scale repository crawling should be deferred.

## 6. Implementation roadmap

### Phase 1 — Define a valid success contract

- Refactor the current application runner into an optional smoke-test module.
- Add `build_status`, `collect_status`, `replay_status`, and `smoke_status`.
- Disable automatic host-subprocess fallback in research mode.
- Record repository URL, commit SHA, base image, image digest, and resolved configuration.

### Phase 2 — Build the transactional Docker environment

- Keep a persistent container for one repository attempt.
- Add typed actions and strict validation.
- Add bounded output capture.
- Implement snapshot-before-mutation and restore-after-failure.
- Implement Python 3.10/3.11 switching.

### Phase 3 — Add verification and synthesis

- Implement `python -m pytest --collect-only -q`.
- Persist an event log.
- Generate a deterministic Dockerfile and lockfile.
- Rebuild and validate the generated Dockerfile from scratch.

### Phase 4 — Run the study

- Freeze a 20-repository benchmark manifest with commit SHAs.
- Compare the current heuristic baseline, one-shot LLM generation, iterative repair without rollback, and the proposed rollback system.
- Run each condition twice on the same repositories.
- Report DGSR, EBSR, clean replay rate, time, action count, snapshot overhead, and failure categories.

## 7. Definition of done

The project is ready for final demonstration when it can:

1. Accept a fixed public Python repository and commit.
2. Build a clean Docker environment.
3. Execute typed repair actions with bounded output.
4. Reject and roll back a failed state-changing action.
5. Validate pytest collection.
6. Save a Dockerfile and exact dependency lockfile.
7. Rebuild that Dockerfile in a clean container.
8. Produce an auditable JSON event log and report.
9. Run an evaluation script over a frozen benchmark.
10. Clearly report unsupported repositories and infrastructure failures instead of claiming success.

## 8. Important academic boundary

This project should be described as a **lightweight, controlled implementation inspired by Repo2Run**, not as a complete reproduction of the paper. The original paper evaluates 420 Python repositories and a large LLM-agent system. This project should instead make a narrower empirical claim about transactional repair, checkpoint granularity, and clean replay on a declared benchmark.
