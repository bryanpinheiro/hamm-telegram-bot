from bot import HammBotController
from dotenv import load_dotenv
import os

if __name__ == "__main__":
    load_dotenv()
    api_token = os.getenv("API_TOKEN")

    if not api_token:
        raise ValueError("API_TOKEN not found in environment variables")
    
    bot = HammBotController(token=api_token)
    bot.start()