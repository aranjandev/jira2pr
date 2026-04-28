# PalletID Multi-Class SL — Claude Code Project Instructions

## Project Overview

This is a **PyTorch pallet classification** training pipeline. It learns discriminative pallet embeddings using ArcFace or PartialFC heads on ResNet-50 / DINOv2 backbones. The system is designed for large-scale (100K+ class) similarity search.

**Everything runs inside Docker.** Never install Python packages on the host.

## Repository Layout

- `train_fullfc.py` / `train_pfc.py` — training entry points (run via `torchrun` for multi-GPU DDP).
- `launch-fullfc-train.sh` / `launch-pfc-train.sh` — convenience wrappers that call `torchrun` with the right args.
- `src/` — installable Python package containing all library code.
  - `configs.py` — YACS `CfgNode` defaults (the single source of truth for hyperparameters).
  - `modelling_backbones.py` — `FeatureExtractorBase` → `ResNet_FeatureExtractor`, `Dinov2_FeatureExtractor`.
  - `modelling_heads.py` — `ArcFaceHead` (nn.Module).
  - `pallet_class_model.py` — `PalletClassModel` (backbone + neck + head).
  - `pfc/` — PartialFC v2 head + CombinedMarginLoss (for 100K+ classes).
  - `modeler.py` — `assemble_model()` factory function.
  - `dataloaders.py` — Dataloader builders + `RemappedSubset`.
  - `eval_metrics.py` — Evaluation: TAR@FAR, angular margin, nearest-centroid.
  - `criteria.py`, `lr_schedulers.py`, `optimisers.py` — training primitives.
  - `soft_ce_loss.py` — `SoftCrossEntropyLoss` for label-smoothed / mixed targets.
  - `checkpoint.py` — Save/load training checkpoints including sharded PartialFC state.
  - `embedders.py` — `PalletModelBackbone_Embedding`, `PalletModelHeadPCA_Embedding` inference helpers.
  - `resource_monitor.py` — `ResourceMonitor` for periodic CPU/GPU stats logging.
  - `dist_handler.py` — DDP setup/cleanup helpers.
  - `embedding_generation/` — Standalone embedding generation CLI.
  - `dataset_creator/` — CLI for building train/test/query/gallery CSV splits.
  - `datasets/` — Custom dataset classes.
- `configs/` — YAML config files.
- `scripts/` — helper scripts.
- `tests/` — pytest test suite.
- `notebooks/` — Experiment notebooks (Jupyter, run inside container).
- `docs/` — Versioned experiment write-ups.

## Agent Framework

This project uses a platform-agnostic multi-agent framework:

- **`.agents/`** — Canonical agent definitions (platform-agnostic). The source of truth.
  - `_registry.yaml` — Structured metadata for all agents (tier, capabilities, subagents).
  - `<slug>.md` — Agent body: role, behavior, constraints, output format.
- **`.github/agents/`** — VS Code Copilot adapters (generated from `.agents/` by `scripts/assemble_agents.py`).
- **`.claude/commands/`** — Claude Code slash commands (generated from `.agents/`).
- **`.github/agent-workflows/`** — Multi-phase workflow definitions (feature, bugfix, resume).
- **`.github/skills/`** — Reusable skill modules referenced by agents.
- **`.github/instructions/`** — Cross-cutting rules (commit conventions, PR schema).

To regenerate platform-specific agent files after editing canonical definitions:
```bash
python scripts/assemble_agents.py
```

## Code Conventions

### Imports
- **Inside `src/`**: use relative imports (`from .utils import log_once`).
- **In entry-point scripts** (`train_*.py`): use absolute package imports (`from src.dataloaders import ...`).
- **In tests**: use absolute package imports; pytest's `pythonpath` setting handles resolution.

### Configuration
- All config defaults are in `src/configs.py` → `get_cfg()` which returns a YACS `CfgNode`.
- Never hardcode hyperparameters in training scripts — put them in the config.

### Model Pattern
- Model = Backbone + Neck + Head, assembled by `src/modeler.py:assemble_model()`.
- PartialFC head is handled separately in `train_pfc.py`.
- Full-FC (standard ArcFace) training uses `train_fullfc.py`.

## How to Verify Changes

```bash
# Run tests (inside container, via Makefile)
make test

# Lint
make lint

# Format
make format

# Full check (lint + test)
make check
```

All `make` targets spin up a Docker container automatically.

## Important Constraints

1. **Docker-only** — all `pip install`, `pytest`, `ruff`, and training commands run inside the container.
2. **Multi-GPU DDP** — training uses `torchrun --nproc_per_node=4`. Be careful with single-process assumptions.
3. **Large class counts** — the dataset can have 200K+ classes. PartialFC samples a fraction.
4. **Notebook isolation** — notebooks use `sys.path.append` and run interactively inside the container. Do not refactor notebook imports.
5. **Data paths** — training data is mounted at `/data/` inside the container.

## Tools & Config

- **Linter/formatter**: ruff (config in `pyproject.toml`)
- **Tests**: pytest (config in `pyproject.toml`)
- **Package**: `pyproject.toml` with `pip install -e .`
- **Build**: `Makefile` → Docker Compose
