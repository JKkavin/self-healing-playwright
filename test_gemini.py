import os
from dotenv import load_dotenv
from openai import OpenAI

# Load the .env file
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY not found in .env file")
    exit(1)

print(f"✅ Key loaded (starts with: {api_key[:8]}...)")

# Point OpenAI client at Gemini's OpenAI-compatible endpoint
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# Make a test call
response = client.chat.completions.create(
    model="gemini-3.6-flash",  # ← changed from gemini-2.5-flash
    messages=[
        {"role": "user", "content": "Reply with exactly: Gemini connection works"}
    ]
)

print("🤖 Response:", response.choices[0].message.content)