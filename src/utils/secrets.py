import os
from dotenv import load_dotenv

load_dotenv()

is_stdio = os.getenv("IS_STDIO")
OPEN_AI_KEY = os.getenv("OPEN_AI_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Транспорт для агента: stdio или streamable_http.
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")
