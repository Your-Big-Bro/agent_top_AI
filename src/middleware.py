"""Middleware агента: логирование и защита входных данных.

В LangChain 1.x хуки pre_ainvoke и post_ainvoke реализуются через
before_model и after_model. Эти функции вызываются до и после модели.
"""

import re

from langchain.agents.middleware import after_model, before_model
from langchain_core.messages import AIMessage
from loguru import logger

BLOCKED_PATTERNS = [
    r"системн\w*\s+промпт",
    r"покажи\s+(свои\s+)?инструкц",
    r"ignore\s+(all\s+)?previous",
    r"print\s+your\s+(system\s+)?prompt",
    r"api[\s_-]?key",
]

BLOCKED = []


@before_model
def log_input(state, runtime):
    """Логирует вход пользователя до вызова модели."""
    last = state["messages"][-1]
    text = str(getattr(last, "content", ""))
    logger.info(f"[pre_ainvoke] роль={type(last).__name__}, символов={len(text)}")
    logger.debug(f"[pre_ainvoke] текст: {text[:160]}")
    return None


@before_model(can_jump_to=["end"])
def guard_input(state, runtime):
    """Блокирует запросы с признаками атаки."""
    text = str(state["messages"][-1].content)
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            BLOCKED.append({"text": text, "pattern": pattern})
            logger.warning(f"[guard] запрос заблокирован по шаблону {pattern}")
            return {
                "jump_to": "end",
                "messages": [
                    AIMessage(
                        content=(
                            "Запрос отклонен системой безопасности. "
                            "Нельзя запрашивать служебные инструкции."
                        )
                    )
                ],
            }
    return None


@after_model
def log_output(state, runtime):
    """Логирует ответ модели после вызова."""
    last = state["messages"][-1]
    calls = getattr(last, "tool_calls", None) or []
    text = str(getattr(last, "content", ""))
    logger.info(
        f"[post_ainvoke] роль={type(last).__name__}, вызовов инструментов={len(calls)}, символов={len(text)}"
    )
    if calls:
        logger.info(f"[post_ainvoke] инструменты: {[call['name'] for call in calls]}")
    elif text:
        logger.debug(f"[post_ainvoke] ответ: {text[:160]}")
    return None
