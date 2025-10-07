#!/usr/bin/python3
"""
mini-msf.py — Simple modular CLI framework in Python (safe, educational)

Features:
- Scan modules from modules/ and examples/
- Lazy metadata read (quick show modules)
- Supports aliases for 'use <module>'
- Banners from banner/*.txt (random, reload, list)
- Command set for modules with options (set, run, back)
- Example modules auto-created in examples/
"""

import os
import sys
import shlex
import importlib.util
import re
import platform
import time
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import itertools
import threading

class SingleLineMarquee:
    """Animasi satu baris: teks 'Starting...' muncul progresif huruf kecil-besar & spinner"""
    def __init__(self, text="Starting the Metasploit Framework Console...", fps=10):
        self.text = text
        self.alt_text = ''.join(
            c.lower() if i % 2 == 0 else c.upper() for i, c in enumerate(text)
        )
        self.spinner = itertools.cycle(['|', '/', '-', '\\'])
        self.text_speed = 1      # kecepatan huruf muncul
        self.spinner_speed = 0.04  # kecepatan rotasi spinner
        self._stop = threading.Event()
        self._pos = 0
        self._thread = None

    def _compose_line(self, pos, spin_char):
        left = self.alt_text[:pos]
        right = self.text[pos:]
        return f"{left + right} [{spin_char}]"

    def _run(self):
        L = len(self.text)
        last_update = time.time()
   
        while not self._stop.is_set():
            spin = next(self.spinner)
            now = time.time()

            # tampilkan huruf berikutnya tiap text_speed
            if now - last_update >= self.text_speed and self._pos < L:
                self._pos += 1
                last_update = now

            # tulis ulang 1 baris
            sys.stdout.write('\r' + self._compose_line(self._pos, spin))
            sys.stdout.flush()

            if self._pos >= L:
                break

            time.sleep(self.spinner_speed)
       
        # tampilkan teks akhir
        sys.stdout.write(f'\r{self.text}\n')
        sys.stdout.flush()

    def start(self):
        if not self._thread or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def wait(self):
        if self._thread:
            self._thread.join()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()

# --------- configurable paths ----------
BASE_DIR = Path(__file__).parent
MODULE_DIR = BASE_DIR / "modules"
EXAMPLES_DIR = BASE_DIR / "examples"
BANNER_DIR = BASE_DIR / "banner"
METADATA_READ_LINES = 120  # how many lines to scan for metadata

# in-memory loaded banners
_loaded_banners = []

def load_banners_from_folder():
    """Load all .txt files from BANNER_DIR into _loaded_banners (fallback minimal)."""
    global _loaded_banners
    _loaded_banners = []
    if not BANNER_DIR.exists() or not BANNER_DIR.is_dir():
       print(f"Error: {BANNER_DIR} folder does not exists.")
       return
    try:
        for p in sorted(BANNER_DIR.glob("*.txt")):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore").rstrip()
                if text:
                    _loaded_banners.append(text + "\n\n")
            except Exception:
                pass
    except Exception:
        pass
    if not _loaded_banners:
        _loaded_banners = ["Lazy Framework\n"]

    



def get_random_banner():
    if not _loaded_banners:
        load_banners_from_folder()
    return random.choice(_loaded_banners)

@dataclass
class ModuleInstance:
    name: str
    module: Any
    options: Dict[str, Any] = field(default_factory=dict)

    def set_option(self, key: str, value: Any):
        if key in self.module.OPTIONS:
            self.options[key] = value
        else:
            raise KeyError(f"Unknown option '{key}'")

    def get_options(self):
        opts = {}
        for k, meta in self.module.OPTIONS.items():
            opts[k] = {"value": self.options.get(k, meta.get("default")), **meta}
        return opts

    def run(self, session):
        return self.module.run(session, self.options)

class Search:
    def __init__(self, modules: Dict[str, Path], metadata: Dict[str, Dict[str, Any]]):
        self.modules = modules
        self.metadata = metadata
    def search_modules(self, keyword: str):
        keyword = keyword.lower()
        results = []
        if '/' in keyword or ':' in keyword:
            parts = re.split(r'[/]', keyword)
            for key, meta in self.metadata.items():
                if parts[0] in key.lower() and (parts[1] in meta.get("description", "").lower() if len(parts) > 1 else True):
                   results.append((key, meta.get('description', "(no description)")))
        else:
            for key, meta in self.metadata.items():
                name = key.lower()
                description = meta.get("description", "").lower()
                if keyword in name or keyword in description:
                    results.append((key, meta.get('description', "(no description)")))
        return results           

class LazyFramework:
    def __init__(self):
        self.modules: Dict[str, Path] = {}  # key -> path
        self.metadata: Dict[str, Dict[str, Any]] = {}  # key -> metadata
        self.loaded_module: Optional[ModuleInstance] = None
        self.session = {"user": os.getlogin() if hasattr(os, "getlogin") else "unknown"}
        self.scan_modules()

    def check_folders_exist(self):
        """Check if necessary directories exist, and print an error message if any are missing."""
        if not MODULE_DIR.exists() or not MODULE_DIR.is_dir():
            print(f"Error: {MODULE_DIR} folder does not exist.")
        if not EXAMPLES_DIR.exists() or not EXAMPLES_DIR.is_dir():
            print(f"Error: {EXAMPLES_DIR} folder does not exist.")
        if not BANNER_DIR.exists() or not BANNER_DIR.is_dir():
            print(f"Error: {BANNER_DIR} folder does not exist.")

    def scan_modules(self):
        """Scan module files in both MODULE_DIR and EXAMPLES_DIR and read lightweight metadata without importing."""
        self.check_folders_exist()  # Ensure necessary folders exist

        if not MODULE_DIR.exists() or not MODULE_DIR.is_dir():
            print("Skipping module scan because the 'modules/' folder doesn't exist.")
            return
        if not EXAMPLES_DIR.exists() or not EXAMPLES_DIR.is_dir():
            print("Skipping example module scan because the 'examples/' folder doesn't exist.")
            return

        self.modules = {}
        self.metadata = {}

        for folder, prefix in ((MODULE_DIR, "modules"), (EXAMPLES_DIR, "examples")):
            for p in folder.rglob("*.py"):
                rel = str(p.relative_to(folder)).replace(os.sep, "/")
                key = f"{prefix}/{rel}"
                self.modules[key] = p
                self.metadata[key] = self._read_metadata_from_file(p)

    def _read_metadata_from_file(self, path: Path) -> Dict[str, Any]:
        data = {"description": "", "options": []}
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                lines = []
                for _ in range(METADATA_READ_LINES):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line)
                header_text = "".join(lines)

            # find MODULE_INFO = { ... }
            m = re.search(r"MODULE_INFO\s*=\s*{([^}]*)}", header_text, re.DOTALL)
            if m:
                inside = m.group(1)
                mdesc = re.search(r"['\"]description['\"]\s*:\s*['\"]([^'\"]+)['\"]", inside)
                if mdesc:
                    data["description"] = mdesc.group(1).strip()

            # OPTIONS keys
            mo = re.search(r"OPTIONS\s*=\s*{([^}]*)}", header_text, re.DOTALL)
            if mo:
                inside_o = mo.group(1)
                keys = re.findall(r"['\"]([A-Za-z0-9_]+)['\"]\s*:", inside_o)
                data["options"] = keys

            # fallback: module-level docstring first line
            if not data["description"]:
                mdoc = re.search(r'^(?:\s)*(?:"""|\'\'\')(.+?)(?:"""|\'\'\')', header_text, re.DOTALL | re.MULTILINE)
                if mdoc:
                    first_line = mdoc.group(1).strip().splitlines()[0].strip()
                    data["description"] = first_line
        except Exception:
            pass
        return data

    def import_module(self, key: str):
        if key not in self.modules:
            raise KeyError("Module not found")
        path = self.modules[key]
        spec = importlib.util.spec_from_file_location(f"plugin_{key.replace('/', '_')}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # validate API
        if not hasattr(mod, "MODULE_INFO") or not hasattr(mod, "OPTIONS") or not hasattr(mod, "run"):
            raise RuntimeError("Invalid module API. require MODULE_INFO, OPTIONS, run()")
        return mod

    # ------- REPL commands ----------
    def cmd_show(self, args):
        # allow: show modules [filter]
        if len(args) == 0 or args[0] == "modules":
            filt = args[1] if len(args) > 1 else None
            print("Available modules:")
            keys = sorted(self.modules.keys())
            if not keys:
                print("No modules found.")
            else:
                if filt:
                    keys = [k for k in keys if filt in k]
                for k in keys:
                    meta = self.metadata.get(k, {})
                    desc = meta.get("description") or "(no description)"
                    print(f"  {k:30} {desc}")
        else:
            print("Usage: show modules [filter]")

    def _resolve_alias(self, key: str) -> Optional[str]:
        """If user passes 'recon/sysinfo' (no prefix), try 'modules/...' then 'examples/...'"""
        if key in self.modules:
            return key
        # try with prefixes
        for prefix in ("modules", "examples"):
            cand = f"{prefix}/{key}"
            if cand in self.modules:
                return cand
        return None

    def cmd_use(self, args):
        if not args:
            print("Usage: use <module>")
            return
        key = args[0]
        # support alias resolution
        if not (key.startswith("modules/") or key.startswith("examples/")):
            resolved = self._resolve_alias(key)
            if resolved:
                key = resolved
        try:
            mod = self.import_module(key)
        except Exception as e:
            print(f"Error loading module: {e}")
            return
        inst = ModuleInstance(name=key, module=mod)
        # initialize defaults
        for k, meta in mod.OPTIONS.items():
            if "default" in meta:
                inst.options[k] = meta["default"]
        self.loaded_module = inst
        print(f"Loaded module {key}")

    def cmd_options(self, args):
        if not self.loaded_module:
            print("No module loaded. use <module> to load.")
            return
        print(f"Options for {self.loaded_module.name}:")
        opts = self.loaded_module.get_options()
        print("  Name         Current    Required    Description")
        for k, v in opts.items():
            cur = v["value"]
            req = "yes" if v.get("required") else "no"
            desc = v.get("description", "")
            print(f"  {k:12} {str(cur):10} {req:10} {desc}")

    def cmd_set(self, args):
        if not self.loaded_module:
            print("No module loaded.")
            return
        if len(args) < 2:
            print("Usage: set <option> <value>")
            return
        opt = args[0]
        val = " ".join(args[1:])
        try:
            self.loaded_module.set_option(opt, val)
            print(f"{opt} => {val}")
        except KeyError as e:
            print(e)

    def cmd_run(self, args):
        if not self.loaded_module:
            print("No module loaded.")
            return
        # check required options
        missing = []
        for k, meta in self.loaded_module.module.OPTIONS.items():
            if meta.get("required") and self.loaded_module.options.get(k) in (None, ""):
                missing.append(k)
        if missing:
            print("Missing required options:", ", ".join(missing))
            return
        try:
            self.loaded_module.run(self.session)
        except Exception as e:
            print("Module execution error:", e)

    def cmd_back(self, args):
        if self.loaded_module:
            print(f"Unload module {self.loaded_module.name}")
            self.loaded_module = None
        else:
            print("No module loaded.")

    def cmd_search(self, args):
        if not args:
           print("Usage: search <keyword>")
           return
        keyword = args[0].lower()
        searcher = Search(self.modules, self.metadata)
        results = searcher.search_modules(keyword)
        if not results:
           print(f"No Module")
        else:
           for results in results:
               print(f"{results[0]} - {results[1]}")

    def cmd_scan(self, args):
        self.scan_modules()
        print(f"Scanned {len(self.modules)} modules.")

    def cmd_banner(self, args):
        """banner reload  -- rescan banner/ folder
           banner list    -- show available banner files (filenames)
        """
        if not args:
            print("Usage: banner reload|list")
            return
        sub = args[0]
        if sub == "reload":
            load_banners_from_folder()
            print(f"Loaded {len(_loaded_banners)} banners (from {BANNER_DIR}).")
            print(get_random_banner())
        elif sub == "list":
            try:
                files = sorted(BANNER_DIR.glob("*.txt"))
                if not files:
                    print("No banner files found.")
                else:
                    for f in files:
                        print(" ", f.name)
            except Exception as e:
                print("Error listing banners:", e)
        else:
            print("Usage: banner reload|list")

    def cmd_cd(self, args):
        if not args:
           return
        new_dir = args[0]
        try:
           os.chdir(new_dir)
           print(f"Changed Directory to: {os.getcwd()}")
        except FileNotFoundError:
           print(f"Error: The Directory '{new_dir}' does not exist.")
        except PermissionError:
           print(f"Erro:You do not have permission to access '{new_dir}'.")
        except Exception as e:
           print(f"Error: {str(e)}")

    def cmd_ls(self, args):
        try:
            files = os.listdir()
            if not files:
               print(f"Tidak ada directory ini")
            else:

               print(f"Daftar File")
               for file in files:
                   print(f"\033[31m] {file} ")
        except Exception as e:
            print(f"Error saat mencoba membaca direktori: {str(e)}")

    def cmd_help(self):

    # Menghitung lebar terminal
       terminal_width = 40  # Misalnya, 80 karakter adalah lebar terminal
       terminal2_width = 80
       terminal3_width = 20
      # Header dengan desain ASCII art dan informasi tambahan
       #print("=" * terminal2_width)  # Pembatas
       print("\n")
    # Menampilkan judul dan garis pembatas
       print("Core Commands".center(terminal3_width))
       print("--------------".center(terminal3_width))  # Pembatas horizontal
    # Menampilkan tabel perintah dan deskripsi
       print("=" * terminal2_width)  # Pembatas
       print(f"{'Command':<30} {'Description'}".center(terminal3_width))
       print("=" * terminal2_width)  # Garis pemisah tabel

    # Menggunakan commands baru yang sudah diberikan
       commands = [
         ("show modules [filter]", "Show available modules, optionally filtered by 'filter.'"),
         ("use <module>", "Load a module by name (e.g., 'use modules/recon/sysinfo')."),
         ("options", "Show options for the current module."),
         ("set <option> <value>", "Set the value for an option of the loaded module."),
         ("run", "Run the current loaded module with set options."),
         ("back", "Unload the current module."),
         ("scan", "Scan for modules in 'modules/' and 'examples.'"),
         ("cd", "Change Directory.'"),
         ("banner reload", "Reload banner files from the 'banner/' folder."),
         ("banner list", "List available banner files."),
         ("exit / quit", "Exit the program.")
    ]

    # Menampilkan setiap perintah dan deskripsi
       for cmd, desc in commands:
         print(f"{cmd:<30} {desc}".center(terminal_width))
        
    def terminal_clear(self):

         system_platform = platform.system().lower()
         if system_platform == "windows":
            os.system("cls")
         else:
            os.system("clear")

    def repl(self):
        print("lzf (safe) — type 'help' for commands")
        print(get_random_banner(), end="")
        while True:
            try:
               if  self.loaded_module and 'modules' in self.loaded_module.name:
                   # print a random banner each prompt iteration
                   prompt = f"lzf(\033[41m\033[97m{self.loaded_module.name}\033[0m)> " if self.loaded_module else "lzf> "
               else:
                   prompt = "lzf> "
               line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line.strip():
                continue
            parts = shlex.split(line)
            cmd = parts[0]
            args = parts[1:]
            if cmd in ("exit", "quit"):
                break
            elif cmd == "help":
                 self.cmd_help()
            elif cmd == "show":
                self.cmd_show(args)
            elif cmd == "use":
                self.cmd_use(args)
            elif cmd == "options":
                self.cmd_options(args)
            elif cmd == "set":
                self.cmd_set(args)
            elif cmd == "run":
                self.cmd_run(args)
            elif cmd == "back":
                self.cmd_back(args)
            elif cmd == "scan":
                self.cmd_scan(args)
            elif cmd == "banner":
                self.cmd_banner(args)
            elif cmd == "search":
                self.cmd_search(args)
            elif cmd == "cd":
                self.cmd_cd(args)
            elif cmd == "ls":
                self.cmd_ls(args)
            elif cmd == "clear":
                self.terminal_clear()
            else:
                print("Unknown command. type 'help'")

# --------- create example modules in examples/ if missing (kept separate) ----------
EXAMPLE_MODULES = {
    "recon/sysinfo.py": '''"""
recon/sysinfo — safe module: print local system info
"""
import platform
MODULE_INFO = {"name": "recon/sysinfo", "description": "Print local system information"}
OPTIONS = {
    "VERBOSE": {"required": False, "default": "true", "description": "Verbose output"},
}

def run(session, options):
    print("System info:")
    print("  User:", session.get("user"))
    print("  Platform:", platform.platform())
    print("  Machine:", platform.machine())
    print("  Processor:", platform.processor())
    print("  Python:", platform.python_version())
''',
    "aux/echo.py": '''"""
aux/echo — safe module: echo input string
"""
MODULE_INFO = {"name": "aux/echo", "description": "Echo string back (safe)"}
OPTIONS = {
    "MSG": {"required": True, "default": "", "description": "Message to echo"},
}

def run(session, options):
    msg = options.get("MSG", "")
    print("ECHO:", msg)
''',
    "aux/netinfo.py": '''"""
aux/netinfo — safe module: shows local network interfaces & IPs (read-only)
"""
import socket
try:
    import psutil
except Exception:
    psutil = None
MODULE_INFO = {"name": "aux/netinfo", "description": "Show local network interfaces (read-only)"}
OPTIONS = {}

def run(session, options):
    try:
        if psutil:
            ifaces = psutil.net_if_addrs()
            for ifname, addrs in ifaces.items():
                print(f"{ifname}:")
                for a in addrs:
                    print("  ", a.family, a.address)
        else:
            print("Hostname:", socket.gethostname())
            try:
                print("Local IP:", socket.gethostbyname(socket.gethostname()))
            except Exception:
                print("Local IP: unknown")
    except Exception as e:
        print("netinfo error:", e)
'''
}

def ensure_example_modules():
    EXAMPLES_DIR.mkdir(exist_ok=True, parents=True)
    for rel, content in EXAMPLE_MODULES.items():
        p = EXAMPLES_DIR / rel
        if not p.exists():
            p.parent.mkdir(exist_ok=True, parents=True)
            p.write_text(content)

def main():
    anim = SingleLineMarquee("Starting the Metasploit Framework Console...", fps=10)
    anim.start()
    anim._thread.join()
    time.sleep(6)
    # Setelah animasi selesai, langsung clear terminal
    system_platform = platform.system().lower()
    if system_platform == "windows":
        os.system("cls")
    else:
        os.system("clear")
    ensure_example_modules()
    load_banners_from_folder()
    app = LazyFramework()
    try:
        app.repl()
    except Exception as e:
        print("Fatal error:", e)
    print("Goodbye.")

if __name__ == "__main__":
    main()
