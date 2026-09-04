"""
Minimal, stomp.py-independent test of the raw TLS handshake to Network
Rail's feed host. Uses a hard socket timeout so a stalled handshake
raises a clear error instead of hanging forever.
"""

import socket
import ssl

HOST = "publicdatafeeds.networkrail.co.uk"
PORT = 61618
TIMEOUT = 10

print(f"Attempting raw TLS handshake to {HOST}:{PORT} (timeout {TIMEOUT}s)...")

context = ssl.create_default_context()

try:
    with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as sock:
        print("Raw TCP connected.")
        sock.settimeout(TIMEOUT)
        with context.wrap_socket(sock, server_hostname=HOST) as ssock:
            print("TLS handshake SUCCEEDED.")
            print("Negotiated protocol:", ssock.version())
            print("Cipher:", ssock.cipher())
except socket.timeout:
    print("FAIL: TLS handshake timed out — connection hung, no response from either side.")
    print("This strongly suggests something (antivirus SSL inspection, a proxy, or a")
    print("firewall doing deep packet inspection) is intercepting/blocking the TLS")
    print("handshake on this specific port, even though plain TCP connects fine.")
except ssl.SSLError as e:
    print(f"FAIL: TLS handshake failed with an SSL error: {e}")
except Exception as e:
    print(f"FAIL: unexpected error: {type(e).__name__}: {e}")