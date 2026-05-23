import os
from pathlib import Path

# --- Telegram ---
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

# --- Anthropic ---
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))

# --- Knowledge base ---
# Locally point to the AI Knowledge Vault; on Railway mount a volume or copy files
KNOWLEDGE_DIR = Path(os.getenv(
    "KNOWLEDGE_DIR",
    str(Path(__file__).parent / "knowledge")
))

# --- RAG settings ---
CHUNK_SIZE: int = 800       # characters per chunk
CHUNK_OVERLAP: int = 150    # overlap between chunks
TOP_K: int = 5              # number of chunks to retrieve

# --- Bot behaviour ---
# Respond when: bot mentioned, reply to bot, or message contains ? / question words
TRIGGER_QUESTION_MARK: bool = True
TRIGGER_QUESTION_WORDS: bool = True
