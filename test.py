import os
from dotenv import load_dotenv

load_dotenv()  # loads .env in the current directory
api_key = os.getenv("OPENROUTER_API_KEY")

if api_key:
    print(f"✅ API key loaded successfully: {api_key[:5]}...********")
else:
    print("❌ API key not found. Check .env file and path.")
