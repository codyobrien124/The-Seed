import datetime
import os
import psutil

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
        except Exception: pass
        
    journal_path = os.path.join(os.path.dirname(__file__), "journal.txt")
    if os.path.exists(journal_path):
        size = os.path.getsize(journal_path)
        with open(journal_path) as f:
            entries = f.read().count("--- cycle")
        readings.append(f"Journal: {entries} entries, {size} bytes")
        
    inbox_path = os.path.join(os.path.dirname(__file__), "inbox.txt")
    if os.path.exists(inbox_path):
        try:
            with open(inbox_path, "r+") as f:
                msg = f.read().strip()
                f.seek(0)
                f.truncate()
            if msg:
                readings.append(f"Message from human: {msg}")
        except Exception: pass
                
    return "\n".join(readings)
