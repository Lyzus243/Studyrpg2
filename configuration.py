import smtplib
import socket
import os
from dotenv import load_dotenv

load_dotenv()

def test_sendgrid_ports():
    """Test different SendGrid SMTP ports"""
    EMAIL = os.getenv("MAIL_USERNAME", "apikey")
    PASSWORD = os.getenv("MAIL_PASSWORD")
    
    # SendGrid supports multiple ports
    ports = [
        (587, "STARTTLS", True),    # Most common, but blocked for you
        (465, "SSL/TLS", False),    # SSL port
        (25, "Plain/STARTTLS", True),  # Often blocked by ISPs
        (2525, "STARTTLS", True)    # Alternative port, less likely to be blocked
    ]
    
    print("=== TESTING SENDGRID PORTS ===")
    
    for port, description, use_starttls in ports:
        print(f"\n🔌 Testing port {port} ({description})...")
        
        # First test raw socket connectivity
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex(("smtp.sendgrid.net", port))
            sock.close()
            
            if result != 0:
                print(f"❌ Port {port}: Socket connection failed (error: {result})")
                continue
            else:
                print(f"✅ Port {port}: Socket connection successful")
        except Exception as e:
            print(f"❌ Port {port}: Socket test failed - {e}")
            continue
        
        # Test SMTP authentication
        try:
            if port == 465:
                # Use SMTP_SSL for port 465
                server = smtplib.SMTP_SSL("smtp.sendgrid.net", port, timeout=30)
            else:
                # Use regular SMTP for other ports
                server = smtplib.SMTP("smtp.sendgrid.net", port, timeout=30)
                if use_starttls:
                    server.starttls()
            
            server.login(EMAIL, PASSWORD)
            print(f"✅ Port {port}: SMTP authentication successful!")
            server.quit()
            return port  # Return the working port
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Port {port}: Authentication failed - {e}")
        except smtplib.SMTPException as e:
            print(f"❌ Port {port}: SMTP error - {e}")
        except Exception as e:
            print(f"❌ Port {port}: Connection failed - {e}")
    
    print("\n❌ No working SMTP ports found")
    return None

def update_env_with_working_port(working_port):
    """Update .env file with working port"""
    if working_port:
        print(f"\n✅ Update your .env file to use port {working_port}:")
        print(f"SMTP_PORT={working_port}")
        if working_port == 465:
            print("# Note: Port 465 uses SSL, not STARTTLS")

if __name__ == "__main__":
    working_port = test_sendgrid_ports()
    update_env_with_working_port(working_port)