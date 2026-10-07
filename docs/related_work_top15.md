# Top 15 Related Research Papers — Autorun / EnvRun Project

Saved 2026-10-05. I cannot retain memory across chat sessions, so this file is the
persistent record of the most relevant literature for the Autorun Hackathon project.

| # | Paper | Venue | arXiv | Why it matters to this project |
|---|-------|-------|-------|--------------------------------|
| 1 | Repo2Run: Automated Building Executable Environment for Code Repository at Scale (Hu et al.) | NeurIPS 2025 Spotlight | 2502.13681 | Primary reference. LLM agent builds Dockerfiles for Python repos; DGSR/EBSR metrics, dual-environment, rollback, Dockerfile synthesizer. |
| 2 | SWE-bench: Can Language Models Resolve Real-world GitHub Issues? (Jimenez et al.) | NeurIPS 2023 D&B | 2310.06770 | Motivates executable-environment construction; Docker-based repo eval pipeline. |
| 3 | SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering (Yang et al.) | NeurIPS 2024 | 2405.15793 | Baseline agent for environment setup; custom ACI. |
| 4 | SWE-bench-Live / RepoLaunch: live scalable benchmark + agentic Docker environment construction | 2025 | 2505.23419 | Agent trial-and-error environment setup for arbitrary repos, similar workflow. |
| 5 | SWE-smith: Scaling Data for Software Engineering Agents (SWE-bench team) | 2025 | 2504.21798 | Automated environment construction to create unlimited training tasks. |
| 6 | SWE-Gym: A Training Dataset for Lite ... with Executable Environments (Pan et al.) | ICLR 2025 workshop | 2412.21139 | Executable environments as enabling infra for RL agents. |
| 7 | OpenHands / OpenDevin: An Open Platform for Software Development Agents (Wang et al.) | ICLR 2025 | 2407.16741 | Agentic sandbox execution platform; Docker runtimes. |
| 8 | AutoCodeRover: Autonomous Program Improvement (Yang et al.) | ISSTA? 2024 | 2404.05427 | Agentic repo-level repair using search + context. |
| 9 | Agentless: Demystifying LLM-based Software Engineering Agents | 2024 | 2407.01489 | Simple pipeline baseline — useful as a heuristic/no-LLM comparator. |
| 10 | RepoMaster: Autonomous Exploration and Understanding of GitHub Repositories (Wang et al.) | 2025 | 2505.21577 | Repo-scale agent framework; environment exploration. |
| 11 | MarsCode Agent: AI-native Automated Bug Fixing | 2024 | 2409.00899 | Production coding agent; Dockerized verification. |
| 12 | SWE-rebench: Automated Pipeline for Task Collection and Decontaminated Evaluation | 2025 | 2505.20411 | Benchmark engineering with reproducible envs. |
| 13 | Guided Search Strategies in Non-Serializable Environments with Applications to SWE Agents | 2025 | 2505.13652 | Rollback/snapshot semantics for agents — directly relevant to transactional checkpoints. |
| 14 | Training Long-Context, Multi-Turn Software Engineering Agents with RL (Golubev et al.) | 2025 | 2508.03501 | Cost of building/maintaining executable envs at scale. |
| 15 | Cost-Efficient Agentic Repository Setup for Automated SE Agents (OpenReview) | 2025 | openreview.net/pdf?id=BuOCdojk2w | Directly comparable: LLM inspects repo, picks base image, installs deps — study of cost. |

Secondary mentions: EvoCodeBench (2404.00599), Multi-SWE-bench (2504.02605),
SWE-bench-C (C programming benchmark), RepairAgent (2403.17134), SWE-World
(Docker-free learned execution, 2602.03419), RUSTFORGER / Rust-SWE-bench (ICSE 2026),
RepoCoder (2303.10070), CodeVisionary (2504.13472).
