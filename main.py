#!/usr/bin/python3
"""
mini-msf.py — Simple modular CLI framework in Python (safe, educational)
Responsive CLI, no pagination, one-line startup animation.
"""

import os, sys, shlex, importlib.util, re, platform, time, random, itertools, threading, shutil, textwrap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# Paths
BASE_DIR = Path(__file__).parent
MODULE_DIR, EXAMPLES_DIR, BANNER_DIR = BASE_DIR/"modules", BASE_DIR/"examples", BASE_DIR/"banner"
METADATA_READ_LINES = 120
_loaded_banners = []

# ========== Banner Loader ==========
def load_banners_from_folder():
    global _loaded_banners
    _loaded_banners = []
    BANNER_DIR.mkdir(parents=True, exist_ok=True)
    for p in sorted(BANNER_DIR.glob("*.txt")):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore").rstrip()
            if text:
                _loaded_banners.append(text + "\n\n")
        except Exception:
            pass
    if not _loaded_banners:
        _loaded_banners = ["Lazy Framework\n"]

def colorize_banner(text):
    colors = ['\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m']
    color = random.choice(colors)
    reset = '\033[0m'
    return f"{color}{text}{reset}"

def get_random_banner():
    if not _loaded_banners:
        load_banners_from_folder()

    banner = random.choice(_loaded_banners).rstrip("\n")
    try:
        cols = shutil.get_terminal_size(fallback=(80, 24)).columns
    except Exception:
        cols = 80

    lines = banner.splitlines()
    max_len = max((len(line) for line in lines), default=0)
    scale = min(1.0, cols / max_len) if max_len > 0 else 1.0

    if scale < 1.0:
        # Jika terminal kecil, pangkas tiap baris agar pas
        new_lines = [line[:int(cols)] for line in lines]
    else:
        # Jika terminal lebar, center tiap baris
        new_lines = [line.center(cols) for line in lines]

    return colorize_banner("\n".join(new_lines)) + "\n\n"

# ========== One-line Animation ==========
class SingleLineMarquee:
    def __init__(self, text="Starting the Metasploit Framework Console...",
                 text_speed: float = 6.06, spinner_speed: float = 0.06):
        self.text, self.spinner = text, itertools.cycle(['|', '/', '-', '\\'])
        self.alt_text = ''.join(c.lower() if i % 2 == 0 else c.upper() for i, c in enumerate(text))
        self.text_speed, self.spinner_speed = max(0.01, text_speed), max(0.01, spinner_speed)
        self._stop, self._pos, self._thread = threading.Event(), 0, None

    def _compose(self, pos, spin): 
        return f"{self.alt_text[:pos] + self.text[pos:]} [{spin}]"

    def _run(self):
        L = len(self.text)
        last_time = time.time()
        while not self._stop.is_set():
            spin = next(self.spinner)
            now = time.time()
            if self._pos < L and (now - last_time) >= self.text_speed:
                self._pos += 1
                last_time = now
            sys.stdout.write('\r' + self._compose(self._pos, spin))
            sys.stdout.flush()
            if self._pos >= L:
                break
            time.sleep(self.spinner_speed)
        sys.stdout.write('\r' + self.text + '\n')
        sys.stdout.flush()

    def start(self):
        if not (self._thread and self._thread.is_alive()):
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
    def wait(self): 
        if self._thread: self._thread.join()
    def stop(self): 
        self._stop.set(); 
        if self._thread: self._thread.join()

# ========== Core Framework ==========
@dataclass
class ModuleInstance:
    name: str
    module: Any
    options: Dict[str, Any] = field(default_factory=dict)
    def set_option(self, key, value): 
        if key not in self.module.OPTIONS: raise KeyError(f"Unknown option '{key}'")
        self.options[key] = value
    def get_options(self): 
        return {k: {"value": self.options.get(k, v.get("default")), **v} for k, v in self.module.OPTIONS.items()}
    def run(self, session): return self.module.run(session, self.options)

class Search:
    def __init__(self, modules, metadata): self.modules, self.metadata = modules, metadata
    def search_modules(self, keyword):
        keyword = keyword.lower(); results = []
        for key, meta in self.metadata.items():
            if keyword in key.lower() or keyword in meta.get("description","").lower():
                results.append((key, meta.get("description","(no description)")))
        return results

class LazyFramework:
    def __init__(self):
        self.modules, self.metadata = {}, {}
        self.loaded_module: Optional[ModuleInstance] = None
        self.session = {"user": os.getenv("USER", "unknown")}
        self.scan_modules()

    def _ensure_dirs(self):
        for d in (MODULE_DIR, EXAMPLES_DIR, BANNER_DIR):
            d.mkdir(parents=True, exist_ok=True)

    def scan_modules(self):
        self._ensure_dirs()
        self.modules.clear(); self.metadata.clear()
        for folder, prefix in ((MODULE_DIR, "modules"), (EXAMPLES_DIR, "examples")):
            for p in folder.rglob("*.py"):
                rel = str(p.relative_to(folder)).replace(os.sep, "/")
                key = f"{prefix}/{rel}"
                self.modules[key] = p
                self.metadata[key] = self._read_meta(p)

    def _read_meta(self, path):
        data = {"description": "", "options": []}
        try:
            text = "".join(path.open("r", encoding="utf-8", errors="ignore").readlines()[:METADATA_READ_LINES])
            if (m := re.search(r"['\"]description['\"]\s*:\s*['\"]([^'\"]+)['\"]", text)): 
                data["description"] = m.group(1)
            if (mo := re.search(r"OPTIONS\s*=\s*{([^}]*)}", text, re.DOTALL)):
                data["options"] = re.findall(r"['\"]([A-Za-z0-9_]+)['\"]\s*:", mo.group(1))
        except: pass
        return data

    def import_module(self, key):
        path = self.modules[key]
        spec = importlib.util.spec_from_file_location(key.replace('/', '_'), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    # -------- Commands --------
    def cmd_help(self, args):
        """Responsive help (no pagination, fully adaptive)."""
        commands = [
            ("show modules", "Show available modules"),
            ("use <module>", "Load a module by name"),
            ("options", "Show options for current module"),
            ("set <option> <value>", "Set module option"),
            ("run", "Run current module"),
            ("back", "Unload module"),
            ("search <keyword>", "Search modules"),
            ("scan", "Rescan modules"),
            ("banner reload|list", "Reload/list banner files"),
            ("cd <dir>", "Change working directory"),
            ("ls", "List current directory"),
            ("clear", "Clear terminal screen"),
            ("exit / quit", "Exit the program"),
        ]
        try:
            size = shutil.get_terminal_size(fallback=(80, 24))
            term_width = size.columns
        except: term_width = 80

        print("\n" + "Core Commands" .center( term_width))
        print("-" * term_width)
        cmd_col = max(18, int(term_width * 0.35))
        desc_col = term_width - cmd_col - 2
        wrapper = textwrap.TextWrapper(width=desc_col)

        for cmd, desc in commands:
            wrapped = wrapper.wrap(desc)
            print(f"{cmd.ljust(cmd_col)}  {wrapped[0]}")
            for extra in wrapped[1:]:
                print(" " * (cmd_col + 2) + extra)
        print()

    def cmd_show(self, args):
        print("Available modules:")
        for k, v in sorted(self.metadata.items()):
            print(f"  {k:40} {v.get('description','(no description)')}")

    def cmd_use(self, args):
        if not args: return print("Usage: use <module>")
        key = args[0]
        if not key.startswith(("modules/", "examples/")):
            for prefix in ("modules", "examples"):
                cand = f"{prefix}/{key}"
                if cand in self.modules:
                    key = cand; break
        try:
            mod = self.import_module(key)
            inst = ModuleInstance(key, mod)
            for k, meta in mod.OPTIONS.items():
                if "default" in meta: inst.options[k] = meta["default"]
            self.loaded_module = inst
            print(f"Loaded module {key}")
        except Exception as e:
            print("Load error:", e)

    def cmd_options(self, args):
        if not self.loaded_module: return print("No module loaded.")
        print(f"Options for {self.loaded_module.name}:")
        print("  Name         Current    Required    Description")
        for k, v in self.loaded_module.get_options().items():
            print(f"  {k:12} {v['value']:10} {'yes' if v.get('required') else 'no':10} {v.get('description','')}")

    def cmd_set(self, args):
        if not self.loaded_module: return print("No module loaded.")
        if len(args)<2: return print("Usage: set <option> <value>")
        opt, val = args[0], " ".join(args[1:])
        try: self.loaded_module.set_option(opt, val); print(f"{opt} => {val}")
        except Exception as e: print(e)

    def cmd_run(self, args):
        if not self.loaded_module: return print("No module loaded.")
        try: self.loaded_module.run(self.session)
        except Exception as e: print("Run error:", e)

    def cmd_back(self, args):
        if self.loaded_module: print(f"Unloaded {self.loaded_module.name}"); self.loaded_module = None
        else: print("No module loaded.")

    def cmd_scan(self, args): self.scan_modules(); print(f"Scanned {len(self.modules)} modules.")
    def cmd_search(self, args):
        if not args: return print("Usage: search <keyword>")
        res = Search(self.modules, self.metadata).search_modules(args[0])
        for r in res: print(f"{r[0]} - {r[1]}")
    def cmd_banner(self, args):
        if not args: return print("Usage: banner reload|list")
        if args[0]=="reload": load_banners_from_folder(); print(get_random_banner())
        elif args[0]=="list": [print(" ",f.name) for f in BANNER_DIR.glob("*.txt")]
    def cmd_cd(self, args):
        if not args: return
        try: os.chdir(args[0]); print("Changed Directory to:", os.getcwd())
        except Exception as e: print("Error:", e)
    def cmd_ls(self, args):
        try: [print("]",f) for f in os.listdir()]
        except Exception as e: print("Error:", e)
    def cmd_clear(self, args): os.system("cls" if platform.system().lower()=="windows" else "clear")

    def repl(self):
        print("Lazy Framework type 'help' for commands")
        print(get_random_banner(), end="")
        while True:
            try:
                prompt = f"lzf(\033[41m\033[97m{self.loaded_module.name}\033[0m)> " if self.loaded_module else "lzf> "
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print(); break
            if not line.strip(): continue
            parts = shlex.split(line); cmd, args = parts[0], parts[1:]
            if cmd in ("exit","quit"): break
            getattr(self, f"cmd_{cmd}", lambda a: print("Unknown command"))(args)

# ========== Example Modules ==========
EXAMPLES = {
    "recon/sysinfo.py": '''import platform
MODULE_INFO={"name":"recon/sysinfo","description":"Print local system info"}
OPTIONS={"VERBOSE":{"required":False,"default":"true","description":"Verbose output"}}
def run(session, options):
    print("System info:");print("  User:",session.get("user"));print("  Platform:",platform.platform())''',
    "aux/echo.py": '''MODULE_INFO={"name":"aux/echo","description":"Echo string back (safe)"}
OPTIONS={"MSG":{"required":True,"default":"","description":"Message to echo"}}
def run(session,options):print("ECHO:",options.get("MSG",""))'''
}
def ensure_examples():
    EXAMPLES_DIR.mkdir(exist_ok=True, parents=True)
    for rel, content in EXAMPLES.items():
        p = EXAMPLES_DIR/rel; p.parent.mkdir(exist_ok=True, parents=True)
        if not p.exists(): p.write_text(content)

# ========== Main ==========
def main():
    anim = SingleLineMarquee("Starting the Metasploit Framework Console...", 0.60, 0.06)
    anim.start(); anim.wait()
    time.sleep(6)
    os.system("cls" if platform.system().lower()=="windows" else "clear")
    ensure_examples(); load_banners_from_folder()
    LazyFramework().repl()
    print("Goodbye.")

if __name__ == "__main__":
    main()
