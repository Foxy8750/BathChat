from google import genai
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file
key = os.getenv("API_KEY")



client = genai.Client(api_key=key)

response = client.models.generate_content(
    model="gemini-flash-latest",
    contents="hello"
)

print(response.text)