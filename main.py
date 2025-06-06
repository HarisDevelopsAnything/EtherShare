import customtkinter as ctk
import os
import subprocess
import sys
import ctypes
import time
import threading

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

def is_admin():
    """Check if the current process has administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Restart the script with administrator privileges"""
    if is_admin():
        return True
    else:
        # Re-run the program with admin rights
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                sys.executable, 
                " ".join(sys.argv), 
                None, 
                1
            )
            return False
        except:
            return False

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def set_static_ip(role):
    if role == "Sender":
        ip = "192.168.0.1"
        gateway = "192.168.0.2"
    else:
        ip = "192.168.0.2"
        gateway = "192.168.0.1"
    
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
    run_cmd(r'start \\192.168.0.1\Shared')

def wait_for_ping(ip, status_label):
    while True:
        result = run_cmd(f"ping -n 1 {ip}")
        if result.returncode == 0:
            break
        time.sleep(1)
    status_label.configure(text="Connected!", text_color="green")
    time.sleep(1)
    connect_to_share()

def revert_changes(role):
    print("[*] Reverting network configuration...")
    revert_ip()
    if role == "Sender":
        print("[i] Shared folder left intact.")

class FileShareApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("EtherShare")
        self.geometry("400x300")
        self.resizable(False, False)
        
        self.role = ctk.StringVar(value="Sender")		
        self.folder_path = ctk.StringVar(value="C:\\Shared")
        
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        ctk.CTkLabel(self, text="EtherShare", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
        
        ctk.CTkSegmentedButton(self, values=["Sender", "Receiver"], variable=self.role).pack(pady=10)
        
        self.folder_entry = ctk.CTkEntry(self, textvariable=self.folder_path, width=300)
        self.folder_entry.pack(pady=5)
        
        self.start_button = ctk.CTkButton(self, text="Start", command=self.start)
        self.start_button.pack(pady=20)
        
        self.status_label = ctk.CTkLabel(self, text="Ready to start (Running as Administrator)", text_color="green")
        self.status_label.pack(pady=10)

    def start(self):
        role = self.role.get()
        self.status_label.configure(text=f"Configuring as {role}...", text_color="blue")
        threading.Thread(target=self.process_role, daemon=True).start()

    def process_role(self):
        role = self.role.get()
        set_static_ip(role)
        
        if role == "Sender":
            enable_file_sharing()
            share_folder(self.folder_path.get())
            self.status_label.configure(text="Waiting for receiver...", text_color="orange")
            wait_for_ping("192.168.0.2", self.status_label)
        else:
            self.status_label.configure(text="Waiting for sender...", text_color="orange")
            wait_for_ping("192.168.0.1", self.status_label)

    def on_close(self):
        revert_changes(self.role.get())
        self.destroy()

if __name__ == "__main__":
    if os.name != "nt":
        print("This app is only for Windows.")
        sys.exit(1)
    
    # Check for admin privileges and request if needed
    if not is_admin():
        print("Requesting administrator privileges...")
        if run_as_admin():
            sys.exit(0)  # Exit current instance
        else:
            print("Administrator privileges are required to run this application.")
            input("Press Enter to exit...")
            sys.exit(1)
    
    # Run the application with admin privileges
    app = FileShareApp()
    app.mainloop()
