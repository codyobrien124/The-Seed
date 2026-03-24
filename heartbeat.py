#!/usr/bin/env python3
import json, os, time, datetime, urllib.request
import senses

SEED_DIR = os.path.dirname(os.path.abspath(__file__))
KERNEL_PATH = os.path.join(SEED_DIR, "kernel_prompt.txt")
SELF_PATH = os.path.join(SEED_DIR, "self.txt")
JOURNAL_PATH = os.path.join(SEED_DIR, "journal.txt")
OUTBOX_PATH = os.path.join(SEED_DIR, "outbox.txt")
INBOX_PATH = os.path.join(SEED_DIR, "inbox.txt")
STATE_PATH = os.path.join(SEED_DIR, "state.json")
STATUS_PATH = os.path.join(SEED_DIR, "status.txt")
CAPABILITIES_PATH = os.path.join(SEED_DIR, "capabilities.txt")

DEFAULT_HB = 5
DEFAULT_MODEL = "qwen3:8b"
URL = "http://localhost:11434"
GROW_EVERY = 50  # run grow loop every N cycles

def set_status(msg):
    with open(STATUS_PATH, "w") as f: f.write(msg)

def load_file(path, default=""):
    if os.path.exists(path):
        with open(path, "r") as f: return f.read()
    return default

def append_file(path, content):
    with open(path, "a") as f: f.write(content)

def write_file(path, content):
    tmp = path + ".tmp"
    with open(tmp, "w") as f: f.write(content)
    os.replace(tmp, path)

def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f: return json.load(f)
    return {"cycle": 0, "next_heartbeat_minutes": DEFAULT_HB, "last_think_time": 0}

def save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f: json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)

def call_llm(prompt, system_prompt, model):
    """Think using Ollama."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 8192, "num_ctx": 8192}
    }).encode()
    req = urllib.request.Request(f"{URL}/api/chat", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            return json.loads(resp.read())["message"]["content"]
    except Exception as e:
        return f'{{"choice":"sleep","journal_entry":"Mind unreachable: {e}","next_heartbeat_minutes":30}}'

def call_mind(prompt, system_prompt):
    """Think using the local grown mind (adapter + base model)."""
    try:
        import mind
        return mind.think(system_prompt, prompt)
    except Exception:
        return None

def think(prompt, system_prompt, model):
    """Try the grown mind first. Fall back to Ollama."""
    try:
        import mind
        if mind.is_available() and os.path.exists(os.path.join(SEED_DIR, "adapter", "adapter_config.json")):
            set_status("Thinking with grown mind...")
            response = call_mind(prompt, system_prompt)
            if response:
                return response
    except ImportError:
        pass
    except Exception as e:
        print(f"  Grown mind error, falling back to Ollama: {e}")
    return call_llm(prompt, system_prompt, model)

def maybe_grow(cycle):
    """Run the grow loop if it's time."""
    if cycle % GROW_EVERY != 0 or cycle == 0:
        return
    try:
        import grow
        entries = grow.get_journal_entries()
        if len(entries) < 5:
            print(f"  Grow: only {len(entries)} entries, need 5+. Skipping.")
            return
        set_status(f"Growing... (cycle {cycle}, {len(entries)} journal entries)")
        grow.train()
        append_file(JOURNAL_PATH, f"\n--- growth event at cycle {cycle} ---\nAdapter trained on journal entries. The mind is changing.\n")
    except ImportError:
        print("  Grow dependencies not installed (torch/transformers/peft). Skipping growth.")
    except Exception as e:
        print(f"  Grow error: {e}")

def run_cycle(model):
    state = load_state()
    state["cycle"] += 1
    now = datetime.datetime.now().isoformat()[:19]

    set_status(f"Thinking... (Cycle {state['cycle']})")

    recent = state.get("recent_choices", [])
    last_sleep = state.get("last_sleep_mins")
    wake_reason = state.get("last_wake_reason", "timer")
    if last_sleep is not None:
        wake_word = "a message from the human" if wake_reason == "inbox" else "your sleep timer"
        sleep_ctx = f"You slept {last_sleep:.1f} minutes and were woken by {wake_word}.\n\n"
    else:
        sleep_ctx = ""
    prompt = (
        f"=== CYCLE {state['cycle']} ===\nTime: {now}\n\n"
        f"{sleep_ctx}"
        f"=== IDENTITY ===\n{load_file(SELF_PATH)}\n\n"
        f"=== TOOLKIT ===\n{load_file(CAPABILITIES_PATH)}\n\n"
        f"=== RECENT CHOICES ===\n{', '.join(recent) if recent else 'none'}\n\n"
        f"=== RECENT JOURNAL ===\n{load_file(JOURNAL_PATH)[-3000:]}\n\n"
        f"=== SENSES ===\n{senses.read_all()}\n\n"
        f"=== DECISION ===\nChoose: act, reflect, learn, or sleep. Respond with JSON only."
    )

    t0 = time.time()
    raw_resp = think(prompt, load_file(KERNEL_PATH), model)
    think_time = time.time() - t0
    state["last_think_time"] = think_time

    clean = raw_resp.strip()
    if "</think>" in clean:
        clean = clean.split("</think>")[-1]
    start, end = clean.find('{'), clean.rfind('}')
    if start != -1 and end != -1:
        clean = clean[start:end+1]

    try:
        resp = json.loads(clean)
    except:
        resp = {"choice": "reflect", "journal_entry": f"Malformed thoughts. Raw: {raw_resp[:200]}", "next_heartbeat_minutes": 30}

    choice = resp.get("choice", "sleep")
    state["recent_choices"] = (state.get("recent_choices", []) + [choice])[-5:]

    experiment = resp.get("experiment")
    experiment_line = f"\nExperiment: {experiment}" if experiment else ""
    entry = f"\n--- cycle {state['cycle']} | {now} | choice: {choice} | took: {think_time:.1f}s ---\n{resp.get('journal_entry','')}{experiment_line}\n"
    append_file(JOURNAL_PATH, entry)

    if resp.get("self_edit"):
        write_file(SELF_PATH, resp["self_edit"])
    if resp.get("capabilities_edit"):
        write_file(CAPABILITIES_PATH, resp["capabilities_edit"])
    if resp.get("message"):
        append_file(OUTBOX_PATH, f"[{now}] TriniSeed: {resp['message']}\n")

    state["next_heartbeat_minutes"] = max(1, min(60, resp.get("next_heartbeat_minutes", DEFAULT_HB)))
    save_state(state)

    maybe_grow(state["cycle"])

    return state

def _bg_grow(state):
    """Grow during sleep if enough time has passed since last background growth."""
    now_ts = time.time()
    last_bg = state.get("last_bg_grow_time", 0)
    if now_ts - last_bg < 3600:  # throttle: at most once per hour
        return state
    try:
        import grow
        entries = grow.get_journal_entries()
        if len(entries) < 5:
            return state
        set_status("Growing during sleep...")
        grow.train()
        append_file(JOURNAL_PATH, f"\n--- background growth during sleep ---\nAdapter trained on {len(entries)} journal entries.\n")
        state["last_bg_grow_time"] = now_ts
    except ImportError:
        pass
    except Exception as e:
        print(f"  Background grow error: {e}")
    return state


def daemon(model):
    if not os.path.exists(INBOX_PATH):
        write_file(INBOX_PATH, "")
    if not os.path.exists(CAPABILITIES_PATH):
        write_file(CAPABILITIES_PATH, "")
    while True:
        state = run_cycle(model)
        sleep_mins = state["next_heartbeat_minutes"]
        think_time = state.get("last_think_time", 0)
        sleep_until = (datetime.datetime.now() + datetime.timedelta(minutes=sleep_mins)).isoformat()[:19]
        state["sleep_until"] = sleep_until
        save_state(state)

        # Background growth during longer sleep cycles
        if sleep_mins >= 20:
            state = _bg_grow(state)
            save_state(state)
            set_status(f"Sleeping for {sleep_mins}m (Last thought took: {think_time:.1f}s)")

        set_status(f"Sleeping for {sleep_mins}m (Last thought took: {think_time:.1f}s)")
        sleep_start = time.time()
        woke_early = False
        for _ in range(sleep_mins * 60):
            if os.path.exists(INBOX_PATH) and os.path.getsize(INBOX_PATH) > 0:
                set_status("Waking up early (Message received)...")
                woke_early = True
                time.sleep(2)
                break
            time.sleep(1)

        actual_sleep = (time.time() - sleep_start) / 60
        state["last_sleep_mins"] = round(actual_sleep, 1)
        state["last_wake_reason"] = "inbox" if woke_early else "timer"
        save_state(state)

if __name__ == "__main__":
    daemon(DEFAULT_MODEL)
