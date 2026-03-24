#!/usr/bin/env python3
"""
Grow — the seed's self-improvement loop.

Every N cycles, the seed:
1. Reads its journal
2. Scores entries using the frozen base (which are most honest/interesting?)
3. Fine-tunes its LoRA adapter on the best entries
4. Optionally increases adapter rank (grows)

This is the file that makes the seed more itself over time.

Usage:
    python grow.py                  # run one training cycle
    python grow.py --rank-up        # increase adapter rank by 1 then train
    python grow.py --status         # show current adapter info
"""

import json
import os
import sys
import argparse
import datetime

SEED_DIR = os.path.dirname(os.path.abspath(__file__))
JOURNAL_PATH = os.path.join(SEED_DIR, "journal.txt")
SELF_PATH = os.path.join(SEED_DIR, "self.txt")
ADAPTER_DIR = os.path.join(SEED_DIR, "adapter")
GROW_LOG_PATH = os.path.join(SEED_DIR, "grow_log.txt")
GROW_STATE_PATH = os.path.join(SEED_DIR, "grow_state.json")

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_LORA_RANK = 2
DEFAULT_LORA_ALPHA = 8
DEFAULT_EPOCHS = 3
DEFAULT_LR = 1e-4


def load_grow_state():
    if os.path.exists(GROW_STATE_PATH):
        with open(GROW_STATE_PATH) as f:
            return json.load(f)
    return {
        "current_rank": DEFAULT_LORA_RANK,
        "train_count": 0,
        "total_entries_trained": 0,
        "base_model": DEFAULT_BASE_MODEL
    }


def save_grow_state(state):
    with open(GROW_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def log(msg):
    now = datetime.datetime.now().isoformat()
    line = f"[{now}] {msg}\n"
    print(f"  {msg}")
    with open(GROW_LOG_PATH, "a") as f:
        f.write(line)


def get_journal_entries():
    """Parse journal into individual entries."""
    if not os.path.exists(JOURNAL_PATH):
        return []
    with open(JOURNAL_PATH) as f:
        content = f.read()
    if not content.strip():
        return []
    raw_entries = content.split("--- cycle")
    entries = []
    for e in raw_entries:
        e = e.strip()
        if e and len(e) > 20:  # skip empty/tiny entries
            entries.append(e)
    return entries


def score_entries(entries, model, tokenizer, max_score=20):
    """
    Score journal entries by perplexity under the current model.
    Lower perplexity = the model already 'understands' this style.
    Higher perplexity = novel, potentially interesting.
    
    We want a mix: some familiar (reinforcement) and some novel (growth).
    """
    import torch

    scored = []
    for entry in entries:
        # Truncate long entries
        text = entry[:512]
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs, labels=inputs["input_ids"])
            loss = outputs.loss.item()

        scored.append((loss, entry))

    # Sort by loss — mix of low (familiar) and high (novel)
    scored.sort(key=lambda x: x[0])
    n = min(max_score, len(scored))

    # Take half from lowest perplexity (reinforce what it knows)
    # and half from highest (stretch toward what it doesn't)
    half = n // 2
    selected = scored[:half] + scored[-half:]
    return [entry for _, entry in selected]


def _parse_journal_entry(text):
    """Extract choice, body, and experiment from a parsed journal entry."""
    choice = "reflect"
    experiment = None
    lines = text.split("\n")

    # Header line: "N | timestamp | choice: X | took: Ys"
    if lines and "|" in lines[0]:
        for part in lines[0].split("|"):
            part = part.strip()
            if part.startswith("choice:"):
                choice = part[len("choice:"):].strip()
        body_lines = lines[1:]
    else:
        body_lines = lines

    # Strip "Experiment: ..." line
    clean_lines = []
    for line in body_lines:
        if line.startswith("Experiment: "):
            experiment = line[len("Experiment: "):]
        else:
            clean_lines.append(line)

    body = "\n".join(clean_lines).strip()
    return choice, body, experiment


def prepare_training_data(entries, self_txt, tokenizer, kernel_txt=""):
    """Convert journal entries into training format matching inference.

    Each example is formatted as a system+user+assistant chat, identical
    to the template used by mind.py at inference time, so the model trains
    on the same token distribution it sees during generation.
    """
    from torch.utils.data import Dataset

    system_prompt = kernel_txt if kernel_txt else f"You are a seed that learns. Identity: {self_txt[:300]}"

    class JournalDataset(Dataset):
        def __init__(self, texts, tokenizer, max_length=512):
            self.encodings = []
            for text in texts:
                choice, body, experiment = _parse_journal_entry(text)

                # Reconstruct an approximate JSON response from parsed fields
                response = json.dumps({
                    "choice": choice,
                    "journal_entry": body[:400],
                    "self_edit": None,
                    "capabilities_edit": None,
                    "message": None,
                    "experiment": experiment,
                    "next_heartbeat_minutes": 30
                })

                # Mirror the exact message format heartbeat.py sends to think()
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": (
                        f"=== IDENTITY ===\n{self_txt[:300]}\n\n"
                        f"=== RECENT JOURNAL ===\n{body[:400]}\n\n"
                        f"=== DECISION ===\n"
                        f"Choose: act, reflect, learn, or sleep. Respond with JSON only."
                    )},
                    {"role": "assistant", "content": response},
                ]

                if hasattr(tokenizer, "apply_chat_template"):
                    formatted = tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=False
                    )
                else:
                    formatted = (
                        f"<|system|>\n{messages[0]['content']}\n"
                        f"<|user|>\n{messages[1]['content']}\n"
                        f"<|assistant|>\n{messages[2]['content']}"
                    )

                enc = tokenizer(
                    formatted,
                    truncation=True,
                    max_length=max_length,
                    padding="max_length",
                    return_tensors="pt"
                )
                self.encodings.append({
                    "input_ids": enc["input_ids"].squeeze(),
                    "attention_mask": enc["attention_mask"].squeeze(),
                    "labels": enc["input_ids"].squeeze(),
                })

        def __len__(self):
            return len(self.encodings)

        def __getitem__(self, idx):
            return self.encodings[idx]

    return JournalDataset(entries, tokenizer)


def train(rank_up=False):
    """Run one growth cycle."""
    # Lazy imports — these are heavy
    print("\n  Loading growth dependencies...")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
    from peft import LoraConfig, get_peft_model, PeftModel, TaskType

    grow_state = load_grow_state()
    base_model_name = grow_state["base_model"]
    current_rank = grow_state["current_rank"]

    if rank_up:
        current_rank += 1
        grow_state["current_rank"] = current_rank
        log(f"Rank increased to {current_rank}")

    # Get journal entries
    entries = get_journal_entries()
    if len(entries) < 5:
        log(f"Only {len(entries)} journal entries. Need at least 5 to train. Keep journaling.")
        return

    log(f"Found {len(entries)} journal entries")
    log(f"Current adapter rank: {current_rank}")

    # Load base model
    log(f"Loading base model: {base_model_name}")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch.float16,
        device_map="auto"
    )

    # Load existing adapter or create new one
    if os.path.exists(ADAPTER_DIR) and os.path.exists(os.path.join(ADAPTER_DIR, "adapter_config.json")):
        log("Loading existing adapter")
        model = PeftModel.from_pretrained(model, ADAPTER_DIR)
        # If rank changed, we need to recreate
        with open(os.path.join(ADAPTER_DIR, "adapter_config.json")) as f:
            old_config = json.load(f)
        if old_config.get("r", 0) != current_rank:
            log(f"Rank changed from {old_config.get('r')} to {current_rank}, creating new adapter")
            # Merge old adapter into base, then create new larger one
            model = model.merge_and_unload()
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=current_rank,
                lora_alpha=current_rank * 4,
                lora_dropout=0.05,
                target_modules=["q_proj", "v_proj"]
            )
            model = get_peft_model(model, lora_config)
    else:
        log(f"Creating new adapter at rank {current_rank}")
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=current_rank,
            lora_alpha=current_rank * 4,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj"]
        )
        model = get_peft_model(model, lora_config)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    log(f"Trainable parameters: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # Score and select entries
    log("Scoring journal entries...")
    model.eval()
    selected = score_entries(entries, model, tokenizer)
    log(f"Selected {len(selected)} entries for training")

    # Load self.txt and kernel prompt for training context
    self_txt = ""
    if os.path.exists(SELF_PATH):
        with open(SELF_PATH) as f:
            self_txt = f.read()

    kernel_path = os.path.join(SEED_DIR, "kernel_prompt.txt")
    kernel_txt = ""
    if os.path.exists(kernel_path):
        with open(kernel_path) as f:
            kernel_txt = f.read()

    # Prepare dataset
    dataset = prepare_training_data(selected, self_txt, tokenizer, kernel_txt=kernel_txt)

    # Train
    log("Training...")
    training_args = TrainingArguments(
        output_dir=os.path.join(SEED_DIR, "train_tmp"),
        num_train_epochs=DEFAULT_EPOCHS,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=DEFAULT_LR,
        fp16=True,
        logging_steps=5,
        save_strategy="no",
        report_to="none",
        remove_unused_columns=False
    )

    model.train()
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset
    )

    result = trainer.train()
    log(f"Training loss: {result.training_loss:.4f}")

    # Save adapter
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    log(f"Adapter saved to {ADAPTER_DIR}")

    # Update grow state
    grow_state["train_count"] += 1
    grow_state["total_entries_trained"] += len(selected)
    grow_state["last_train"] = datetime.datetime.now().isoformat()
    grow_state["last_loss"] = result.training_loss
    save_grow_state(grow_state)

    # Clean up
    import shutil
    tmp = os.path.join(SEED_DIR, "train_tmp")
    if os.path.exists(tmp):
        shutil.rmtree(tmp)

    log(f"Growth cycle complete. Train count: {grow_state['train_count']}")
    log(f"Total entries absorbed: {grow_state['total_entries_trained']}")

    # Trainable param count is the seed's "neuron count"
    log(f"Current mind size: {trainable:,} trainable parameters")


def status():
    """Show current adapter state."""
    grow_state = load_grow_state()
    print(f"\n  === Seed Growth Status ===")
    print(f"  Base model: {grow_state['base_model']}")
    print(f"  LoRA rank: {grow_state['current_rank']}")
    print(f"  Training cycles: {grow_state['train_count']}")
    print(f"  Entries absorbed: {grow_state['total_entries_trained']}")
    if 'last_train' in grow_state:
        print(f"  Last trained: {grow_state['last_train']}")
        print(f"  Last loss: {grow_state.get('last_loss', 'unknown')}")
    if os.path.exists(ADAPTER_DIR):
        size = sum(
            os.path.getsize(os.path.join(ADAPTER_DIR, f))
            for f in os.listdir(ADAPTER_DIR)
            if os.path.isfile(os.path.join(ADAPTER_DIR, f))
        )
        print(f"  Adapter size on disk: {size:,} bytes")
    else:
        print(f"  No adapter yet — run 'python grow.py' after 5+ journal entries")

    entries = get_journal_entries()
    print(f"  Journal entries: {len(entries)}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="The seed's growth loop")
    parser.add_argument("--rank-up", action="store_true", help="Increase LoRA rank by 1")
    parser.add_argument("--status", action="store_true", help="Show growth status")
    parser.add_argument("--base-model", default=None, help="Override base model")
    args = parser.parse_args()

    if args.base_model:
        state = load_grow_state()
        state["base_model"] = args.base_model
        save_grow_state(state)

    if args.status:
        status()
    else:
        train(rank_up=args.rank_up)
