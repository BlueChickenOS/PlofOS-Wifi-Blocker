#!/usr/bin/env python3
"""
WiFi Control - Terminal App
By PlofOS Group
Control and limit your WiFi speed from the terminal.
Supports system-wide AND per-app bandwidth limits.
Requires admin/sudo privileges for applying changes.
"""

import os
import sys
import subprocess
import platform
import shutil
import time
import json
from datetime import datetime

# ─── Colors ────────────────────────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    GRAY    = "\033[90m"
    WHITE   = "\033[97m"
    MAGENTA = "\033[95m"

def clr(text, color):
    return f"{color}{text}{C.RESET}"

def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")

# ─── OS Detection ───────────────────────────────────────────────────────────────
OS = platform.system()

def is_linux():   return OS == "Linux"
def is_mac():     return OS == "Darwin"
def is_windows(): return OS == "Windows"

# ─── Admin Check ────────────────────────────────────────────────────────────────
def is_admin():
    if is_windows():
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        return os.geteuid() == 0

# ─── File Paths ─────────────────────────────────────────────────────────────────
def get_config_dir():
    """Return the directory where settings and logs are stored (same folder as this script)."""
    d = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(d, exist_ok=True)
    return d

SETTINGS_FILE = None   # set after config dir is ready
LOG_FILE      = None

def init_paths():
    global SETTINGS_FILE, LOG_FILE
    d = get_config_dir()
    SETTINGS_FILE = os.path.join(d, "settings.json")
    LOG_FILE      = os.path.join(d, "activity.log")

# ─── Logging ────────────────────────────────────────────────────────────────────
def log(action, detail="", level="INFO"):
    """Append a line to the activity log."""
    if LOG_FILE is None:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    line = f"[{ts}] [{level:<5}] [{user}] {action}"
    if detail:
        line += f" | {detail}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ─── Settings (auto-save + named profiles) ──────────────────────────────────────
def settings_to_dict():
    """Serialize current state into a plain dict for JSON storage."""
    return {
        "interface":     state.get("interface"),
        "download_kbit": state.get("download_kbit"),
        "upload_kbit":   state.get("upload_kbit"),
        "is_limited":    state.get("is_limited", False),
        "is_blocked":    state.get("is_blocked", False),
        "app_limits":    state.get("app_limits", {}),
    }

def load_settings_file():
    """Load the JSON settings file. Returns the full file content as a dict."""
    if not SETTINGS_FILE or not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def write_settings_file(data):
    """Write the full settings dict back to disk."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False

def autosave():
    """Automatically persist current state to the 'last_session' slot."""
    data = load_settings_file()
    data["last_session"] = settings_to_dict()
    data["last_saved"]   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_settings_file(data)

def restore_last_session():
    """
    On startup, load the last_session slot into state (interface only —
    we don't re-apply limits automatically since the OS resets on reboot).
    Returns True if a session was found.
    """
    data = load_settings_file()
    sess = data.get("last_session")
    if not sess:
        return False
    # Only restore interface preference — limits need to be re-applied manually
    if sess.get("interface"):
        state["interface"] = sess["interface"]
    log("STARTUP", f"Loaded last session — interface: {sess.get('interface')}")
    return True

def save_named_profile(name):
    """Save current state under a named profile."""
    data = load_settings_file()
    profiles = data.get("profiles", {})
    profiles[name] = {
        **settings_to_dict(),
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    data["profiles"] = profiles
    ok = write_settings_file(data)
    if ok:
        log("PROFILE_SAVE", f"Saved profile '{name}'")
    return ok

def load_named_profile(name):
    """Load a named profile into state. Returns the profile dict or None."""
    data = load_settings_file()
    profiles = data.get("profiles", {})
    return profiles.get(name)

def delete_named_profile(name):
    data = load_settings_file()
    profiles = data.get("profiles", {})
    if name in profiles:
        del profiles[name]
        data["profiles"] = profiles
        write_settings_file(data)
        log("PROFILE_DELETE", f"Deleted profile '{name}'")
        return True
    return False

def list_profiles():
    data = load_settings_file()
    return data.get("profiles", {})

# ─── Network Interface Detection ────────────────────────────────────────────────
def get_wifi_interface():
    if is_linux():
        try:
            result = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                if "IEEE 802.11" in line or "ESSID" in line:
                    iface = line.split()[0]
                    if iface:
                        return iface
        except Exception:
            pass
        try:
            ifaces = os.listdir("/sys/class/net/")
            for iface in ifaces:
                if iface.startswith(("wlan", "wlp", "wifi")):
                    return iface
        except Exception:
            pass
        return "wlan0"
    elif is_mac():
        try:
            result = subprocess.run(
                ["networksetup", "-listallhardwareports"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.splitlines()
            for i, line in enumerate(lines):
                if "Wi-Fi" in line or "AirPort" in line:
                    for j in range(i, min(i + 3, len(lines))):
                        if "Device:" in lines[j]:
                            return lines[j].split("Device:")[-1].strip()
        except Exception:
            pass
        return "en0"
    elif is_windows():
        try:
            result = subprocess.run(
                ["netsh", "interface", "show", "interface"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "Wi-Fi" in line or "Wireless" in line or "WLAN" in line:
                    parts = line.split()
                    if parts:
                        return " ".join(parts[3:]) if len(parts) > 3 else parts[-1]
        except Exception:
            pass
        return "Wi-Fi"
    return "wlan0"

# ─── Command Runner ─────────────────────────────────────────────────────────────
def run_cmd(cmd, sudo=False, input_text=None, shell=False):
    if sudo and is_linux() and not is_admin():
        cmd = ["sudo"] + cmd
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=20, input=input_text, shell=shell
        )
        return result.returncode == 0, result.stdout, result.stderr
    except FileNotFoundError as e:
        return False, "", str(e)
    except Exception as e:
        return False, "", str(e)

def run_ps(script):
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=20
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

# ─── Linux: tc system-wide ──────────────────────────────────────────────────────
def check_tc_available():
    return shutil.which("tc") is not None

def apply_linux_limit(iface, download_kbit, upload_kbit):
    run_cmd(["tc", "qdisc", "del", "dev", iface, "root"], sudo=True)
    run_cmd(["tc", "qdisc", "del", "dev", iface, "ingress"], sudo=True)
    errors = []
    for cmd in [
        ["tc", "qdisc", "add", "dev", iface, "root", "handle", "1:", "htb", "default", "12"],
        ["tc", "class", "add", "dev", iface, "parent", "1:", "classid", "1:1",
         "htb", "rate", f"{upload_kbit}kbit"],
        ["tc", "class", "add", "dev", iface, "parent", "1:1", "classid", "1:12",
         "htb", "rate", f"{upload_kbit}kbit"],
    ]:
        ok, _, err = run_cmd(cmd, sudo=True)
        if not ok and err.strip():
            errors.append(err.strip())
    if shutil.which("modprobe"):
        run_cmd(["modprobe", "ifb"], sudo=True)
        run_cmd(["ip", "link", "set", "dev", "ifb0", "up"], sudo=True)
        run_cmd(["tc", "qdisc", "add", "dev", iface, "handle", "ffff:", "ingress"], sudo=True)
        run_cmd(["tc", "filter", "add", "dev", iface, "parent", "ffff:", "protocol", "ip",
                 "u32", "match", "u32", "0", "0", "action", "mirred", "egress",
                 "redirect", "dev", "ifb0"], sudo=True)
        run_cmd(["tc", "qdisc", "add", "dev", "ifb0", "root", "handle", "1:", "htb", "default", "12"], sudo=True)
        run_cmd(["tc", "class", "add", "dev", "ifb0", "parent", "1:", "classid", "1:1",
                 "htb", "rate", f"{download_kbit}kbit"], sudo=True)
        run_cmd(["tc", "class", "add", "dev", "ifb0", "parent", "1:1", "classid", "1:12",
                 "htb", "rate", f"{download_kbit}kbit"], sudo=True)
    return len(errors) == 0, errors

def remove_linux_limit(iface):
    run_cmd(["tc", "qdisc", "del", "dev", iface, "root"], sudo=True)
    run_cmd(["tc", "qdisc", "del", "dev", iface, "ingress"], sudo=True)
    run_cmd(["tc", "qdisc", "del", "dev", "ifb0", "root"], sudo=True)
    return True, []

def block_linux(iface):
    run_cmd(["tc", "qdisc", "del", "dev", iface, "root"], sudo=True)
    ok, _, _ = run_cmd(
        ["tc", "qdisc", "add", "dev", iface, "root", "handle", "1:", "htb", "default", "12"],
        sudo=True
    )
    run_cmd(["tc", "class", "add", "dev", iface, "parent", "1:", "classid", "1:12",
             "htb", "rate", "1kbit"], sudo=True)
    return ok, []

# ─── Linux: per-app cgroup ──────────────────────────────────────────────────────
APP_CGROUP = "wifi_control_app"

def get_cgroup_classid(app_name):
    return abs(hash(app_name)) % 0xFFFE + 1

def apply_per_app_limit_linux(iface, app_name, pid, download_kbit, upload_kbit):
    errors = []
    ok, out, _ = run_cmd(["tc", "qdisc", "show", "dev", iface])
    if "htb" not in out or "root" not in out:
        run_cmd(["tc", "qdisc", "del", "dev", iface, "root"], sudo=True)
        run_cmd(["tc", "qdisc", "add", "dev", iface, "root", "handle", "1:", "htb", "default", "99"], sudo=True)
        run_cmd(["tc", "class", "add", "dev", iface, "parent", "1:", "classid", "1:99",
                 "htb", "rate", "1000mbit"], sudo=True)
    minor = get_cgroup_classid(app_name)
    classid_str  = f"1:{minor}"
    full_classid = (1 << 16) | minor
    run_cmd(["tc", "class", "del", "dev", iface, "classid", classid_str], sudo=True)
    ok, _, err = run_cmd([
        "tc", "class", "add", "dev", iface, "parent", "1:", "classid", classid_str,
        "htb", "rate", f"{upload_kbit}kbit", "ceil", f"{upload_kbit}kbit"
    ], sudo=True)
    if not ok and err.strip():
        errors.append(f"class: {err.strip()}")
    net_cls_path = f"/sys/fs/cgroup/net_cls/{APP_CGROUP}_{app_name}"
    run_cmd(["mkdir", "-p", net_cls_path], sudo=True)
    subprocess.run(["sudo", "bash", "-c",
                    f"echo {full_classid} > {net_cls_path}/net_cls.classid"], capture_output=True)
    subprocess.run(["sudo", "bash", "-c",
                    f"echo {pid} > {net_cls_path}/cgroup.procs"], capture_output=True)
    run_cmd(["tc", "filter", "del", "dev", iface, "parent", "1:",
             "handle", hex(full_classid), "cgroup"], sudo=True)
    run_cmd(["tc", "filter", "add", "dev", iface, "parent", "1:",
             "handle", hex(full_classid), "cgroup"], sudo=True)
    return len(errors) == 0, errors, classid_str

def remove_per_app_limit_linux(iface, app_name):
    minor        = get_cgroup_classid(app_name)
    classid_str  = f"1:{minor}"
    full_classid = (1 << 16) | minor
    run_cmd(["tc", "filter", "del", "dev", iface, "parent", "1:",
             "handle", hex(full_classid), "cgroup"], sudo=True)
    run_cmd(["tc", "class", "del", "dev", iface, "classid", classid_str], sudo=True)
    run_cmd(["rmdir", f"/sys/fs/cgroup/net_cls/{APP_CGROUP}_{app_name}"], sudo=True)
    return True, []

# ─── macOS ──────────────────────────────────────────────────────────────────────
def apply_mac_limit(iface, download_kbit, upload_kbit):
    errors = []
    for cmd in [
        ["dnctl", "pipe", "1", "config", "bw", f"{download_kbit}Kbit/s"],
        ["dnctl", "pipe", "2", "config", "bw", f"{upload_kbit}Kbit/s"],
    ]:
        ok, _, err = run_cmd(cmd, sudo=True)
        if not ok:
            errors.append(err.strip())
    pf_rule    = f"dummynet in on {iface} all pipe 1\ndummynet out on {iface} all pipe 2\n"
    pf_anchor  = "/etc/pf.anchors/wifi_control"
    try:
        subprocess.run(["sudo", "tee", pf_anchor], input=pf_rule, text=True, capture_output=True)
        run_cmd(["pfctl", "-a", "wifi_control", "-f", pf_anchor], sudo=True)
        run_cmd(["pfctl", "-e"], sudo=True)
    except Exception as e:
        errors.append(str(e))
    return len(errors) == 0, errors

def remove_mac_limit():
    run_cmd(["dnctl", "-q", "flush"], sudo=True)
    run_cmd(["pfctl", "-a", "wifi_control", "-F", "all"], sudo=True)
    return True, []

# ─── Windows ────────────────────────────────────────────────────────────────────
WIN_QOS_POLICY = "WiFiControl_SystemLimit"

def apply_windows_limit(download_kbps, upload_kbps):
    errors = []
    run_ps(f'Remove-NetQosPolicy -Name "{WIN_QOS_POLICY}" -Confirm:$false -ErrorAction SilentlyContinue')
    upload_bps = upload_kbps * 1000
    ok, _, err = run_ps(
        f'New-NetQosPolicy -Name "{WIN_QOS_POLICY}" '
        f'-NetworkProfile All -ThrottleRateActionBitsPerSecond {upload_bps}'
    )
    if not ok:
        errors.append(err or "QoS policy creation failed")
    run_ps('netsh int tcp set global autotuninglevel=disabled')
    return len(errors) == 0, errors

def remove_windows_limit():
    run_ps(f'Remove-NetQosPolicy -Name "{WIN_QOS_POLICY}" -Confirm:$false -ErrorAction SilentlyContinue')
    run_ps('netsh int tcp set global autotuninglevel=normal')
    return True, []

def block_windows(iface):
    errors = []
    run_ps('Remove-NetFirewallRule -DisplayName "WiFiControl_Block" -ErrorAction SilentlyContinue')
    ok, _, err = run_ps(
        f'New-NetFirewallRule -DisplayName "WiFiControl_Block" '
        f'-Direction Outbound -Action Block -InterfaceAlias "{iface}" -Enabled True; '
        f'New-NetFirewallRule -DisplayName "WiFiControl_Block_In" '
        f'-Direction Inbound -Action Block -InterfaceAlias "{iface}" -Enabled True'
    )
    if not ok:
        errors.append(err or "Firewall rule creation failed")
    return ok, errors

def unblock_windows():
    run_ps('Remove-NetFirewallRule -DisplayName "WiFiControl_Block" -ErrorAction SilentlyContinue')
    run_ps('Remove-NetFirewallRule -DisplayName "WiFiControl_Block_In" -ErrorAction SilentlyContinue')
    return True, []

def apply_per_app_limit_windows(app_name, exe_path, download_kbps, upload_kbps):
    policy_name = f"WiFiControl_App_{app_name}"
    errors = []
    upload_bps = upload_kbps * 1000
    run_ps(f'Remove-NetQosPolicy -Name "{policy_name}" -Confirm:$false -ErrorAction SilentlyContinue')
    ok, _, err = run_ps(
        f'New-NetQosPolicy -Name "{policy_name}" '
        f'-AppPathNameMatchCondition "{exe_path}" '
        f'-NetworkProfile All -ThrottleRateActionBitsPerSecond {upload_bps}'
    )
    if not ok:
        errors.append(err or "QoS per-app policy failed")
    return ok, errors

def remove_per_app_limit_windows(app_name):
    run_ps(f'Remove-NetQosPolicy -Name "WiFiControl_App_{app_name}" -Confirm:$false -ErrorAction SilentlyContinue')
    return True, []

def block_app_windows(app_name, exe_path):
    rule_out = f"WiFiControl_AppBlock_{app_name}_Out"
    rule_in  = f"WiFiControl_AppBlock_{app_name}_In"
    errors   = []
    run_ps(f'Remove-NetFirewallRule -DisplayName "{rule_out}" -ErrorAction SilentlyContinue')
    run_ps(f'Remove-NetFirewallRule -DisplayName "{rule_in}" -ErrorAction SilentlyContinue')
    ok, _, err = run_ps(
        f'New-NetFirewallRule -DisplayName "{rule_out}" -Direction Outbound '
        f'-Program "{exe_path}" -Action Block -Enabled True; '
        f'New-NetFirewallRule -DisplayName "{rule_in}" -Direction Inbound '
        f'-Program "{exe_path}" -Action Block -Enabled True'
    )
    if not ok:
        errors.append(err or "Firewall app-block rule failed")
    return ok, errors

def unblock_app_windows(app_name):
    run_ps(f'Remove-NetFirewallRule -DisplayName "WiFiControl_AppBlock_{app_name}_Out" -ErrorAction SilentlyContinue')
    run_ps(f'Remove-NetFirewallRule -DisplayName "WiFiControl_AppBlock_{app_name}_In" -ErrorAction SilentlyContinue')
    return True, []

def list_windows_processes():
    ok, out, _ = run_ps(
        'Get-Process | Select-Object Id,ProcessName,Path | '
        'ConvertTo-Csv -NoTypeInformation | Select-Object -Skip 1'
    )
    procs = []
    if ok and out:
        for line in out.strip().splitlines():
            parts = line.strip('"').split('","')
            if len(parts) >= 2:
                pid  = parts[0].strip('"')
                name = parts[1].strip('"')
                path = parts[2].strip('"') if len(parts) > 2 else ""
                procs.append((pid, name, path))
    return procs

# ─── State ───────────────────────────────────────────────────────────────────────
state = {
    "interface":     None,
    "download_kbit": None,
    "upload_kbit":   None,
    "is_limited":    False,
    "is_blocked":    False,
    "app_limits":    {},
}

# ─── UI Helpers ──────────────────────────────────────────────────────────────────
def header():
    print(clr("╔══════════════════════════════════════════╗", C.CYAN))
    print(clr("║        WiFi Control - Terminal App        ║", C.CYAN))
    print(clr("║          by PlofOS Group                  ║", C.MAGENTA))
    print(clr("╚══════════════════════════════════════════╝", C.CYAN))
    print()

def fmt_speed(kbit):
    if kbit is None:
        return "—"
    if kbit >= 1000:
        return f"{kbit // 1000} Mbps"
    return f"{kbit} Kbps"

def status_line():
    iface = clr(state["interface"] or "auto", C.YELLOW)
    if state["is_blocked"]:
        status = clr("● BLOCKED", C.RED)
    elif state["is_limited"]:
        dl = fmt_speed(state["download_kbit"])
        ul = fmt_speed(state["upload_kbit"])
        status = clr(f"● LIMITED  ↓{dl} ↑{ul}", C.YELLOW)
    else:
        status = clr("● UNRESTRICTED", C.GREEN)
    print(f"  Interface : {iface}    Status: {status}")
    if state["app_limits"]:
        print(clr(f"  App limits: {len(state['app_limits'])} active", C.MAGENTA))
    os_tag    = clr(f"[{OS}]", C.GRAY)
    admin_tag = clr("[admin]", C.GREEN) if is_admin() else clr("[no admin]", C.RED)
    print(f"  {os_tag} {admin_tag}")
    print(clr("  ─────────────────────────────────────────", C.GRAY))
    print()

def prompt_int(msg, min_val=None, max_val=None):
    while True:
        try:
            val = int(input(clr(f"  {msg}: ", C.WHITE)))
            if min_val is not None and val < min_val:
                print(clr(f"  ✗ Must be at least {min_val}.", C.RED))
                continue
            if max_val is not None and val > max_val:
                print(clr(f"  ✗ Must be at most {max_val}.", C.RED))
                continue
            return val
        except ValueError:
            print(clr("  ✗ Please enter a valid number.", C.RED))
        except (KeyboardInterrupt, EOFError):
            print()
            return None

def kbps_from_menu(label=""):
    presets = [
        ("1", "Near-zero  (    1 Kbps — effectively blocks)", 1),
        ("2", "Dial-up    (   56 Kbps)",                      56),
        ("3", "Very slow  (  512 Kbps)",                      512),
        ("4", "Slow       (    1 Mbps)",                      1000),
        ("5", "Medium     (    5 Mbps)",                      5000),
        ("6", "Fast       (   25 Mbps)",                      25000),
        ("7", "Very fast  (  100 Mbps)",                      100000),
        ("8", "Custom (enter manually)",                      None),
    ]
    if label:
        print(clr(f"  — {label} —", C.CYAN))
    for key, lbl, _ in presets:
        print(f"    {clr(key, C.CYAN)}.  {lbl}")
    print()
    while True:
        choice = input(clr("  Choose preset [1-8]: ", C.WHITE)).strip()
        for key, _, val in presets:
            if choice == key:
                if val is not None:
                    return val
                return prompt_int("Enter speed in Kbps (min 1)", min_val=1, max_val=10_000_000)
        print(clr("  ✗ Invalid choice.", C.RED))

def print_ok(msg):   print(clr(f"  ✓ {msg}", C.GREEN))
def print_err(msg):  print(clr(f"  ✗ {msg}", C.RED))
def print_info(msg): print(clr(f"  ℹ {msg}", C.GRAY))
def pause():         input(clr("\n  Press Enter to continue...", C.GRAY))

# ─── Process Browser ─────────────────────────────────────────────────────────────
def list_running_processes():
    if is_windows():
        return list_windows_processes()
    try:
        cmd = ["ps", "aux", "--sort=-pcpu"] if is_linux() else ["ps", "aux"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        procs = []
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            pid  = parts[1]
            cmd_ = parts[10].strip()
            name = os.path.basename(cmd_.split()[0]) if cmd_ else "?"
            procs.append((pid, name, cmd_[:60]))
        return procs
    except Exception:
        return []

def _browse_processes(all_procs):
    active_filter = ""
    page          = 0
    page_size     = 16
    while True:
        filtered = (
            [(p, n, c) for p, n, c in all_procs
             if active_filter in n.lower() or active_filter in c.lower()]
            if active_filter else all_procs
        )
        total = len(filtered)
        if total > 0 and page * page_size >= total:
            page = max(0, (total - 1) // page_size)
        start = page * page_size
        chunk = filtered[start:start + page_size]

        print()
        filter_tag = (clr(f' (filter: "{active_filter}", {total} results)', C.YELLOW)
                      if active_filter else clr(f" ({total} total)", C.GRAY))
        print(clr(f"  Processes [{start+1}–{start+len(chunk)}]", C.BOLD) + filter_tag)
        print(clr("  " + "─" * 62, C.GRAY))

        if not chunk:
            print(clr("  No processes match your filter.", C.GRAY))
        else:
            for i, (pid, name, cmd_) in enumerate(chunk, 1):
                disp_name = name
                if active_filter and active_filter in name.lower():
                    idx = name.lower().index(active_filter)
                    disp_name = (name[:idx]
                                 + clr(name[idx:idx+len(active_filter)], C.YELLOW)
                                 + name[idx+len(active_filter):])
                print(f"    {clr(str(i), C.CYAN)}.  {clr(pid, C.MAGENTA):>14}  "
                      f"{disp_name:<30}  {clr(cmd_[:28], C.GRAY)}")

        print()
        hints = []
        if start + page_size < total:
            hints.append(f"{clr('n', C.GRAY)} next")
        if page > 0:
            hints.append(f"{clr('p', C.GRAY)} prev")
        hints.append(f"{clr('/keyword', C.CYAN)} search")
        if active_filter:
            hints.append(f"{clr('/clear', C.CYAN)} clear filter")
        hints.append(f"{clr('0', C.GRAY)} cancel")
        print("  " + "  │  ".join(hints))
        print()

        sel = input(clr("  Pick # / n / p / /keyword / 0: ", C.WHITE)).strip()

        if sel == "0":
            return None, None
        elif sel.lower() == "n" and start + page_size < total:
            page += 1
        elif sel.lower() == "p" and page > 0:
            page -= 1
        elif sel.startswith("/"):
            keyword = sel[1:].strip().lower()
            active_filter = "" if keyword == "clear" else keyword
            page = 0
        else:
            try:
                idx = int(sel)
                if 1 <= idx <= len(chunk):
                    pid, name, path = chunk[idx - 1]
                    if is_windows() and path:
                        return path, name
                    return pid, name
                print_err("Out of range.")
            except ValueError:
                print_err("Invalid input.")

def pick_process():
    print()
    print(clr("  How would you like to identify the app?\n", C.BOLD))
    if is_windows():
        print(f"    {clr('1', C.CYAN)}.  Enter .exe path directly")
        print(f"    {clr('2', C.CYAN)}.  Browse / search running processes")
    else:
        print(f"    {clr('1', C.CYAN)}.  Enter PID directly")
        print(f"    {clr('2', C.CYAN)}.  Browse / search running processes")
    print(f"    {clr('0', C.GRAY)}.  Cancel")
    print()
    choice = input(clr("  Choose [0-2]: ", C.WHITE)).strip()

    if choice == "1":
        if is_windows():
            exe  = input(clr("  Full .exe path: ", C.WHITE)).strip()
            name = input(clr("  Label (e.g. 'firefox'): ", C.WHITE)).strip() or os.path.basename(exe)
            return exe, name
        else:
            pid = prompt_int("Enter PID", min_val=1)
            if pid is None:
                return None, None
            name = input(clr("  Label (e.g. 'firefox'): ", C.WHITE)).strip() or f"pid_{pid}"
            return str(pid), name

    elif choice == "2":
        print_info("Loading process list...")
        procs = list_running_processes()
        if not procs:
            print_err("Could not list processes.")
            return None, None
        print_info("Tip: /keyword to filter  │  /clear to reset  │  n/p to page")
        return _browse_processes(procs)

    return None, None

# ─── Actions ─────────────────────────────────────────────────────────────────────
def action_set_interface():
    clear(); header()
    print(clr("  [ Set Interface ]\n", C.BOLD))
    detected = get_wifi_interface()
    print(f"  Auto-detected: {clr(detected, C.YELLOW)}")
    print()
    iface = input(clr(f"  Enter name (Enter to keep '{detected}'): ", C.WHITE)).strip()
    if not iface:
        iface = detected
    old = state["interface"]
    state["interface"] = iface
    log("SET_INTERFACE", f"{old} → {iface}")
    autosave()
    print_ok(f"Interface set to '{iface}'.")
    pause()

def action_set_speed():
    clear(); header()
    print(clr("  [ System-Wide Speed Limit ]\n", C.BOLD))
    if not state["interface"]:
        state["interface"] = get_wifi_interface()

    dl = kbps_from_menu("Download Speed")
    if dl is None:
        return
    print()
    ul = kbps_from_menu("Upload Speed")
    if ul is None:
        return

    iface = state["interface"]
    print()
    print(f"  Applying: ↓{clr(fmt_speed(dl), C.YELLOW)}  ↑{clr(fmt_speed(ul), C.YELLOW)}  on {clr(iface, C.CYAN)}")
    print()

    success = False
    if is_linux():
        if not check_tc_available():
            print_err("'tc' not found. Install: sudo apt install iproute2")
            log("SET_SPEED", f"FAILED — tc not available", level="WARN")
        else:
            ok, errs = apply_linux_limit(iface, dl, ul)
            if ok:
                success = True
                print_ok("Speed limit applied.")
            else:
                print_err("Failed to apply limit:")
                for e in errs:
                    if e: print(clr(f"    {e}", C.RED))
                log("SET_SPEED", f"FAILED — {'; '.join(e for e in errs if e)}", level="ERROR")

    elif is_mac():
        ok, errs = apply_mac_limit(iface, dl, ul)
        if ok:
            success = True
            print_ok("Speed limit applied.")
        else:
            print_err("Failed:")
            for e in errs:
                if e: print(clr(f"    {e}", C.RED))
            log("SET_SPEED", f"FAILED — {'; '.join(e for e in errs if e)}", level="ERROR")

    elif is_windows():
        if not is_admin():
            print_err("Administrator rights required. Run as Administrator.")
            log("SET_SPEED", "FAILED — no admin rights", level="WARN")
        else:
            ok, errs = apply_windows_limit(dl, ul)
            if ok:
                success = True
                print_ok("Speed limit applied.")
            else:
                print_err("Failed:")
                for e in errs:
                    if e: print(clr(f"    {e}", C.RED))
                log("SET_SPEED", f"FAILED — {'; '.join(e for e in errs if e)}", level="ERROR")

    if success:
        state["download_kbit"] = dl
        state["upload_kbit"]   = ul
        state["is_limited"]    = True
        state["is_blocked"]    = False
        log("SET_SPEED", f"↓{fmt_speed(dl)} ↑{fmt_speed(ul)} on {iface}")
        autosave()

    pause()

def action_per_app_limit():
    clear(); header()
    print(clr("  [ Per-App Speed Limit ]\n", C.BOLD))
    if not state["interface"]:
        state["interface"] = get_wifi_interface()

    if is_windows():
        print_info("Windows: QoS per .exe (upload throttle) or full Firewall block.")
        print()
        print(f"    {clr('1', C.CYAN)}.  Throttle app speed (QoS)")
        print(f"    {clr('2', C.CYAN)}.  Block app entirely (Firewall)")
        print(f"    {clr('0', C.GRAY)}.  Cancel")
        print()
        sub = input(clr("  Choose [0-2]: ", C.WHITE)).strip()
        if sub == "0":
            return
        elif sub == "2":
            _action_block_app_windows()
            return
    elif is_linux():
        if not check_tc_available():
            print_err("'tc' not found. Install: sudo apt install iproute2")
            pause()
            return
    elif is_mac():
        print_err("Per-app limiting is not supported on macOS via CLI.")
        pause()
        return

    print(clr("  Step 1: Identify the app\n", C.CYAN))
    pid_or_exe, app_name = pick_process()
    if pid_or_exe is None:
        print_info("Cancelled.")
        pause()
        return

    print()
    print(clr("  Step 2: Set speeds\n", C.CYAN))
    dl = kbps_from_menu("Download Speed")
    if dl is None:
        return
    print()
    ul = kbps_from_menu("Upload Speed")
    if ul is None:
        return

    print()
    print(f"  Applying to {clr(app_name, C.CYAN)}: "
          f"↓{clr(fmt_speed(dl), C.YELLOW)}  ↑{clr(fmt_speed(ul), C.YELLOW)}")
    print()

    if is_linux():
        ok, errs, classid = apply_per_app_limit_linux(
            state["interface"], app_name, pid_or_exe, dl, ul
        )
        if ok:
            state["app_limits"][app_name] = {
                "pid": pid_or_exe, "download_kbit": dl,
                "upload_kbit": ul, "classid": classid, "type": "throttle"
            }
            log("APP_LIMIT", f"'{app_name}' PID={pid_or_exe} ↓{fmt_speed(dl)} ↑{fmt_speed(ul)}")
            autosave()
            print_ok(f"Limit applied to '{app_name}'.")
        else:
            print_err("Errors occurred:")
            for e in errs:
                if e: print(clr(f"    {e}", C.RED))
            log("APP_LIMIT", f"FAILED for '{app_name}' — {'; '.join(e for e in errs if e)}", level="ERROR")

    elif is_windows():
        if not is_admin():
            print_err("Administrator rights required.")
            log("APP_LIMIT", "FAILED — no admin rights", level="WARN")
        else:
            ok, errs = apply_per_app_limit_windows(app_name, pid_or_exe, dl, ul)
            if ok:
                state["app_limits"][app_name] = {
                    "exe": pid_or_exe, "download_kbit": dl,
                    "upload_kbit": ul, "type": "throttle"
                }
                log("APP_LIMIT", f"'{app_name}' exe={pid_or_exe} ↓{fmt_speed(dl)} ↑{fmt_speed(ul)}")
                autosave()
                print_ok(f"Limit applied to '{app_name}'.")
            else:
                print_err("Failed:")
                for e in errs:
                    if e: print(clr(f"    {e}", C.RED))
                log("APP_LIMIT", f"FAILED for '{app_name}' — {'; '.join(e for e in errs if e)}", level="ERROR")

    pause()

def _action_block_app_windows():
    print()
    print(clr("  [ Block App - Windows Firewall ]\n", C.BOLD))
    pid_or_exe, app_name = pick_process()
    if pid_or_exe is None:
        return
    print()
    if not is_admin():
        print_err("Administrator rights required.")
        log("APP_BLOCK", "FAILED — no admin rights", level="WARN")
    else:
        ok, errs = block_app_windows(app_name, pid_or_exe)
        if ok:
            state["app_limits"][app_name] = {"exe": pid_or_exe, "type": "block"}
            log("APP_BLOCK", f"'{app_name}' blocked via Firewall exe={pid_or_exe}")
            autosave()
            print_ok(f"'{app_name}' is now blocked via Windows Firewall.")
        else:
            print_err("Failed:")
            for e in errs:
                if e: print(clr(f"    {e}", C.RED))
            log("APP_BLOCK", f"FAILED for '{app_name}' — {'; '.join(e for e in errs if e)}", level="ERROR")
    pause()

def action_view_app_limits():
    clear(); header()
    print(clr("  [ Active App Limits ]\n", C.BOLD))
    if not state["app_limits"]:
        print_info("No per-app limits active.")
        pause()
        return

    print(f"  {'App':<22} {'Type':<10} {'Download':<12} {'Upload':<12} {'PID/EXE'}")
    print(clr("  " + "─" * 68, C.GRAY))
    for name, info in state["app_limits"].items():
        kind      = info.get("type", "throttle")
        dl        = fmt_speed(info.get("download_kbit")) if kind == "throttle" else "BLOCKED"
        ul        = fmt_speed(info.get("upload_kbit"))   if kind == "throttle" else "BLOCKED"
        ref       = str(info.get("pid") or info.get("exe", "?"))[:30]
        color     = C.RED if kind == "block" else C.YELLOW
        print(f"  {clr(name, C.CYAN):<31} {clr(kind, color):<19} "
              f"{clr(dl, C.WHITE):<21} {clr(ul, C.WHITE):<21} {clr(ref, C.GRAY)}")

    print()
    remove = input(clr("  Remove a limit? Enter app name (or Enter to go back): ", C.WHITE)).strip()
    if remove and remove in state["app_limits"]:
        info  = state["app_limits"][remove]
        iface = state["interface"] or get_wifi_interface()
        if is_linux():
            remove_per_app_limit_linux(iface, remove)
        elif is_windows():
            if info.get("type") == "block":
                unblock_app_windows(remove)
            else:
                remove_per_app_limit_windows(remove)
        del state["app_limits"][remove]
        log("APP_LIMIT_REMOVE", f"Removed limit for '{remove}'")
        autosave()
        print_ok(f"Limit removed for '{remove}'.")
    elif remove:
        print_err(f"'{remove}' not found in active limits.")
    pause()

def action_block_wifi():
    clear(); header()
    print(clr("  [ Block All WiFi Traffic ]\n", C.BOLD))
    if not state["interface"]:
        state["interface"] = get_wifi_interface()
    iface = state["interface"]
    print(f"  This will {clr('block ALL traffic', C.RED)} on {clr(iface, C.CYAN)}.")
    confirm = input(clr("  Type 'yes' to confirm: ", C.WHITE)).strip().lower()
    if confirm != "yes":
        print_info("Cancelled.")
        log("BLOCK_WIFI", "Cancelled by user")
        pause()
        return
    print()
    success = False
    if is_linux():
        if not check_tc_available():
            print_err("'tc' not found. Install: sudo apt install iproute2")
            log("BLOCK_WIFI", "FAILED — tc not available", level="WARN")
        else:
            ok, _ = block_linux(iface)
            if ok:
                success = True
                print_ok("WiFi blocked.")
    elif is_mac():
        ok, _ = apply_mac_limit(iface, 1, 1)
        if ok:
            success = True
            print_ok("WiFi effectively blocked.")
    elif is_windows():
        if not is_admin():
            print_err("Administrator rights required. Run as Administrator.")
            log("BLOCK_WIFI", "FAILED — no admin rights", level="WARN")
        else:
            ok, errs = block_windows(iface)
            if ok:
                success = True
                print_ok("WiFi blocked via Windows Firewall.")
            else:
                print_err("Failed:")
                for e in errs:
                    if e: print(clr(f"    {e}", C.RED))
                log("BLOCK_WIFI", f"FAILED — {'; '.join(e for e in errs if e)}", level="ERROR")

    if success:
        state["is_blocked"] = True
        state["is_limited"] = False
        log("BLOCK_WIFI", f"Blocked all traffic on {iface}")
        autosave()

    pause()

def action_remove_limits():
    clear(); header()
    print(clr("  [ Remove All Restrictions ]\n", C.BOLD))
    if not state["interface"]:
        state["interface"] = get_wifi_interface()
    iface = state["interface"]
    print(f"  Removing all limits on {clr(iface, C.CYAN)}...")
    print()
    if is_linux():
        remove_linux_limit(iface)
        for name in list(state["app_limits"].keys()):
            remove_per_app_limit_linux(iface, name)
    elif is_mac():
        remove_mac_limit()
    elif is_windows():
        if not is_admin():
            print_err("Administrator rights required.")
            log("REMOVE_LIMITS", "FAILED — no admin rights", level="WARN")
            pause()
            return
        remove_windows_limit()
        unblock_windows()
        for name, info in list(state["app_limits"].items()):
            if info.get("type") == "block":
                unblock_app_windows(name)
            else:
                remove_per_app_limit_windows(name)

    state["is_limited"]    = False
    state["is_blocked"]    = False
    state["download_kbit"] = None
    state["upload_kbit"]   = None
    state["app_limits"]    = {}
    log("REMOVE_LIMITS", f"All restrictions removed on {iface}")
    autosave()
    print_ok("All restrictions removed. WiFi is unrestricted.")
    pause()

def action_show_info():
    clear(); header()
    print(clr("  [ System Info ]\n", C.BOLD))
    iface = state["interface"] or get_wifi_interface()
    print(f"  OS           : {clr(f'{OS} ({platform.release()})', C.CYAN)}")
    print(f"  Interface    : {clr(iface, C.YELLOW)}")
    print(f"  Admin        : {clr(str(is_admin()), C.GREEN if is_admin() else C.RED)}")
    print(f"  Settings dir : {clr(get_config_dir(), C.GRAY)}")

    if is_linux():
        tc_ok = check_tc_available()
        print(f"  tc (iproute2): {clr(str(tc_ok), C.GREEN if tc_ok else C.RED)}")
        if not tc_ok:
            print_info("Install tc with: sudo apt install iproute2")
        print()
        print(clr("  Current tc rules:", C.BOLD))
        ok, out, _ = run_cmd(["tc", "qdisc", "show", "dev", iface])
        for line in (out.strip().splitlines() or ["(none)"]):
            print(f"    {clr(line, C.GRAY)}")

    elif is_windows():
        print()
        print(clr("  Active QoS Policies:", C.BOLD))
        ok, out, _ = run_ps(
            'Get-NetQosPolicy | Where-Object {$_.Name -like "WiFiControl*"} | '
            'Select-Object Name,ThrottleRateActionBitsPerSecond | Format-Table -AutoSize'
        )
        for line in (out.strip().splitlines() or ["  (none)"]):
            print(f"    {clr(line, C.GRAY)}")
        print()
        print(clr("  Active Firewall Rules:", C.BOLD))
        ok, out, _ = run_ps(
            'Get-NetFirewallRule | Where-Object {$_.DisplayName -like "WiFiControl*"} | '
            'Select-Object DisplayName,Enabled | Format-Table -AutoSize'
        )
        for line in (out.strip().splitlines() or ["  (none)"]):
            print(f"    {clr(line, C.GRAY)}")

    if state["app_limits"]:
        print()
        print(clr("  Per-app limits:", C.BOLD))
        for name, info in state["app_limits"].items():
            kind = info.get("type", "throttle")
            if kind == "block":
                print(f"    {clr(name, C.CYAN)}: {clr('BLOCKED', C.RED)}")
            else:
                print(f"    {clr(name, C.CYAN)}: ↓{fmt_speed(info.get('download_kbit'))}  ↑{fmt_speed(info.get('upload_kbit'))}")

    pause()

# ─── Settings & Profiles Action ──────────────────────────────────────────────────
def action_settings_menu():
    while True:
        clear(); header(); status_line()
        print(clr("  Settings & Profiles\n", C.BOLD))

        profiles = list_profiles()
        data     = load_settings_file()
        last_saved = data.get("last_saved", "never")

        print(f"  Config dir  : {clr(get_config_dir(), C.GRAY)}")
        print(f"  Auto-saved  : {clr(last_saved, C.YELLOW)}")
        print(f"  Profiles    : {clr(str(len(profiles)), C.CYAN)}")
        print()
        print(f"    {clr('1', C.CYAN)}.  Save current settings as a profile")
        print(f"    {clr('2', C.CYAN)}.  Load a profile")
        print(f"    {clr('3', C.CYAN)}.  Delete a profile")
        print(f"    {clr('4', C.CYAN)}.  View all profiles")
        print(f"    {clr('5', C.CYAN)}.  View activity log")
        print(f"    {clr('6', C.CYAN)}.  Clear activity log")
        print(f"    {clr('0', C.GRAY)}.  Back")
        print()
        choice = input(clr("  Choose [0-6]: ", C.WHITE)).strip()

        if choice == "1":
            _save_profile_action()
        elif choice == "2":
            _load_profile_action()
        elif choice == "3":
            _delete_profile_action()
        elif choice == "4":
            _view_profiles_action()
        elif choice == "5":
            _view_log_action()
        elif choice == "6":
            _clear_log_action()
        elif choice == "0":
            break
        else:
            print_err("Invalid option.")

def _save_profile_action():
    clear(); header()
    print(clr("  [ Save Profile ]\n", C.BOLD))
    print(f"  Current state will be saved:")
    print(f"    Interface : {clr(state['interface'] or '—', C.YELLOW)}")
    print(f"    Speed     : ↓{clr(fmt_speed(state['download_kbit']), C.WHITE)}  ↑{clr(fmt_speed(state['upload_kbit']), C.WHITE)}")
    print(f"    Blocked   : {clr(str(state['is_blocked']), C.RED if state['is_blocked'] else C.GRAY)}")
    print(f"    App limits: {clr(str(len(state['app_limits'])), C.MAGENTA)}")
    print()

    existing = list_profiles()
    if existing:
        print(clr("  Existing profiles: ", C.GRAY) + clr(", ".join(existing.keys()), C.CYAN))
        print()

    name = input(clr("  Profile name (e.g. 'work', 'gaming', 'night'): ", C.WHITE)).strip()
    if not name:
        print_info("Cancelled.")
        pause()
        return

    ok = save_named_profile(name)
    autosave()
    if ok:
        print_ok(f"Profile '{name}' saved.")
        log("PROFILE_SAVE", f"Saved profile '{name}'")
    else:
        print_err("Failed to save profile.")
    pause()

def _load_profile_action():
    clear(); header()
    print(clr("  [ Load Profile ]\n", C.BOLD))
    profiles = list_profiles()
    if not profiles:
        print_info("No profiles saved yet.")
        pause()
        return

    names = list(profiles.keys())
    for i, name in enumerate(names, 1):
        p        = profiles[name]
        dl       = fmt_speed(p.get("download_kbit"))
        ul       = fmt_speed(p.get("upload_kbit"))
        iface    = p.get("interface") or "—"
        saved_at = p.get("saved_at", "?")
        blocked  = p.get("is_blocked", False)
        status   = clr("BLOCKED", C.RED) if blocked else clr(f"↓{dl} ↑{ul}", C.YELLOW)
        print(f"    {clr(str(i), C.CYAN)}.  {clr(name, C.WHITE):<20} "
              f"iface:{clr(iface, C.YELLOW)}  {status}  {clr(saved_at, C.GRAY)}")

    print()
    idx = prompt_int(f"Pick profile [1-{len(names)}] (0 to cancel)", min_val=0, max_val=len(names))
    if not idx:
        pause()
        return

    name    = names[idx - 1]
    profile = profiles[name]

    # Apply interface from profile
    if profile.get("interface"):
        state["interface"] = profile["interface"]

    print()
    print(f"  Profile {clr(name, C.CYAN)} loaded. Applying settings...")
    print()

    # Re-apply limits if the profile had them
    iface = state["interface"] or get_wifi_interface()

    if profile.get("is_blocked"):
        print_info("Profile was blocked — re-applying block...")
        if is_linux() and check_tc_available():
            ok, _ = block_linux(iface)
            if ok:
                state["is_blocked"] = True
                state["is_limited"] = False
                print_ok("Block re-applied.")
        elif is_windows() and is_admin():
            ok, _ = block_windows(iface)
            if ok:
                state["is_blocked"] = True
                state["is_limited"] = False
                print_ok("Block re-applied via Firewall.")
    elif profile.get("is_limited") and profile.get("download_kbit"):
        dl = profile["download_kbit"]
        ul = profile.get("upload_kbit", dl)
        print_info(f"Profile had speed limit ↓{fmt_speed(dl)} ↑{fmt_speed(ul)} — re-applying...")
        if is_linux() and check_tc_available():
            ok, _ = apply_linux_limit(iface, dl, ul)
            if ok:
                state["download_kbit"] = dl
                state["upload_kbit"]   = ul
                state["is_limited"]    = True
                state["is_blocked"]    = False
                print_ok("Speed limit re-applied.")
        elif is_windows() and is_admin():
            ok, _ = apply_windows_limit(dl, ul)
            if ok:
                state["download_kbit"] = dl
                state["upload_kbit"]   = ul
                state["is_limited"]    = True
                state["is_blocked"]    = False
                print_ok("Speed limit re-applied.")
        elif is_mac():
            ok, _ = apply_mac_limit(iface, dl, ul)
            if ok:
                state["download_kbit"] = dl
                state["upload_kbit"]   = ul
                state["is_limited"]    = True
                state["is_blocked"]    = False
                print_ok("Speed limit re-applied.")
    else:
        state["is_limited"]    = False
        state["is_blocked"]    = False
        state["download_kbit"] = None
        state["upload_kbit"]   = None
        print_ok("Profile loaded (no limits in this profile).")

    log("PROFILE_LOAD", f"Loaded profile '{name}'")
    autosave()
    pause()

def _delete_profile_action():
    clear(); header()
    print(clr("  [ Delete Profile ]\n", C.BOLD))
    profiles = list_profiles()
    if not profiles:
        print_info("No profiles to delete.")
        pause()
        return
    print(clr("  Profiles: ", C.GRAY) + clr(", ".join(profiles.keys()), C.CYAN))
    print()
    name = input(clr("  Profile name to delete (Enter to cancel): ", C.WHITE)).strip()
    if not name:
        pause()
        return
    if delete_named_profile(name):
        print_ok(f"Profile '{name}' deleted.")
    else:
        print_err(f"Profile '{name}' not found.")
    pause()

def _view_profiles_action():
    clear(); header()
    print(clr("  [ All Profiles ]\n", C.BOLD))
    profiles = list_profiles()
    if not profiles:
        print_info("No profiles saved yet.")
        pause()
        return
    for name, p in profiles.items():
        dl      = fmt_speed(p.get("download_kbit"))
        ul      = fmt_speed(p.get("upload_kbit"))
        iface   = p.get("interface") or "—"
        saved   = p.get("saved_at", "?")
        blocked = p.get("is_blocked", False)
        n_apps  = len(p.get("app_limits", {}))
        status  = clr("BLOCKED", C.RED) if blocked else clr(f"↓{dl} ↑{ul}", C.YELLOW)
        print(f"  {clr(name, C.CYAN)}")
        print(f"    Saved    : {clr(saved, C.GRAY)}")
        print(f"    Interface: {clr(iface, C.YELLOW)}   Status: {status}")
        if n_apps:
            print(f"    App limits: {clr(str(n_apps), C.MAGENTA)}")
        print()
    pause()

def _view_log_action():
    clear(); header()
    print(clr("  [ Activity Log ]\n", C.BOLD))
    print(clr(f"  File: {LOG_FILE}\n", C.GRAY))

    if not os.path.exists(LOG_FILE):
        print_info("No log file yet. Actions will be logged as you use the app.")
        pause()
        return

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print_err(f"Could not read log: {e}")
        pause()
        return

    if not lines:
        print_info("Log is empty.")
        pause()
        return

    # Show last 40 lines, most recent at bottom
    display = lines[-40:]
    if len(lines) > 40:
        print(clr(f"  (Showing last 40 of {len(lines)} entries)\n", C.GRAY))

    for line in display:
        line = line.rstrip()
        # Colour-code by level
        if "[ERROR]" in line:
            print(clr(f"  {line}", C.RED))
        elif "[WARN ]" in line:
            print(clr(f"  {line}", C.YELLOW))
        elif "STARTUP" in line or "PROFILE" in line:
            print(clr(f"  {line}", C.CYAN))
        else:
            print(clr(f"  {line}", C.GRAY))

    print()
    print(clr(f"  Full log: {LOG_FILE}", C.GRAY))
    pause()

def _clear_log_action():
    clear(); header()
    print(clr("  [ Clear Activity Log ]\n", C.BOLD))
    confirm = input(clr("  Type 'yes' to permanently clear the log: ", C.WHITE)).strip().lower()
    if confirm != "yes":
        print_info("Cancelled.")
        pause()
        return
    try:
        open(LOG_FILE, "w").close()
        log("LOG_CLEARED", "Activity log was cleared by user")
        print_ok("Log cleared.")
    except Exception as e:
        print_err(f"Could not clear log: {e}")
    pause()

# ─── Menus ───────────────────────────────────────────────────────────────────────
def app_limits_menu():
    while True:
        clear(); header(); status_line()
        print(clr("  Per-App Speed Limits", C.BOLD))
        print()
        print(f"    {clr('1', C.CYAN)}.  Add / update limit for an app")
        print(f"    {clr('2', C.CYAN)}.  View & remove active app limits")
        print(f"    {clr('0', C.GRAY)}.  Back")
        print()
        choice = input(clr("  Choose [0-2]: ", C.WHITE)).strip()
        if   choice == "1": action_per_app_limit()
        elif choice == "2": action_view_app_limits()
        elif choice == "0": break
        else: print_err("Invalid option.")

def wifi_settings_menu():
    while True:
        clear(); header(); status_line()
        print(clr("  WiFi Settings", C.BOLD))
        print()
        print(f"    {clr('1', C.CYAN)}.  Set system-wide speed limit")
        print(f"    {clr('2', C.CYAN)}.  Per-app speed limits")
        print(f"    {clr('3', C.CYAN)}.  Block all WiFi traffic")
        print(f"    {clr('4', C.CYAN)}.  Remove all restrictions")
        print(f"    {clr('5', C.CYAN)}.  Change interface")
        print(f"    {clr('6', C.CYAN)}.  System / interface info")
        print(f"    {clr('0', C.GRAY)}.  Back")
        print()
        choice = input(clr("  Choose [0-6]: ", C.WHITE)).strip()
        if   choice == "1": action_set_speed()
        elif choice == "2": app_limits_menu()
        elif choice == "3": action_block_wifi()
        elif choice == "4": action_remove_limits()
        elif choice == "5": action_set_interface()
        elif choice == "6": action_show_info()
        elif choice == "0": break
        else: print_err("Invalid option.")

def main_menu():
    state["interface"] = get_wifi_interface()
    while True:
        clear(); header(); status_line()
        print(clr("  Main Menu", C.BOLD))
        print()
        print(f"    {clr('1', C.CYAN)}.  WiFi Settings")
        print(f"    {clr('2', C.CYAN)}.  Quick Block")
        print(f"    {clr('3', C.CYAN)}.  Quick Unblock / Remove All Limits")
        print(f"    {clr('4', C.CYAN)}.  Settings & Profiles")
        print(f"    {clr('0', C.GRAY)}.  Exit")
        print()
        choice = input(clr("  Enter a number: ", C.WHITE)).strip()
        if   choice == "1": wifi_settings_menu()
        elif choice == "2": action_block_wifi()
        elif choice == "3": action_remove_limits()
        elif choice == "4": action_settings_menu()
        elif choice == "0":
            log("SHUTDOWN", "App exited by user")
            autosave()
            clear()
            print(clr("\n  Goodbye! — PlofOS Group\n", C.CYAN))
            sys.exit(0)
        else:
            print_err("Invalid option.")
            time.sleep(0.8)

# ─── Entry Point ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_paths()

    if is_linux() and not is_admin():
        print(clr("\n  ⚠  For full functionality, run with sudo:", C.YELLOW))
        print(clr("     sudo python3 wifi_control.py\n", C.GRAY))
        input("  Press Enter to continue anyway... ")
    elif is_windows() and not is_admin():
        print(clr("\n  ⚠  For full functionality, run as Administrator.", C.YELLOW))
        print(clr("     Right-click terminal → Run as Administrator\n", C.GRAY))
        input("  Press Enter to continue anyway... ")

    log("STARTUP", f"App started on {OS} | admin={is_admin()}")
    restored = restore_last_session()
    if restored:
        print(clr("  ℹ  Last session restored (interface preference loaded).", C.GRAY))
        time.sleep(1)

    try:
        main_menu()
    except KeyboardInterrupt:
        log("SHUTDOWN", "App interrupted (Ctrl+C)")
        autosave()
        print(clr("\n\n  Exiting. Goodbye! — PlofOS Group\n", C.CYAN))
        sys.exit(0)
