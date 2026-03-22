from flask import Flask, request, render_template_string, redirect, url_for
import os, datetime

app = Flask(__name__)
SEED_DIR = os.path.dirname(os.path.abspath(__file__))
PATHS = {k: os.path.join(SEED_DIR, f"{v}.txt") for k, v in[("inbox","inbox"), ("outbox","outbox"), ("journal","journal"), ("self","self"), ("status","status"), ("light","light")]}

def read_file(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>TriniSeed Portal</title>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: monospace; padding: 20px; max-width: 600px; margin: auto; }
        textarea, input { width: 100%; box-sizing: border-box; background: #1e1e1e; color: #e0e0e0; border: 1px solid #333; padding: 10px; margin-top: 10px; }
        button { background: #4caf50; color: #121212; border: none; padding: 10px 20px; margin-top: 10px; cursor: pointer; font-weight: bold; width: 100%; }
        .box { background: #1e1e1e; padding: 15px; border-radius: 5px; margin-bottom: 20px; white-space: pre-wrap; max-height: 300px; overflow-y: auto; border: 1px solid #333;}
        h3 { color: #4caf50; margin-bottom: 5px; }
        #status-bar { background: #2c2c2c; padding: 10px; text-align: center; font-weight: bold; font-size: 1.1em; border-radius: 5px; margin-bottom: 20px; border: 1px solid #4caf50; color: #81c784; }
    </style>
    <script>
        function fetchStatus() {
            fetch('/status').then(r => r.text()).then(t => document.getElementById('status-bar').innerText = t);
        }
        setInterval(fetchStatus, 2000);
    </script>
</head>
<body onload="fetchStatus()">
    <h2>TriniSeed</h2>
    <div id="status-bar">Loading status...</div>
    
    
    <h3>Virtual Grow Light</h3>
    <div style="text-align: center; font-size: 24px; font-weight: bold; padding: 20px; border-radius: 5px; color: #121212; background-color: {{ '#ffeb3b' if light == 'ON' else '#333333' }};">
        {{ '💡 LIGHT IS ON' if light == 'ON' else '🌑 LIGHT IS OFF' }}
    </div>
    <h3>Message to Inbox</h3>
    <form method="POST" action="/send">
        <textarea name="message" rows="3" placeholder="Wake TriniSeed up..."></textarea>
        <button type="submit">Send & Wake</button>
    </form>
    <h3>Conversation Log</h3>
    <div class="box">{{ outbox }}</div>
    <h3>Identity (self.txt)</h3>
    <div class="box">{{ self_txt }}</div>
    <h3>Recent Journal</h3>
    <div class="box">{{ journal }}</div>
</body>
</html>
"""

@app.route('/')
def home():
    light_state = read_file(PATHS['light']).strip() or 'OFF'
    outbox = read_file(PATHS["outbox"]) or "(Empty)"
    self_txt = read_file(PATHS["self"]) or "(Empty)"
    j = read_file(PATHS["journal"])
    return render_template_string(HTML, outbox=outbox, self_txt=self_txt, journal=j[-3000:] if len(j)>3000 else (j or "(Empty)"), light=light_state)

@app.route('/status')
def status():
    return read_file(PATHS["status"]) or "Status unknown"

@app.route('/send', methods=['POST'])
def send_message():
    msg = request.form.get('message', '').strip()
    if msg:
        with open(PATHS["inbox"], 'w') as f: f.write(msg)
        with open(PATHS["outbox"], 'a') as f: f.write(f"[{datetime.datetime.now().isoformat()[:19]}] You: {msg}\n")
    return redirect(url_for('home'))

if __name__ == '__main__': 
    from waitress import serve
    print("Starting production server on http://0.0.0.0:5001")
    serve(app, host='0.0.0.0', port=5001)
