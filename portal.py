from flask import Flask, request, render_template_string, redirect, url_for, Response
import os, datetime, json

app = Flask(__name__)
SEED_DIR = os.path.dirname(os.path.abspath(__file__))
PATHS = {k: os.path.join(SEED_DIR, f"{v}.txt") for k, v in [
    ("inbox", "inbox"), ("outbox", "outbox"), ("journal", "journal"),
    ("self", "self"), ("status", "status"), ("capabilities", "capabilities")
]}
STATE_PATH = os.path.join(SEED_DIR, "state.json")

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
    <title>Stan Portal</title>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: monospace; padding: 20px; max-width: 800px; margin: auto; }
        textarea, input { width: 100%; box-sizing: border-box; background: #1e1e1e; color: #e0e0e0; border: 1px solid #333; padding: 10px; margin-top: 10px; }
        button { background: #4caf50; color: #121212; border: none; padding: 10px 20px; margin-top: 10px; cursor: pointer; font-weight: bold; width: 100%; }
        .box { background: #1e1e1e; padding: 15px; border-radius: 5px; margin-bottom: 20px; white-space: pre-wrap; max-height: 300px; overflow-y: auto; border: 1px solid #333; }
        h3 { color: #4caf50; margin-bottom: 5px; }
        #status-bar { background: #2c2c2c; padding: 10px; text-align: center; font-weight: bold; font-size: 1.1em; border-radius: 5px; margin-bottom: 6px; border: 1px solid #4caf50; color: #81c784; }
        #cycle-bar { background: #1a1a1a; padding: 6px 10px; text-align: center; font-size: 0.85em; color: #888; border-radius: 5px; margin-bottom: 6px; border: 1px solid #2a2a2a; }
        #choices-bar { background: #1a1a1a; padding: 6px 10px; text-align: center; font-size: 0.85em; border-radius: 5px; margin-bottom: 20px; border: 1px solid #2a2a2a; }
    </style>
    <script>
        var sleepUntil = null;
        var cycleData = {};

        function fetchStatus() {
            fetch('/status').then(r => r.text()).then(t => document.getElementById('status-bar').innerText = t);
        }

        function fetchState() {
            fetch('/state').then(r => r.json()).then(data => {
                cycleData = data;
                sleepUntil = data.sleep_until ? new Date(data.sleep_until) : null;
            });
        }

        var CHOICE_COLORS = {act: '#ff9800', reflect: '#2196f3', learn: '#4caf50', sleep: '#757575'};

        function updateCycleBar() {
            var bar = document.getElementById('cycle-bar');
            if (!cycleData.cycle) return;
            var thinkTime = cycleData.last_think_time ? cycleData.last_think_time.toFixed(1) + 's' : '—';
            var countdown = '';
            if (sleepUntil) {
                var remaining = Math.max(0, Math.floor((sleepUntil - new Date()) / 1000));
                if (remaining > 0) {
                    var m = Math.floor(remaining / 60);
                    var s = remaining % 60;
                    countdown = ' | Next wake in ' + m + 'm ' + String(s).padStart(2, '0') + 's';
                } else {
                    countdown = ' | Waking soon...';
                }
            }
            bar.innerText = 'Cycle ' + cycleData.cycle + ' | Last thought: ' + thinkTime + countdown;

            var choices = cycleData.recent_choices || [];
            if (choices.length) {
                var isLoop = choices.length >= 3 && choices.slice(-3).every(function(c) { return c === choices[choices.length - 1]; });
                var html = 'Recent: ' + choices.map(function(c) {
                    return '<span style="color:' + (CHOICE_COLORS[c] || '#e0e0e0') + ';font-weight:bold">' + c + '</span>';
                }).join(' &rarr; ');
                if (isLoop) html += ' <span style="color:#f44336;font-weight:bold">&#9888; loop</span>';
                document.getElementById('choices-bar').innerHTML = html;
            }
        }

        function scrollBoxes() {
            document.querySelectorAll('.box').forEach(function(b) { b.scrollTop = b.scrollHeight; });
        }

        function init() {
            fetchStatus();
            fetchState();
            scrollBoxes();
        }

        setInterval(fetchStatus, 2000);
        setInterval(fetchState, 5000);
        setInterval(updateCycleBar, 1000);
    </script>
</head>
<body onload="init()">
    <h2>Stan</h2>
    <div id="status-bar">Loading status...</div>
    <div id="cycle-bar">Loading...</div>
    <div id="choices-bar"></div>

    <form method="POST" action="/wake" style="margin-bottom: 10px;">
        <button type="submit" style="background: #1565c0;">Wake Up</button>
    </form>
    <h3>Message to Inbox</h3>
    <form method="POST" action="/send">
        <textarea name="message" rows="3" placeholder="Wake Stan up..."></textarea>
        <button type="submit">Send & Wake</button>
    </form>
    <h3>Conversation Log</h3>
    <div class="box">{{ outbox }}</div>
    <h3>Identity (self.txt)</h3>
    <div class="box">{{ self_txt }}</div>
    <h3>Toolkit (capabilities.txt)</h3>
    <div class="box">{{ capabilities_txt }}</div>
    <h3>Recent Journal</h3>
    <div class="box">{{ journal }}</div>
</body>
</html>
"""

@app.route('/')
def home():
    outbox = read_file(PATHS["outbox"]) or "(Empty)"
    self_txt = read_file(PATHS["self"]) or "(Empty)"
    capabilities_txt = read_file(PATHS["capabilities"]) or "(Empty)"
    j = read_file(PATHS["journal"])
    return render_template_string(
        HTML,
        outbox=outbox,
        self_txt=self_txt,
        capabilities_txt=capabilities_txt,
        journal=j[-3000:] if len(j) > 3000 else (j or "(Empty)")
    )

@app.route('/status')
def status():
    return read_file(PATHS["status"]) or "Status unknown"

@app.route('/state')
def state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            data = json.load(f)
        return Response(json.dumps({
            "cycle": data.get("cycle", 0),
            "last_think_time": data.get("last_think_time", 0),
            "sleep_until": data.get("sleep_until", ""),
            "recent_choices": data.get("recent_choices", [])
        }), mimetype="application/json")
    return Response(json.dumps({"cycle": 0, "last_think_time": 0, "sleep_until": "", "recent_choices": []}), mimetype="application/json")

@app.route('/wake', methods=['POST'])
def wake():
    with open(PATHS["inbox"], 'w') as f: f.write(" ")
    return redirect(url_for('home'))

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
