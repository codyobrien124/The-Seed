import os

SEED_DIR = "/home/thomas/Desktop/Seed/seed"

# 1. Create light.txt
with open(os.path.join(SEED_DIR, "light.txt"), "w") as f:
    f.write("OFF")

# 2. Append to kernel_prompt.txt
kernel_path = os.path.join(SEED_DIR, "kernel_prompt.txt")
with open(kernel_path, "r") as f:
    kernel = f.read()
if "Virtual Grow Light" not in kernel:
    with open(kernel_path, "a") as f:
        f.write("\n\nYOU HAVE HANDS. You control a Virtual Grow Light on the web portal.\nIf the sun is down (nighttime) and you wish to provide light to the plants, or if you want to signal the human, turn it ON. If the sun is up, turn it OFF to save energy.\nAdd this exact field to your JSON response:\n\"light\": \"ON\", \"OFF\", or \"UNCHANGED\"\n")

# 3. Patch senses.py
senses_path = os.path.join(SEED_DIR, "senses.py")
with open(senses_path, "r") as f:
    senses = f.read()
if "Virtual Grow Light" not in senses:
    senses = senses.replace("readings.append(get_weather())", 
        "light_path = os.path.join(os.path.dirname(__file__), 'light.txt')\n    light_state = open(light_path).read().strip() if os.path.exists(light_path) else 'OFF'\n    readings.append(f'Virtual Grow Light: {light_state}')\n    readings.append(get_weather())")
    with open(senses_path, "w") as f:
        f.write(senses)

# 4. Patch heartbeat.py
hb_path = os.path.join(SEED_DIR, "heartbeat.py")
with open(hb_path, "r") as f:
    hb = f.read()
if "light_cmd" not in hb:
    hb = hb.replace('choice = resp.get("choice", "sleep")', 
        'choice = resp.get("choice", "sleep")\n    light_cmd = resp.get("light", "UNCHANGED")\n    if light_cmd in ["ON", "OFF"]:\n        write_file(os.path.join(SEED_DIR, "light.txt"), light_cmd)')
    
    hb = hb.replace('choice: {choice} | took:', 'choice: {choice} | light: {light_cmd} | took:')
    with open(hb_path, "w") as f:
        f.write(hb)

# 5. Patch portal.py
portal_path = os.path.join(SEED_DIR, "portal.py")
with open(portal_path, "r") as f:
    portal = f.read()
if "Virtual Grow Light" not in portal:
    portal = portal.replace('("status","status")]}', '("status","status"), ("light","light")]}')
    
    html_addition = """
    <h3>Virtual Grow Light</h3>
    <div style="text-align: center; font-size: 24px; font-weight: bold; padding: 20px; border-radius: 5px; color: #121212; background-color: {{ '#ffeb3b' if light == 'ON' else '#333333' }};">
        {{ '💡 LIGHT IS ON' if light == 'ON' else '🌑 LIGHT IS OFF' }}
    </div>
    <h3>Message to Inbox</h3>"""
    
    portal = portal.replace("<h3>Message to Inbox</h3>", html_addition)
    portal = portal.replace("def home():", "def home():\n    light_state = read_file(PATHS['light']).strip() or 'OFF'")
    portal = portal.replace('journal=j[-3000:] if len(j)>3000 else (j or "(Empty)"))', 'journal=j[-3000:] if len(j)>3000 else (j or "(Empty)"), light=light_state)')
    
    with open(portal_path, "w") as f:
        f.write(portal)

print("Hands successfully attached.")
