import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
import subprocess
import sys
import ctypes
import time
import threading
import json
import logging

# ---------------- Logging Setup ---------------- #
logging.basicConfig(
    filename="ethershare_log.txt",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Hide console window immediately on Windows
if os.name == 'nt':
    try:
        import ctypes.wintypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        console_window = kernel32.GetConsoleWindow()
        if console_window:
            user32.ShowWindow(console_window, 0)
    except Exception as e:
        logging.warning(f"Failed to hide console window: {e}")

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Try to relaunch script with admin privileges"""
    try:
        script_path = os.path.abspath(__file__)
        python_path = sys.executable
        pythonw_path = python_path.replace("python.exe", "pythonw.exe")

        if not os.path.exists(pythonw_path):
            logging.warning(f"pythonw.exe not found. Using python.exe instead.")
            pythonw_path = python_path

        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            pythonw_path,
            f'"{script_path}"',
            os.path.dirname(script_path),
            0
        )
        return ret > 32
    except Exception as e:
        logging.error(f"Admin elevation failed: {e}")
        return False

CONFIG_FILE = "ethershare_config.json"

def load_config():
    default_config = {
        "appearance_mode": "System",
        "color_theme": "blue"
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
        else:
            return default_config
    except Exception as e:
        logging.warning(f"Failed to load config: {e}")
        return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logging.warning(f"Failed to save config: {e}")

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def set_static_ip(role):
    ip = "192.168.0.1" if role == "Sender" else "192.168.0.2"
    gateway = "192.168.0.2" if role == "Sender" else "192.168.0.1"
    run_cmd(f'netsh interface ip set address name="Ethernet" static {ip} 255.255.255.0 {gateway}')

def revert_ip():
    run_cmd('netsh interface ip set address name="Ethernet" dhcp')
    run_cmd('netsh interface ip set dns name="Ethernet" dhcp')

def enable_file_sharing():
    run_cmd('netsh advfirewall firewall set rule group="File and Printer Sharing" new enable=Yes')

def share_folder(folder_path):
    folder_name = os.path.basename(folder_path)
    run_cmd(f'mkdir "{folder_path}"')
    run_cmd(f'net share Shared="{folder_path}" /grant:Everyone,full')
    run_cmd(f'icacls "{folder_path}" /grant Everyone:F /T')

def connect_to_share():
    run_cmd(r'start \\192.168.0.2\Shared')

def wait_for_ping(ip, status_label, app_instance):
    while True:
        result = run_cmd(f"ping -n 1 {ip}")
        if result.returncode == 0:
            break
        time.sleep(1)
    status_label.configure(text="Connected!", text_color="green")
    time.sleep(1)
    connect_to_share()
    app_instance.start_connection_monitoring(ip)

def monitor_connection(ip, status_label, stop_event):
    consecutive_failures = 0
    max_failures = 3
    while not stop_event.is_set():
        result = run_cmd(f"ping -n 1 -w 2000 {ip}")
        if result.returncode == 0:
            consecutive_failures = 0
            if status_label.cget("text") != "Connected!":
                status_label.configure(text="Connected!", text_color="green")
        else:
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                status_label.configure(text="Connection Lost!", text_color="red")
        time.sleep(2)

def revert_changes(role):
    logging.info("[*] Reverting network configuration...")
    revert_ip()
    if role == "Sender":
        logging.info("[i] Shared folder left intact.")

class FileShareApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.config_data = load_config()
        ctk.set_appearance_mode(self.config_data["appearance_mode"])
        ctk.set_default_color_theme(self.config_data["color_theme"])

        self.title("EtherShare")
        self.geometry("400x350")
        self.resizable(False, False)

        self.role = ctk.StringVar(value="Sender")
        self.folder_path = ctk.StringVar(value="C:\\Shared")

        self.monitoring_thread = None
        self.stop_monitoring = threading.Event()
        self.create_menu()
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_menu(self):
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)

        theme_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Theme", menu=theme_menu)

        appearance_menu = tk.Menu(theme_menu, tearoff=0)
        theme_menu.add_cascade(label="Appearance", menu=appearance_menu)
        for mode in ["Light", "Dark", "System"]:
            appearance_menu.add_command(label=mode, command=lambda m=mode: self.change_appearance(m))

        color_menu = tk.Menu(theme_menu, tearoff=0)
        theme_menu.add_cascade(label="Color Theme", menu=color_menu)
        for theme in ["blue", "green", "dark-blue"]:
            color_menu.add_command(label=theme.title(), command=lambda t=theme: self.change_color_theme(t))

        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def create_widgets(self):
        ctk.CTkLabel(self, text="EtherShare", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
        ctk.CTkSegmentedButton(self, values=["Sender", "Receiver"], variable=self.role).pack(pady=10)
        ctk.CTkEntry(self, textvariable=self.folder_path, width=300).pack(pady=5)
        ctk.CTkButton(self, text="Start", command=self.start).pack(pady=20)
        self.status_label = ctk.CTkLabel(self, text="Please connect ethernet cable to start. \nConnect the other end to other PC.", text_color="green")
        self.status_label.pack(pady=10)

    def change_appearance(self, mode):
        self.config_data["appearance_mode"] = mode
        save_config(self.config_data)
        ctk.set_appearance_mode(mode)

    def change_color_theme(self, theme):
        self.config_data["color_theme"] = theme
        save_config(self.config_data)
        messagebox.showinfo("Theme Saved", f"Theme changed to {theme.title()}.\nRestart to apply fully.")

    def show_about(self):
        messagebox.showinfo("About", "EtherShare v0.3 BETA\n\nSimple, fast local file sharing over direct connection.\nBy Haris S [HarisDevelopsAnything]\n 2025\nReleased under GNU GPL")

    def start(self):
        role = self.role.get()
        self.status_label.configure(text=f"Configuring as {role}...", text_color="blue")
        self.stop_connection_monitoring()
        threading.Thread(target=self.process_role, daemon=True).start()

    def process_role(self):
        try:
            role = self.role.get()
            set_static_ip(role)
            if role == "Sender":
                enable_file_sharing()
                share_folder(self.folder_path.get())
                self.status_label.configure(text="Waiting for receiver...", text_color="orange")
                wait_for_ping("192.168.0.2", self.status_label, self)
            else:
                self.status_label.configure(text="Waiting for sender...", text_color="orange")
                wait_for_ping("192.168.0.1", self.status_label, self)
        except Exception as e:
            logging.error(f"Error during role processing: {e}")
            self.status_label.configure(text="Error configuring network.", text_color="red")

    def start_connection_monitoring(self, ip):
        self.stop_connection_monitoring()
        self.stop_monitoring = threading.Event()
        self.monitoring_thread = threading.Thread(
            target=monitor_connection,
            args=(ip, self.status_label, self.stop_monitoring),
            daemon=True
        )
        self.monitoring_thread.start()

    def stop_connection_monitoring(self):
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.stop_monitoring.set()
            self.monitoring_thread.join(timeout=1)

    def on_close(self):
        self.stop_connection_monitoring()
        revert_changes(self.role.get())
        self.destroy()

# ----------------- Entry Point ------------------ #
if __name__ == "__main__":
    try:
        if os.name != "nt":
            print("EtherShare only works on Windows.")
            sys.exit(1)

        if not is_admin():
            print("Requesting administrator privileges...")
            if run_as_admin():
                sys.exit(0)
            else:
                messagebox.showerror("Admin Required", "Failed to run as administrator.")
                sys.exit(1)

        app = FileShareApp()
        app.mainloop()

    except Exception as e:
        logging.critical(f"Fatal error: {e}")
        if sys.stdin.isatty():
            input("Press Enter to exit...")
        sys.exit(1)
