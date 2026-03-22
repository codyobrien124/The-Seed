"""
Mind — local inference using the frozen base + grown adapter.

This replaces ollama when the seed is ready to think with its own brain.
Falls back to ollama if transformers/peft aren't installed or adapter doesn't exist.

Usage in heartbeat.py:
    from mind import think
    response = think(system_prompt, user_prompt)
"""

import json
import os

SEED_DIR = os.path.dirname(os.path.abspath(__file__))
ADAPTER_DIR = os.path.join(SEED_DIR, "adapter")
GROW_STATE_PATH = os.path.join(SEED_DIR, "grow_state.json")

# Cache the model in memory between cycles when running as daemon
_model = None
_tokenizer = None
_model_loaded_at = None


def _load_model():
    """Load base model + adapter. Cached in memory."""
    global _model, _tokenizer, _model_loaded_at
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    # Get base model name from grow state
    if os.path.exists(GROW_STATE_PATH):
        with open(GROW_STATE_PATH) as f:
            state = json.load(f)
        base_model_name = state.get("base_model", "Qwen/Qwen2.5-0.5B-Instruct")
    else:
        base_model_name = "Qwen/Qwen2.5-0.5B-Instruct"

    print(f"  Loading base model: {base_model_name}")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype="auto",
        device_map="auto"
    )

    # Load adapter if it exists
    if os.path.exists(ADAPTER_DIR) and os.path.exists(
        os.path.join(ADAPTER_DIR, "adapter_config.json")
    ):
        print(f"  Loading grown adapter from {ADAPTER_DIR}")
        model = PeftModel.from_pretrained(model, ADAPTER_DIR)
    else:
        print(f"  No adapter yet — using base model only")

    model.eval()
    _model = model
    _tokenizer = tokenizer
    _model_loaded_at = os.path.getmtime(ADAPTER_DIR) if os.path.exists(ADAPTER_DIR) else 0


def _check_reload():
    """Reload if adapter has been updated since last load."""
    global _model_loaded_at
    if _model is None:
        return True
    if os.path.exists(ADAPTER_DIR):
        current_mtime = os.path.getmtime(ADAPTER_DIR)
        if current_mtime > _model_loaded_at:
            return True
    return False


def think(system_prompt, user_prompt, max_new_tokens=1024, temperature=0.7):
    """
    Generate a response using the local model.
    Returns the raw text response.
    """
    import torch

    if _check_reload():
        _load_model()

    # Build chat messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # Use chat template if available
    if hasattr(_tokenizer, "apply_chat_template"):
        text = _tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        text = f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>\n"

    inputs = _tokenizer(text, return_tensors="pt")
    inputs = {k: v.to(_model.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = _model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            pad_token_id=_tokenizer.pad_token_id
        )

    # Decode only the new tokens
    new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
    response = _tokenizer.decode(new_tokens, skip_special_tokens=True)

    return response.strip()


def is_available():
    """Check if local inference is possible."""
    try:
        import torch
        from transformers import AutoModelForCausalLM
        from peft import PeftModel
        return True
    except ImportError:
        return False
