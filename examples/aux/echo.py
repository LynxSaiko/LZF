"""
aux/echo — safe module: echo input string
"""
MODULE_INFO = {"name": "aux/echo", "description": "Echo string back (safe)"}
OPTIONS = {
    "MSG": {"required": True, "default": "", "description": "Message to echo"},
}

def run(session, options):
    msg = options.get("MSG", "")
    print("ECHO:", msg)
