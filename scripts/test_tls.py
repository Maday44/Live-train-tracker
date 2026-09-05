import socket
import ssl
import sys

HOST = "publicdatafeeds.networkrail.co.uk"
PORTS_TO_TEST = [61618, 61613, 61614]
TIMEOUT = 5

print(f"=== Starting Network Rail STOMP Port Diagnostic ===")
print(f"Target Host: {HOST}")
print(f"OpenSSL Version: {ssl.OPENSSL_VERSION}\n")

successful_port = None
successful_ssl = False

context = ssl.create_default_context()

for PORT in PORTS_TO_TEST:
    print(f"--------------------------------------------------")
    print(f"Testing Connection to {HOST}:{PORT} ...")
    
    sock = None
    try:
        # Step 1: Attempt raw TCP socket connection
        sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
        sock.settimeout(TIMEOUT)
        print(f"  ✓ TCP Socket Connected on Port {PORT}")

        # Step 2: Perform TLS handshake if on port 61618 or 61614
        if PORT in [61618, 61614]:
            print(f"  -> Wrapping socket in SSL (SNI: '{HOST}')...")
            ssock = context.wrap_socket(sock, server_hostname=HOST)
            ssock.do_handshake()
            print(f"  ✓ TLS Handshake Completed! Protocol: {ssock.version()}, Cipher: {ssock.cipher()[0]}")
            sock = ssock
            successful_ssl = True
        else:
            print(f"  ✓ Plain TCP connection ready (No SSL required on Port {PORT})")
            successful_ssl = False

        successful_port = PORT
        print(f"\n=== SUCCESS: Connected successfully on Port {PORT} ===")
        sock.close()
        break

    except socket.timeout:
        print(f"  ✗ FAIL: Connection/Handshake Timed Out on Port {PORT}")
        print("    Likely cause: ISP/Firewall filtering non-standard port traffic.")
    except ssl.SSLError as e:
        print(f"  ✗ FAIL: SSL Handshake Error on Port {PORT}: {e.reason if hasattr(e, 'reason') else e}")
    except Exception as e:
        print(f"  ✗ FAIL: Connection Error on Port {PORT}: {type(e).__name__} - {e}")
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass

print(f"\n--------------------------------------------------")
if successful_port:
    print(f"RESULT: Use PORT = {successful_port} in your scripts.")
    print(f"SSL Enabled: {successful_ssl}")
else:
    print("RESULT: All ports failed. Complete network/ISP block detected.")
    sys.exit(1)