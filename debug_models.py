import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY, transport="rest")

try:
    with open('available_models.txt', 'w') as f:
        for m in genai.list_models():
            f.write(f"{m.name}\n")
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
