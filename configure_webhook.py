"""
configure_webhook.py - Configure Twilio WhatsApp Sandbox Webhook
Place this file in THE TARNISHED/ folder (not in backend/)
"""

import os
from pathlib import Path
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables from .env
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(env_path)

# Get credentials
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Your ngrok URL (update this if ngrok URL changes)
NGROK_URL = "https://sensuous-subsoil-preview.ngrok-free.dev"
WEBHOOK_URL = f"{NGROK_URL}/twilio/webhook"

def configure_webhook():
    """Configure WhatsApp Sandbox webhook"""
    
    print("=" * 70)
    print("🔧 Configuring Twilio WhatsApp Sandbox Webhook")
    print("=" * 70)
    
    if not ACCOUNT_SID or not AUTH_TOKEN:
        print("\n❌ ERROR: Missing Twilio credentials!")
        print("   Make sure backend/.env file has:")
        print("   TWILIO_ACCOUNT_SID=your_sid_here")
        print("   TWILIO_AUTH_TOKEN=your_token_here")
        return
    
    try:
        # Initialize Twilio client
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        print("✅ Twilio client initialized")
        
        # Search for WhatsApp numbers
        print(f"\n📞 Looking for WhatsApp Sandbox number...")
        numbers = client.incoming_phone_numbers.list(limit=20)
        
        found = False
        for number in numbers:
            if "whatsapp" in number.phone_number:
                print(f"\n✅ Found WhatsApp number: {number.phone_number}")
                print(f"   SID: {number.sid}")
                print(f"   Current SMS URL: {number.sms_url or 'Not configured'}")
                print(f"   Current SMS Method: {number.sms_method or 'Not configured'}")
                
                # Update webhook
                print(f"\n🔄 Updating webhook to:")
                print(f"   {WEBHOOK_URL}")
                
                number.update(
                    sms_url=WEBHOOK_URL,
                    sms_method="POST"
                )
                
                print(f"\n✅ Webhook configured successfully!")
                print(f"   New SMS URL: {number.sms_url}")
                print(f"   New SMS Method: {number.sms_method}")
                found = True
                break
        
        if not found:
            print("\n❌ Could not find WhatsApp Sandbox number.")
            print("   Make sure you've activated the sandbox.")
            print("   Send 'join twilio-trial' to +1 (737) 250-8034 from WhatsApp")
            print("\n💡 Manual configuration:")
            print("   1. Go to: https://console.twilio.com")
            print("   2. Messaging → Try it Out → WhatsApp")
            print("   3. Find 'When a message comes in'")
            print(f"   4. Enter: {WEBHOOK_URL}")
        
        print("\n" + "=" * 70)
        print("🧪 Next Steps:")
        print("   1. Send 'join twilio-trial' to +1 (737) 250-8034")
        print("   2. Send a photo of a maize leaf")
        print("   3. Check FastAPI logs for responses")
        print("   4. Check ngrok dashboard: http://127.0.0.1:4040")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Try manual configuration:")
        print("   1. Go to: https://console.twilio.com")
        print("   2. Messaging → Try it Out → WhatsApp")
        print("   3. Find 'When a message comes in'")
        print(f"   4. Enter: {WEBHOOK_URL}")
        print("   5. Method: POST")
        print("   6. Click Save")

if __name__ == "__main__":
    configure_webhook()