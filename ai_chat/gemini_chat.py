"""
gemini_chat.py: Simple terminal chat with Google Gemini.

Requirements:
    pip install google-genai

Setup:
    Get a free API key at https://aistudio.google.com/apikey and set it as
    an environment variable (never hardcode keys in shared code):

    Windows (PowerShell):   $env:GEMINI_API_KEY = "your-key-here"
    Linux/macOS:            export GEMINI_API_KEY="your-key-here"

Usage:
    python gemini_chat.py
    Type your question, or "exit" to quit.
"""

import os
import sys

from google import genai

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("GEMINI_API_KEY is not set. See the instructions at the top of this file.")
    sys.exit(1)

client = genai.Client(api_key=api_key)

print("Chat with Gemini. Type 'exit' to quit.\n")

while True:
    question = input("You: ").strip()

    if not question:
        continue

    if question.lower() == "exit":
        print("Exiting the chat. Goodbye!")
        break

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=question,
    )

    print("Gemini: " + response.text + "\n")
