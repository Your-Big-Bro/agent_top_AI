import sys
from pathlib import Path

from langchain_core.messages import ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from loguru import logger

from src.utils.secrets import MCP_TRANSPORT, MCP_URL, OPENROUTER_API_KEY

BASE_DIR = Path(__file__).resolve().parents[1]
SERVER_PATH = BASE_DIR / "mcp-server.py"

WEATHER_RESOURCE_URI = "entry-weather-example://weather-letter"
CITY_RESOURCE_URI = "info-city://Yekaterinburg"


def get_tools_used(response):
    """Извлекает информацию об инструментах, использованных в ответе агента."""
    tools = []
    for message in response["messages"]:
        if isinstance(message, ToolMessage):
            tools.append(
                {
                    "name": message.name,
                    "result": message.content,
                    "tool_call_id": message.tool_call_id,
                }
            )
    return tools


def get_resource_content(resources, uri: str = WEATHER_RESOURCE_URI) -> str:
    """Возвращает содержимое ресурса по URI."""
    for blob in resources:
        if str(blob.metadata.get("uri")) == uri:
            return blob.as_string()
    return ""


def get_all_resources_text(resources) -> str:
    """Склеивает все ресурсы в один текст для system_prompt."""
    parts = []
    for blob in resources:
        uri = blob.metadata.get("uri")
        if uri:
            parts.append(f"[{uri}]\n{blob.as_string()}")
    return "\n\n".join(parts)


def client_setup(transport: str | None = None):
    """Создает MCP клиент. Режим задается аргументом или переменной MCP_TRANSPORT."""
    mode = (transport or MCP_TRANSPORT or "stdio").lower().replace("-", "_")
    if mode.startswith("http"):
        config = {
            "main": {
                "transport": "streamable_http",
                "url": MCP_URL,
            }
        }
        logger.info(f"MCP транспорт: streamable_http, URL={MCP_URL}")
    else:
        config = {
            "main": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(SERVER_PATH)],
                "env": {"IS_STDIO": "True"},
            }
        }
        logger.info(f"MCP транспорт: stdio, сервер={SERVER_PATH}")
    return MultiServerMCPClient(config)


def model_setup():
    """Возвращает ChatOpenAI при наличии ключа, иначе демо-модель."""
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY не задан. Используется демо-модель ScriptedChatModel.")
        from src.demo_model import ScriptedChatModel

        return ScriptedChatModel()
    model = ChatOpenAI(
        model="nvidia/nemotron-3.5-super-vl:free",
        base_url="https://openrouter.ai/api/v1",
        temperature=0.1,
        api_key=OPENROUTER_API_KEY,
        max_tokens=1000,
        timeout=30,
    )
    return model
