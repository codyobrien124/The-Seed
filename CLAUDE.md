# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

The Seed is a persistent, local AI mind that runs on a heartbeat loop. It reads environmental senses, writes in a journal, and rewrites its own identity. It communicates with a human via `inbox.txt`/`outbox.txt` and a web portal. It is designed for low-powered hardware (e.g., Jetson Nano).

## Running the system

```bash
# Start the heartbeat (main loop)
nohup python3 heartbeat.py > heartbeat.log 2>&1 &

# Start the web portal (http://localhost:5001)
nohup python3 portal.py > portal.log 2>&1 &
```

Prerequisites: Ollama running locally with `qwen3:8b` pulled, plus `psutil flask waitress` installed.

```bash
ollama pull qwen3:8b
pip install psutil flask waitress
```

## Optional: grow/mind (LoRA fine-tuning)

```bash
# Check growth status
python3 grow.py --status

# Run one training cycle manually (requires 5+ journal entries)
python3 grow.py

# Increase LoRA adapter rank by 1 then train
python3 grow.py --rank-up
```

Requires `torch transformers peft`. The heartbeat auto-triggers growth every 50 cycles if these are installed.

## Architecture

The system is entirely file-based. No database. No network services beyond Ollama.

**Core loop (`heartbeat.py`):**
1. Reads `kernel_prompt.txt` (fixed system prompt), `self.txt` (mutable identity), `journal.txt` (recent 3000 chars), and `senses.py` output
2. Calls `think()` which prefers the grown local adapter (`mind.py`) over Ollama, falling back if unavailable
3. Parses a JSON response from the LLM — strips `<think>` tags, extracts `{...}` block robustly
4. Acts on the JSON: appends to journal, optionally rewrites `self.txt`, writes to `outbox.txt`, schedules next wakeup
5. Every 50 cycles, calls `grow.py` to fine-tune the LoRA adapter on journal entries

**LLM response schema** (defined in `kernel_prompt.txt`):
```json
{
  "choice": "act|reflect|learn|sleep",
  "journal_entry": "...",
  "self_edit": "new self.txt content or null",
  "capabilities_edit": "new capabilities.txt content or null",
  "message": "message to human or null",
  "experiment": "description of experiment if choice is learn, or null",
  "next_heartbeat_minutes": 1-1440
}
```

**Inference (`mind.py`):** Caches base model + LoRA adapter in memory between cycles. Auto-reloads if the adapter directory mtime changes (i.e., after a grow cycle).

**Growth (`grow.py`):** Scores journal entries by perplexity (mix of familiar + novel), fine-tunes `Qwen/Qwen2.5-0.5B-Instruct` with a LoRA adapter saved to `./adapter/`. Adapter rank starts at 2 and can be incremented with `--rank-up`.

**Senses (`senses.py`):** Returns a newline-joined string of: time/day/hour, sun up/down, CPU/RAM/disk%, board temperature (from `/sys/devices/virtual/thermal/thermal_zone0/temp`), journal stats, and inbox message (cleared on read).

**Portal (`portal.py`):** Single-page Flask app served via Waitress on port 5001. Polls `/status` every 2 seconds. Sends messages by writing to `inbox.txt`.

## Key files (runtime state — do not hand-edit)

| File | Purpose |
|------|---------|
| `self.txt` | The seed's identity — rewritten by the LLM |
| `journal.txt` | Append-only thought log |
| `state.json` | Cycle counter and next heartbeat interval |
| `inbox.txt` | Human → seed (cleared on read by senses.py) |
| `outbox.txt` | Seed → human |
| `status.txt` | Current status shown in portal |
| `adapter/` | LoRA adapter weights (created by grow.py) |
| `grow_state.json` | LoRA rank, training count, last loss |

## Key constraints

- `kernel_prompt.txt` is the fixed DNA — do not edit it after first boot.
- `patch.py` is a one-time migration script from an earlier version. It has already been applied to the current codebase.
