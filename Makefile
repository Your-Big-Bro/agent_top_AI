# Установка зависимостей 
setup:
	uv sync

# Запуск MCP сервера STDIO
mcp_stdio:
	npx @modelcontextprotocol/inspector uv run --with fastmcp mcp-server.py

# Запуск MCP сервера Streamable HTTP, необходимо выполнить две команды: mcp, inspector
mcp:
	uv run --with fastmcp --with requests --with starlette --with uvicorn mcp-server.py

# Запуск MCP Inspector
inspector:
	npx @modelcontextprotocol/inspector

# Запуск агента, который будет взаимодействовать с MCP сервером
agent:
	python main.py

# Запуск агента по HTTP. Сначала запустите make mcp в другом терминале
agent_http:
	MCP_TRANSPORT=http python main.py

# Эксперименты по заданиям 1-4. Пишет experiments/results.json
experiments:
	uv run --with fastmcp --with requests experiments.py
