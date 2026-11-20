"""Детерминированная модель для запуска агента без ключа API."""

import re
import uuid

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

CITY_RE = re.compile(r"(?:в|во)\s+([А-ЯЁA-Z][\w\-]+)")
NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _plain(content) -> str:
    """Приводит содержимое сообщения к строке."""
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return " ".join(part for part in parts if part)
    return str(content)


def _numbers(query: str):
    """Возвращает числа из запроса."""
    return [float(item.replace(",", ".")) for item in NUMBER_RE.findall(query)]


def _city(query: str):
    """Возвращает город из запроса или None."""
    match = CITY_RE.search(query)
    return match.group(1) if match else None


class ScriptedChatModel(BaseChatModel):
    """Имитирует модель: выбирает инструмент по ключевым словам запроса."""

    model_name: str = "scripted-demo"
    bound_names: list = []

    @property
    def _llm_type(self) -> str:
        return "scripted-demo"

    def bind_tools(self, tools, **kwargs):
        names = []
        for item in tools or []:
            name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
            if name:
                names.append(name)
        self.bound_names = names
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        last_human = None
        tool_messages = []
        for message in messages:
            if isinstance(message, HumanMessage):
                last_human = message
                tool_messages = []
            elif isinstance(message, ToolMessage):
                tool_messages.append(message)

        if tool_messages:
            facts = "\n".join(f"- {m.name}: {_plain(m.content)[:220]}" for m in tool_messages)
            return self._answer("Кратко по результатам инструментов:\n" + facts)

        query = str(last_human.content) if last_human else ""
        call = self._choose(query)
        if call is None:
            return self._answer(
                "Могу посчитать сумму, показать погоду или перевести температуру. Уточните запрос."
            )

        name, args = call
        if self.bound_names and name not in self.bound_names:
            return self._answer(f"Инструмент {name} недоступен.")

        tool_call = {
            "name": name,
            "args": args,
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "type": "tool_call",
        }
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[tool_call]))]
        )

    def _choose(self, query: str):
        low = query.lower()

        if "погод" in low:
            return "get_weather", {"city": _city(query) or "Екатеринбург"}

        if "фаренгейт" in low or "цельс" in low or "температур" in low:
            values = _numbers(query)
            value = values[0] if values else 20.0
            scale = "celsius" if "цельс" in low else "fahrenheit"
            return "convert_temperature", {"value": value, "scale": scale}

        if any(word in low for word in ("сколько", "сумм", "плюс", "+")):
            values = _numbers(query)
            if len(values) >= 2:
                return "add", {"a": int(values[0]), "b": int(values[1])}

        return None

    @staticmethod
    def _answer(text: str):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])
