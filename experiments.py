"""Эксперименты по заданиям 1-4: prompt, resources, tools, transports.

Скрипт запускает MCP сервер в памяти, по stdio и по streamable-http,
сохраняет результаты в experiments/results.json и печатает сводку.
"""

import asyncio
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport, StreamableHttpTransport

BASE_DIR = Path(__file__).resolve().parent
SERVER_PATH = BASE_DIR / "mcp-server.py"
RESULTS_DIR = BASE_DIR / "experiments"
RESULTS_DIR.mkdir(exist_ok=True)

HOST = "127.0.0.1"
PORT = 8000


def load_server():
    """Загружает mcp-server.py как модуль и возвращает объект сервера."""
    sys.path.insert(0, str(BASE_DIR))
    spec = importlib.util.spec_from_file_location("mcp_server", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.server


def result_text(result) -> str:
    """Достает текст из результата вызова инструмента."""
    data = getattr(result, "data", None)
    if data is not None:
        return str(data)
    if getattr(result, "content", None):
        return str(result.content[0].text)
    return str(result)


async def prompt_experiments(client):
    """Задание 1: промпт на простых, сложных и некорректных данных."""
    cases = [
        ("MCP", "beginner"),
        ("квантовая запутанность", "beginner"),
        ("MCP", "expert"),
        ("", "beginner"),
        ("MCP", "unknown-style"),
    ]
    rows = []
    for topic, level in cases:
        try:
            prompt = await client.get_prompt("explain_topic", {"topic": topic, "level": level})
            text = prompt.messages[0].content.text
            rows.append({"topic": topic, "level": level, "prompt": text, "error": None})
        except Exception as exc:
            rows.append(
                {"topic": topic, "level": level, "prompt": None,
                 "error": f"{type(exc).__name__}: {exc}"}
            )
    return rows


async def resource_experiments(client):
    """Задание 2: чтение ресурсов и их содержимого."""
    rows = []
    for resource in await client.list_resources():
        uri = str(resource.uri)
        try:
            content = await client.read_resource(uri)
            text = content[0].text if content else ""
            rows.append({"uri": uri, "mime": getattr(resource, "mime_type", None) or getattr(resource, "mimeType", None),
                         "text": text, "error": None})
        except Exception as exc:
            rows.append({"uri": uri, "mime": None, "text": None,
                         "error": f"{type(exc).__name__}: {exc}"})
    return rows


async def tool_experiments(client):
    """Задание 3: инструменты на разных входных данных."""
    cases = [
        ("add", {"a": 2, "b": 2}),
        ("add", {"a": -5, "b": 3}),
        ("add", {"a": 1.5, "b": 2}),
        ("add", {"a": "2", "b": "x"}),
        ("get_weather", {"city": "Paris"}),
        ("get_weather", {"city": "PARIS"}),
        ("get_weather", {"city": "paris"}),
        ("get_weather", {"city": "Atlantis12345"}),
        ("get_weather", {"city": ""}),
        ("convert_temperature", {"value": 25, "scale": "celsius"}),
        ("convert_temperature", {"value": 77, "scale": "fahrenheit"}),
        ("convert_temperature", {"value": 10, "scale": "kelvin"}),
        ("count_words", {"text": "Байкал - самое глубокое озеро мира. Летом там тепло."}),
        ("count_words", {"text": ""}),
        ("count_words", {"text": "   "}),
        ("count_words", {"text": 123}),
    ]
    rows = []
    for name, args in cases:
        started = time.perf_counter()
        try:
            result = await client.call_tool(name, args)
            text, error = result_text(result), None
        except Exception as exc:
            text, error = None, f"{type(exc).__name__}: {str(exc)[:160]}"
        rows.append(
            {
                "tool": name,
                "args": args,
                "result": text,
                "error": error,
                "ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
    return rows


async def measure_transport(transport, label: str, calls: int = 5):
    """Подключается к серверу и измеряет время подключения и вызовов."""
    started = time.perf_counter()
    async with Client(transport) as client:
        connect_ms = round((time.perf_counter() - started) * 1000, 1)
        timings = []
        for _ in range(calls):
            begin = time.perf_counter()
            await client.call_tool("add", {"a": 1, "b": 2})
            timings.append((time.perf_counter() - begin) * 1000)
        tools = [tool.name for tool in await client.list_tools()]
    return {
        "transport": label,
        "connect_ms": connect_ms,
        "mean_call_ms": round(sum(timings) / len(timings), 1),
        "min_call_ms": round(min(timings), 1),
        "max_call_ms": round(max(timings), 1),
        "tools": tools,
    }


def wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    """Ждет, пока порт начнет принимать соединения."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.5)
    return False


async def http_experiment():
    """Задание 4: streamable-http транспорт на отдельном процессе."""
    env = os.environ.copy()
    env["IS_STDIO"] = "False"
    process = subprocess.Popen(
        [sys.executable, str(SERVER_PATH)],
        cwd=str(BASE_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_for_port(HOST, PORT):
            return {"transport": "streamable-http", "error": "сервер не открыл порт 8000"}
        transport = StreamableHttpTransport(f"http://{HOST}:{PORT}/mcp")
        return await measure_transport(transport, "streamable-http")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


async def main():
    server = load_server()

    async with Client(server) as client:
        prompts = await prompt_experiments(client)
        resources = await resource_experiments(client)
        tools = await tool_experiments(client)
        in_memory = {
            "transport": "in-memory",
            "tools": [tool.name for tool in await client.list_tools()],
            "prompts": [prompt.name for prompt in await client.list_prompts()],
        }

    stdio_env = os.environ.copy()
    stdio_env["IS_STDIO"] = "True"
    try:
        stdio = await measure_transport(
            PythonStdioTransport(str(SERVER_PATH), env=stdio_env), "stdio"
        )
    except Exception as exc:
        stdio = {"transport": "stdio", "error": f"{type(exc).__name__}: {exc}"}

    try:
        http = await http_experiment()
    except Exception as exc:
        http = {"transport": "streamable-http", "error": f"{type(exc).__name__}: {exc}"}

    payload = {
        "in_memory": in_memory,
        "prompts": prompts,
        "resources": resources,
        "tools": tools,
        "transports": {"stdio": stdio, "streamable-http": http},
    }

    output = RESULTS_DIR / "results.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== PROMPTS ===")
    for row in prompts:
        print(f"[{row['level']}] {row['topic']!r} -> {str(row['prompt'])[:110]}")

    print("\n=== RESOURCES ===")
    for row in resources:
        print(f"{row['uri']} ({row['mime']}): {str(row['text'])[:80]}")

    print("\n=== TOOLS ===")
    for row in tools:
        value = row["result"] if row["error"] is None else "ERROR " + row["error"]
        print(f"{row['tool']}({row['args']}) -> {str(value)[:110]}")

    print("\n=== TRANSPORTS ===")
    for item in (stdio, http):
        print(item)

    print(f"\nРезультаты сохранены: {output}")


if __name__ == "__main__":
    asyncio.run(main())
