import smtplib
import socket
import os
from dotenv import load_dotenv
import ssl

load_dotenv()

EMAIL = os.getenv("SMTP_USER", "apikey")
PASSWORD = os.getenv("SMTP_PASS")
SMTP_SERVER = os.getenv("SMTP_HOST", "smtp.sendgrid.net")

def test_port_connectivity(host, port, timeout=10):
    """Test if we can connect to a specific port"""
    try:
        print(f"Testing connectivity to {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port} is reachable")
            return True
        else:
            print(f"❌ Port {port} is not reachable")
            return False
    except Exception as e:
        print(f"❌ Error testing port {port}: {e}")
        return False

def test_smtp_with_timeout(port, use_ssl=False):
    """Test SMTP connection with shorter timeout"""
    try:
        print(f"\n🔌 Testing SMTP on port {port} (SSL: {use_ssl})...")
        
        if use_ssl:
            # For implicit SSL (port 465)
            server = smtplib.SMTP_SSL(SMTP_SERVER, port, timeout=15)
        else:
            # For explicit TLS (port 587)
            server = smtplib.SMTP(SMTP_SERVER, port, timeout=15)
            print("Connected, sending EHLO...")
            server.ehlo()
            print("Starting TLS...")
            server.starttls()
            print("TLS established, sending EHLO again...")
            server.ehlo()
        
        print("Attempting login...")
        server.login(EMAIL, PASSWORD)
        print(f"✅ SMTP connection successful on port {port}!")
        server.quit()
        return True
        
    except socket.timeout:
        print(f"❌ Connection timeout on port {port}")
        return False
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed on port {port}: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"❌ Connection failed on port {port}: {e}")
        return False
    except Exception as e:
        print(f"❌ SMTP test failed on port {port}: {e}")
        return False

def main():
    print("=== SendGrid SMTP Diagnostics ===\n")
    
    # Check credentials
    if not PASSWORD:
        print("❌ SMTP_PASS not set in environment variables")
        return
    
    print(f"SMTP_SERVER: {SMTP_SERVER}")
    print(f"SMTP_USER: {EMAIL}")
    print(f"Password set: {'Yes' if PASSWORD else 'No'}")
    
    # Test basic connectivity first
    print("\n=== Testing Port Connectivity ===")
    ports_to_test = [587, 465, 25]
    reachable_ports = []
    
    for port in ports_to_test:
        if test_port_connectivity(SMTP_SERVER, port):
            reachable_ports.append(port)
    
    if not reachable_ports:
        print("\n❌ No SMTP ports are reachable. This suggests:")
        print("   - Firewall blocking SMTP ports")
        print("   - Corporate network restrictions")
        print("   - ISP blocking SMTP ports")
        print("\nTry using a VPN or different network.")
        return
    
    # Test SMTP on reachable ports
    print(f"\n=== Testing SMTP Authentication ===")
    print(f"Reachable ports: {reachable_ports}")
    
    success = False
    
    # Test port 587 with STARTTLS
    if 587 in reachable_ports:
        success = test_smtp_with_timeout(587, use_ssl=False)
    
    # Test port 465 with implicit SSL if 587 failed
    if not success and 465 in reachable_ports:
        success = test_smtp_with_timeout(465, use_ssl=True)
    
    # Test port 25 if others failed
    if not success and 25 in reachable_ports:
        success = test_smtp_with_timeout(25, use_ssl=False)
    
    if success:
        print("\n✅ At least one SMTP configuration works!")
    else:
        print("\n❌ All SMTP tests failed")
        print("\nPossible solutions:")
        print("1. Try a different network/VPN")
        print("2. Check if SendGrid API key is valid")
        print("3. Verify sender email is authenticated in SendGrid")
        print("4. Consider using SendGrid's HTTP API instead of SMTP")

if __name__ == "__main__":
    main()