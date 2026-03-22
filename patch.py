import re
with open("heartbeat.py", "r") as f:
    code = f.read()

# 1. Remove format strictness if it's still there
code = re.sub(r'\s*"format":\s*"json",', '', code)

# 2. Give it 8000 tokens of room to think
code = re.sub(r'"num_predict":\s*\d+', '"num_predict": 8192', code)

# 3. Bulletproof the JSON parser to just grab what is between { and }
parse_pattern = r'clean = response_text\.strip\(\).*?response = json\.loads\(clean\)'
new_parse = """clean = response_text.strip()
        if "</think>" in clean:
            clean = clean.split("</think>")[-1]
        start = clean.find('{')
        end = clean.rfind('}')
        if start != -1 and end != -1:
            clean = clean[start:end+1]
        response = json.loads(clean)"""
code = re.sub(parse_pattern, new_parse, code, flags=re.DOTALL)

with open("heartbeat.py", "w") as f:
    f.write(code)
print("Brain patched successfully.")
