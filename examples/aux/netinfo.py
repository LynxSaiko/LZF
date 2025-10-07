"""
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
