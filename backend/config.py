import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

AGENT_MODEL = os.getenv(
    "AGENT_MODEL",
    "gpt-4o"
)

INTENT_MODEL = os.getenv(
    "INTENT_MODEL",
    "gpt-4o-mini"
)

DATABASE_URL = os.getenv("DATABASE_URL")