import sys
import time
import json
import threading
import re
from collections import defaultdict
from pynput import keyboard
import tkinter as tk
from tkinter import filedialog, messagebox
from ctypes import wintypes, windll, create_unicode_buffer

# --- Behavior Data ---
current_file = sys.argv[1] if len(sys.argv) > 1 else "NoFile"

data = {
    'current_file': current_file,
    'keystrokes': 0,
    'backspace': 0,
    'typing_bursts': 0,
    'typing_pauses': [],
    'chars_per_minute': 0,
    'lines_added': 0,
    'lines_deleted': 0,
    'file_switches': 0,
    'idle_time': 0,
    'active_time': 0,
    'error_ratio': 0,
    'typing_consistency': 0,
    'file_stats': defaultdict(lambda: {'keystrokes':0, 'backspace':0}),
    'patterns': {}
}

last_active = time.time()
start_time = time.time()
last_keystroke_time = None
current_active_file = ''
previous_text = ''

# --- Detect active window title (Windows only) ---
def get_active_window_title():
    hwnd = windll.user32.GetForegroundWindow()
    length = windll.user32.GetWindowTextLengthW(hwnd)
    buff = create_unicode_buffer(length + 1)
    windll.user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value

# --- Detect active file in VS Code or Code::Blocks ---
def get_active_file():
    title = get_active_window_title()
    if 'Visual Studio Code' in title or 'Code::Blocks' in title:
        # title format: "filename - IDE name"
        parts = title.split(' - ')
        if parts:
            return parts[0]  # return the filename part
    return None

# --- Keystroke Listener ---
def on_press(key):
    global last_active, last_keystroke_time
    now = time.time()
    last_active = now

    # Typing bursts and pauses
    if last_keystroke_time:
        pause = now - last_keystroke_time
        if pause > 3:  # 3 seconds pause defines new burst
            data['typing_bursts'] += 1
            data['typing_pauses'].append(pause)
    last_keystroke_time = now

    # Track keys
    try:
        if hasattr(key, 'char') and key.char is not None:
            data['keystrokes'] += 1
        if key == keyboard.Key.backspace:
            data['backspace'] += 1
    except AttributeError:
        pass

listener = keyboard.Listener(on_press=on_press)
listener.start()

# --- Idle / Active Tracking ---
def track_idle():
    global last_active
    while True:
        now = time.time()
        idle = now - last_active
        data['idle_time'] = idle
        data['active_time'] = now - start_time - idle

        # Update error ratio and chars per minute
        data['error_ratio'] = data['backspace'] / max(1, data['keystrokes'])
        data['chars_per_minute'] = data['keystrokes'] / max(1, data['active_time']) * 60

        # Typing consistency = standard deviation of pauses
        if data['typing_pauses']:
            mean_pause = sum(data['typing_pauses']) / len(data['typing_pauses'])
            variance = sum((p - mean_pause)**2 for p in data['typing_pauses']) / len(data['typing_pauses'])
            data['typing_consistency'] = variance ** 0.5
        time.sleep(1)

threading.Thread(target=track_idle, daemon=True).start()

# --- Code Pattern Detection ---
def analyze_code(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        patterns = {
            'functions': len(re.findall(r'function\s+\w+\(', code)),
            'loops': len(re.findall(r'\b(for|while)\s*\(', code)),
            'if_statements': len(re.findall(r'\bif\s*\(', code)),
            'classes': len(re.findall(r'\bclass\s+\w+', code)),
            'console_logs': len(re.findall(r'console\.log\(', code)),
            'comments': len(re.findall(r'//|/\*', code))
        }
        data['patterns'] = patterns
        # Lines added/deleted
        lines = code.splitlines()
        data['lines_added'] = len(lines)
    except Exception:
        data['patterns'] = {}

# --- Dashboard GUI ---
root = tk.Tk()
root.title("Programmer Behavior Tracker")
root.geometry("450x500")

stats_text = tk.StringVar()
stats_label = tk.Label(root, textvariable=stats_text, justify="left", font=("Arial", 10))
stats_label.pack(pady=10)

def update_dashboard():
    global current_active_file

    # Get active file automatically
    active_file = get_active_file()
    if active_file and active_file != current_active_file:
        current_active_file = active_file
        data['current_file'] = current_active_file
        data['file_switches'] += 1

    if current_active_file:
        analyze_code(current_active_file)

    stats_text.set(
        f"File: {data['current_file']}\n"
        f"Keystrokes: {data['keystrokes']}\n"
        f"Backspace: {data['backspace']}\n"
        f"Typing Bursts: {data['typing_bursts']}\n"
        f"Average Pause: {sum(data['typing_pauses'])/max(1,len(data['typing_pauses'])):.2f}s\n"
        f"Chars per Minute: {data['chars_per_minute']:.2f}\n"
        f"Lines Added: {data['lines_added']}\n"
        f"File Switches: {data['file_switches']}\n"
        f"Idle Time: {data['idle_time']:.1f}s\n"
        f"Active Time: {data['active_time']:.1f}s\n"
        f"Error Ratio (Backspace/Keystrokes): {data['error_ratio']:.2f}\n"
        f"Typing Consistency (SD of pauses): {data['typing_consistency']:.2f}\n"
        f"Code Patterns: {data['patterns']}\n"
    )
    root.after(1000, update_dashboard)

# --- Export Button ---
def export_data():
    file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files","*.json")])
    if file_path:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Export", "Data exported successfully!")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

export_btn = tk.Button(root, text="Export Data", command=export_data)
export_btn.pack(pady=10)

# Start dashboard
update_dashboard()
root.mainloop()
