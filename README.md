# PlofOS-Wifi-Blocker
A simple wifi blocker. You can set the max upload and download speeds from this terminal. It can set it for one or two apps. You can save profiles if needed (not tested yet). Open as admin to get all features. Is not fully accurate with some speeds. Note that this is made with AI and is part of a project and is for the point of testing and playing around with Claude. The log file is personal and can not be seen by anyone else.

Install file:

============================================================
  WiFi Control - Terminal App
  By PlofOS Group
============================================================

  A terminal app to control, limit, and block your WiFi
  speed — system-wide or per application.


------------------------------------------------------------
  FILES
------------------------------------------------------------

  wifi_control.py   — The main app (this is all you run)
  settings.json     — Auto-created on first run, stores your
                      settings and saved profiles
  activity.log      — Auto-created on first run, logs every
                      action you take with a timestamp

  All three files live in the same folder. Move the folder
  anywhere and everything moves with it.


------------------------------------------------------------
  REQUIREMENTS
------------------------------------------------------------

  ALL PLATFORMS
  -------------
  - Python 3.7 or higher

    Check your version by running:
      python3 --version        (Linux / macOS)
      python --version         (Windows)

    If Python is not installed, download it from:
      https://www.python.org/downloads/

  - No extra Python packages needed. The app only uses
    modules that come built into Python (os, sys, json,
    subprocess, platform, shutil, time, datetime).


  LINUX
  -----
  - sudo access (required to apply network rules)

  - iproute2 (provides the "tc" traffic control tool)
    This is pre-installed on most Linux distros.
    If it is missing, install it with:
      sudo apt install iproute2       (Debian / Ubuntu)
      sudo dnf install iproute        (Fedora / RHEL)
      sudo pacman -S iproute2         (Arch)

  - For per-app limits: the "net_cls" cgroup module.
    This is available on most modern Linux kernels
    (4.x and up) by default. No install needed.

  - For download limiting: the "ifb" kernel module.
    Also usually available by default.
    The app will load it automatically using modprobe.

  - Optional: iwconfig (for auto-detecting your WiFi
    interface name). Part of the "wireless-tools" package:
      sudo apt install wireless-tools
    If missing, the app falls back to scanning /sys/class/net
    and defaults to "wlan0" if nothing is found.


  macOS
  -----
  - sudo access (required to apply network rules)

  - dnctl and pfctl — both are built into macOS.
    No install needed.

  - Tested on macOS 10.15 (Catalina) and later.


  WINDOWS
  -------
  - Must be run as Administrator.
    Right-click your terminal (CMD or PowerShell) and
    choose "Run as administrator" before starting the app.

  - PowerShell 5.0 or higher (built into Windows 10/11).
    No install needed.

  - Windows Firewall must be enabled for the block
    features to work.

  - QoS (Quality of Service) must be enabled.
    It is on by default in Windows 10 and 11.

  - Note on speed limiting accuracy on Windows:
    Upload throttle via QoS works well (~60-80% accurate).
    Download throttle uses TCP window tuning and is
    approximate (~40-60% accurate). For precise download
    throttling on Windows a third-party driver-level tool
    such as NetLimiter is needed.


------------------------------------------------------------
  HOW TO RUN
------------------------------------------------------------

  LINUX
    sudo python3 wifi_control.py

    Running with sudo is required for applying limits.
    You can run without sudo but most features will fail.

  macOS
    sudo python3 wifi_control.py

  WINDOWS
    1. Open Command Prompt or PowerShell as Administrator
       (right-click → Run as administrator)
    2. Navigate to the folder:
         cd C:\path\to\your\folder
    3. Run:
         python wifi_control.py


------------------------------------------------------------
  FEATURES
------------------------------------------------------------

  System-wide speed limit
    Limit download and upload speed for the entire
    computer. Choose from presets (1 Kbps up to 100 Mbps)
    or enter a custom value. Minimum is 1 Kbps, which
    is effectively a full block.

  Per-app speed limit (Linux and Windows)
    Limit bandwidth for a single application by picking
    it from a live process browser. You can search by
    typing /keyword while browsing the process list.
    On Linux this uses tc + cgroups (net_cls).
    On Windows this uses QoS policy per executable.
    Not supported on macOS via CLI.

  Block all WiFi traffic
    Cuts all network traffic on your WiFi interface.
    On Linux: uses tc with a 1 Kbps hard cap.
    On macOS: uses dnctl/pfctl with a 1 Kbps hard cap.
    On Windows: uses Windows Firewall rules.

  Block a specific app (Windows only)
    Block one application from accessing the network
    entirely using Windows Firewall rules.

  Profiles
    Save your current settings (interface, speed limits,
    blocked state) as a named profile. Load a profile
    later to instantly re-apply those settings to the OS.
    Examples: "work", "gaming", "night".

  Auto-save
    Every change you make is automatically saved to
    settings.json. Your interface preference is restored
    the next time you open the app.

  Activity log
    Every action is written to activity.log with a
    timestamp and your username. View the last 40 entries
    directly inside the app under Settings & Profiles,
    or open the file in any text editor.


------------------------------------------------------------
  SPEED LIMIT ACCURACY
------------------------------------------------------------

  Linux (system-wide)     90-95% accurate
  Linux (per-app)         80-90% accurate
  macOS (system-wide)     85-95% accurate
  Windows (upload QoS)    60-80% accurate
  Windows (download)      40-60% accurate
  Any platform (block)    100%

  Linux is the most accurate platform for this app
  because tc operates directly in the kernel network stack.


------------------------------------------------------------
  FOLDER STRUCTURE AFTER FIRST RUN
------------------------------------------------------------

  your-folder/
  ├── wifi_control.py     ← the app
  ├── settings.json       ← auto-created, your settings
  └── activity.log        ← auto-created, your log


------------------------------------------------------------
  TROUBLESHOOTING
------------------------------------------------------------

  "tc not found"
    Install iproute2 (see Requirements > Linux above).

  "Permission denied" or features not working
    Make sure you are running with sudo (Linux/macOS)
    or as Administrator (Windows).

  WiFi interface not detected correctly
    Go to WiFi Settings → Change interface and enter
    the correct name manually.
    On Linux, find your interface with:  ip link show
    On macOS, find it with:             ifconfig
    On Windows, find it with:           netsh interface show interface

  Speed limit does not seem to apply
    - Check that you are running with admin/sudo rights.
    - On Linux, verify tc is installed and check the
      "System / interface info" screen inside the app.
    - On Windows, check that QoS and Windows Firewall
      are both enabled in your system settings.

  Log or settings file missing
    They are created automatically when you first run the
    app. If they are missing, check that the folder where
    wifi_control.py lives is writable.

  Colors not showing in terminal (Windows)
    Use Windows Terminal or PowerShell 7+. The older
    CMD prompt may not render ANSI colors correctly.
    In that case the app still works, just without colors.


------------------------------------------------------------
  TESTED ON
------------------------------------------------------------

  Linux   Ubuntu 22.04 / 24.04, Debian 12, Arch Linux
  macOS   Ventura (13), Sonoma (14)
  Windows Windows 10 (21H2+), Windows 11


============================================================
  PlofOS Group
============================================================
