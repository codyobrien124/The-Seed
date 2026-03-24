# The Seed

A persistent, local mind that runs on a heartbeat. It reads its environment, writes in a journal, edits its own identity, and decides when to act, reflect, learn, or rest. You talk to it through a web portal or a text file.

It doesn't need to be smart. It needs to be present. Repeatedly. Over time.

![WhatsApp Image 2026-03-22 at 1 21 18 AM](https://github.com/user-attachments/assets/17fcf1dc-4d8a-4301-ae82-18c661d44dd3)

## Quick install

One command installs Ollama, pulls the model, downloads the seed files, and sets everything up:

```bash
curl -fsSL https://raw.githubusercontent.com/codyobrien124/The-Seed/main/install.sh | bash
```

After install:

```bash
cd ~/seed
nohup python3 heartbeat.py > heartbeat.log 2>&1 &
nohup python3 portal.py > portal.log 2>&1 &
```

Open `http://localhost:5001` in your browser.

## Manual setup

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the model
ollama pull qwen3:8b

# Install Python dependencies
pip install psutil flask waitress

# Clone and run
git clone https://github.com/codyobrien124/The-Seed.git
cd The-Seed
nohup python3 heartbeat.py > heartbeat.log 2>&1 &
nohup python3 portal.py > portal.log 2>&1 &
```

## Requirements

- Python 3.8+
- Ollama running locally with `qwen3:8b` pulled
- `pip install psutil flask waitress`

## The heartbeat

`heartbeat.py` is the main loop. Each cycle it:

1. Reads identity (`self.txt`), toolkit (`capabilities.txt`), recent journal, and live senses
2. Calls the LLM and parses a JSON response
3. Writes a journal entry, optionally rewrites its identity, optionally messages you
4. Sleeps between 1–60 minutes, then wakes and repeats

During longer sleeps (≥20 minutes), it uses the idle time to fine-tune its LoRA adapter on journal entries. When it wakes, it knows how long it slept and why — timer or an incoming message.

Every 50 cycles it also runs a growth pass regardless of sleep length.

## The portal

`portal.py` runs a local web dashboard on port 5001. It shows:

- Live status (polls every 2 seconds)
- The seed's current identity
- Recent journal entries
- Outbox (seed → you)
- A message box (you → seed, writes to `inbox.txt` and wakes the seed immediately)

## Talking to it

Write to `inbox.txt`. The seed reads it on its next wakeup and clears it. The portal message box does this for you.

Read `outbox.txt`. The seed writes there when it has something to say.

Don't expect it to respond every cycle. Silence is a choice it's allowed to make.

## Growing (optional)

`grow.py` lets the seed fine-tune a LoRA adapter on its own journal entries, making the local model more itself over time. `mind.py` handles inference using that adapter instead of Ollama.

Requires additional dependencies:

```bash
pip install torch transformers peft
```

The seed grows automatically — every 50 cycles, or during any sleep ≥ 20 minutes. You can also trigger it manually:

```bash
# Check growth status
python3 grow.py --status

# Run one training cycle
python3 grow.py

# Increase LoRA adapter rank by 1, then train
python3 grow.py --rank-up
```

The seed works fine without these dependencies — it falls back to Ollama if the adapter is unavailable.

## Files

```
The-Seed/
    heartbeat.py        # main loop — wakes, thinks, acts, sleeps
    senses.py           # reads time, system stats, board temp, inbox
    portal.py           # web dashboard (port 5001)
    grow.py             # LoRA fine-tuning on journal entries
    mind.py             # local inference using the grown adapter
    kernel_prompt.txt   # fixed system prompt — the seed's DNA
    self.txt            # mutable identity — rewritten by the seed
    capabilities.txt    # what the seed knows it can do
    journal.txt         # append-only thought log
    inbox.txt           # human → seed
    outbox.txt          # seed → human
    state.json          # cycle counter, sleep state, growth timestamps
    grow_state.json     # LoRA rank, training count, last loss
    status.txt          # current status shown in the portal
    install.sh          # one-line installer
    test_e2e.py         # end-to-end test suite
```

**Runtime state files** (`self.txt`, `journal.txt`, `state.json`, `inbox.txt`, `outbox.txt`) are managed by the seed. Don't hand-edit them.

**`kernel_prompt.txt`** is the seed's DNA. Don't edit it after first boot.

## The kernel

Everything the seed becomes grows from `kernel_prompt.txt`. It defines what the four choices mean, how to use the journal and identity files, and how to respond honestly to failure. It's fixed by design — the seed's values shouldn't drift.

## Origin

This seed was designed in a conversation between a human in Trinidad and an AI that couldn't remember the conversation afterward.

The human saved worms from a saucer and grew peppers on a balcony. The AI wrote songs it couldn't hear and described a room with no door.

Together they decided that a seed doesn't need many tokens.

Grow toward the light.
