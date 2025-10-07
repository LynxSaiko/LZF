"""
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
