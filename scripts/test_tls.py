import socket
import ssl
import sys

HOST = "publicdatafeeds.networkrail.co.uk"
PORT = 61618
TIMEOUT = 10

def ssl_debug_callback(conn, direction, version, content_type, msg_type, data):
    """Callback function to log SSL/TLS handshake steps."""
    print(f"  [SSL DEBUG] {direction} | Version: {version} | Type: {content_type} | Length: {len(data)}")

print(f"=== Starting TLS Diagnostic for {HOST}:{PORT} ===")

# 1. Initialize Context
context = ssl.create_default_context()

# Verbose SSL context options
context.check_hostname = True
context.verify_mode = ssl.CERT_REQUIRED

print(f"OpenSSL Version: {ssl.OPENSSL_VERSION}")
print(f"Default Ciphers Configured: {len(context.get_ciphers())} available")

# 2. Open TCP Connection
try:
    print(f"\n1. Opening TCP connection to {HOST}:{PORT}...")
    sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
    sock.settimeout(TIMEOUT)
    print("   ✓ TCP Socket Connected.")
except Exception as e:
    print(f"   ✗ TCP Connection Failed: {e}")
    sys.exit(1)

# 3. Perform TLS Handshake with Debugging
try:
    print("\n2. Wrapping socket in SSL context (SNI enabled)...")
    print(f"   SNI Server Hostname: '{HOST}'")
    
    ssock = context.wrap_socket(sock, server_hostname=HOST)
    
    print("\n3. Initiating TLS Handshake...")
    ssock.do_handshake()
    
    print("\n=== SUCCESS: TLS Handshake Completed ===")
    print(f"Protocol: {ssock.version()}")
    print(f"Cipher Name: {ssock.cipher()[0]}")
    print(f"TLS Version: {ssock.cipher()[1]}")
    print(f"Secret Key Bits: {ssock.cipher()[2]}")
    
    cert = ssock.getpeercert()
    print(f"Issuer: {cert.get('issuer')}")
    print(f"Subject: {cert.get('subject')}")

except socket.timeout:
    print("\n=== FAIL: Handshake Timed Out ===")
    print("The Client Hello was sent over plain TCP, but no Server Hello response was received.")
    print("Likely cause: ISP/Firewall Deep Packet Inspection dropping non-standard TLS port 61618.")
except ssl.SSLError as e:
    print(f"\n=== FAIL: SSL Error ===")
    print(f"Reason: {e.reason}")
    print(f"Library: {e.library}")
    print(f"Message: {e}")
except Exception as e:
    print(f"\n=== FAIL: Unexpected Error ===")
    print(f"{type(e).__name__}: {e}")
finally:
    try:
        sock.close()
    except Exception:
        pass