import datetime
import os
import psutil
import urllib.request
import json

def get_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=10.66&longitude=-61.51&current=temperature_2m,relative_humidity_2m,weather_code"
        req = urllib.request.Request(url, headers={'User-Agent': 'Seed/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            current = data['current']
            temp = current['temperature_2m']
            humidity = current['relative_humidity_2m']
            code = current['weather_code']
            
            conditions = "Clear/Cloudy"
            if code in [0, 1]: conditions = "Clear skies"
            elif code in [2, 3]: conditions = "Partly cloudy"
            elif 50 <= code <= 69: conditions = "Raining"
            elif 80 <= code <= 99: conditions = "Heavy Rain / Storm"
            
            return f"Outside Weather: {temp}°C, Humidity: {humidity}%, Conditions: {conditions}"
    except Exception:
        return "Outside Weather: unknown (network error)"

def read_all():
    readings = []
    now = datetime.datetime.now()
    readings.append(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    readings.append(f"Day: {now.strftime('%A')}")
    readings.append(f"Hour: {now.hour}")
    
    if 6 <= now.hour < 18: readings.append("Sun: up (daytime)")
    else: readings.append("Sun: down (nighttime)")
    
    readings.append(f"CPU: {psutil.cpu_percent()}%")
    readings.append(f"RAM: {psutil.virtual_memory().percent}%")
    readings.append(f"Disk: {psutil.disk_usage('/').percent}%")
    
    thermal_path = "/sys/devices/virtual/thermal/thermal_zone0/temp"
    if os.path.exists(thermal_path):
        try:
            with open(thermal_path) as f:
                temp_c = int(f.read().strip()) / 1000
                readings.append(f"Board temp: {temp_c:.1f}°C")
        except: pass
        
    fan_path = "/sys/devices/pwm-fan/target_pwm"
    if os.path.exists(fan_path):
        try:
            with open(fan_path) as f:
                pwm_val = int(f.read().strip())
                fan_percent = int((pwm_val / 255.0) * 100)
                readings.append(f"Cooling Fan: {fan_percent}%")
        except: pass
        
    journal_path = os.path.join(os.path.dirname(__file__), "journal.txt")
    if os.path.exists(journal_path):
        size = os.path.getsize(journal_path)
        with open(journal_path) as f:
            entries = f.read().count("--- cycle")
        readings.append(f"Journal: {entries} entries, {size} bytes")
        
    inbox_path = os.path.join(os.path.dirname(__file__), "inbox.txt")
    if os.path.exists(inbox_path):
        with open(inbox_path) as f:
            msg = f.read().strip()
        if msg:
            readings.append(f"Message from human: {msg}")
            with open(inbox_path, "w") as f:
                f.write("")
                
    light_path = os.path.join(os.path.dirname(__file__), "light.txt")
    light_state = open(light_path).read().strip() if os.path.exists(light_path) else "OFF"
    readings.append(f"Virtual Grow Light: {light_state}")
    readings.append(get_weather())
    
    return "\n".join(readings)
