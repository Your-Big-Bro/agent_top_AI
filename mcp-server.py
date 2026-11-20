import asyncio
import re
from pathlib import Path

import requests
from fastmcp import FastMCP

from src.utils.secrets import is_stdio

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "src" / "data"

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 8

server = FastMCP(name="Topic Experiment")


def _read_data(file_name: str) -> str:
    """Читает файл данных. Возвращает текст ошибки, если файла нет."""
    path = DATA_DIR / file_name
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Ошибка: файл данных не найден: {file_name}."
    except OSError as exc:
        return f"Ошибка чтения файла данных: {type(exc).__name__}."


@server.prompt()
def explain_topic(topic: str, level: str = "beginner") -> str:
    """Генерирует промпт для объяснения темы в дружелюбной манере."""
    styles = {
        "beginner": "in a beginner friendly manner with simple wordings and no technical jargon",
        "expert": "in a concise expert manner with precise terminology and no filler",
    }
    style = styles.get(level.lower().strip(), styles["beginner"])
    return f"Can you explain {topic} {style}. Include Concept & Examples."


@server.resource("entry-weather-example://weather-letter", mime_type="text/markdown")
def write_3way_intro() -> str:
    """Пример написания приветственного сообщения, если пользователь хочет информацию по погоде"""
    return _read_data("entry_letter.md")


@server.resource("info-excursion://Paris-trips", mime_type="text/markdown")
def write_excursion_intro() -> str:
    """Информация по экскурсиям в Париже"""
    return _read_data("paris_trips.md")


@server.resource("info-city://Yekaterinburg", mime_type="text/markdown")
def write_city_intro() -> str:
    """Краткая справка о Екатеринбурге: климат, транспорт, достопримечательности"""
    return _read_data("city_yekaterinburg.md")


@server.resource("info-attraction://Baikal", mime_type="text/markdown")
def write_baikal_intro() -> str:
    """Справка о достопримечательности: озеро Байкал"""
    return _read_data("baikal.md")


@server.tool()
async def add(a: int, b: int) -> str:
    """Сумма двух чисел"""
    return str(a + b)


def _geocode(city: str):
    """Возвращает первую запись геокодера или None."""
    response = requests.get(
        GEO_URL,
        params={"name": city, "count": 1, "language": "ru"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    return results[0] if results else None


@server.tool()
def get_weather(city: str) -> str:
    """
    Получает текущую погоду в городе.
    """
    if not city or not city.strip():
        return "Ошибка: укажите название города."

    try:
        geo = _geocode(city.strip())
    except requests.Timeout:
        return "Ошибка: сервис геокодирования не ответил вовремя. Повторите позже."
    except requests.RequestException as exc:
        return f"Ошибка сети при поиске города: {type(exc).__name__}."
    except ValueError:
        return "Ошибка: сервис геокодирования вернул некорректный ответ."

    if geo is None:
        return f"Город не найден: {city}."

    try:
        response = requests.get(
            WEATHER_URL,
            params={
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
                "current_weather": True,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        current = response.json()["current_weather"]
    except requests.Timeout:
        return "Ошибка: сервис погоды не ответил вовремя. Повторите позже."
    except requests.RequestException as exc:
        return f"Ошибка сети при получении погоды: {type(exc).__name__}."
    except (KeyError, TypeError, ValueError):
        return "Ошибка: сервис погоды вернул неожиданный ответ."

    name = geo.get("name", city)
    return f"Погода в {name}: {current['temperature']}°C, ветер {current['windspeed']} км/ч"


@server.tool()
def convert_temperature(value: float, scale: str = "celsius") -> str:
    """Переводит температуру между шкалами Цельсия и Фаренгейта"""
    scale_normalized = scale.lower().strip()
    if scale_normalized.startswith("c"):
        return f"{value}°C = {round(value * 9 / 5 + 32, 1)}°F"
    if scale_normalized.startswith("f"):
        return f"{value}°F = {round((value - 32) * 5 / 9, 1)}°C"
    return "Ошибка: параметр scale должен быть 'celsius' или 'fahrenheit'."


MAX_TEXT_LENGTH = 10000


@server.tool()
def count_words(text: str) -> str:
    """Считает слова, символы и предложения в тексте"""
    if text is None:
        return "Ошибка: передайте текст. Параметр text пустой."

    cleaned = text.strip()
    if not cleaned:
        return "Ошибка: текст пустой. Передайте текст для подсчета."

    if len(cleaned) > MAX_TEXT_LENGTH:
        return f"Ошибка: текст слишком длинный. Максимум {MAX_TEXT_LENGTH} символов."

    words = len(cleaned.split())
    sentences = len([item for item in re.split(r"[.!?]+", cleaned) if item.strip()])
    chars_with_spaces = len(text)
    chars_without_spaces = len(re.sub(r"\s", "", text))
    return (
        f"Слова: {words}. Символы: {chars_with_spaces}. "
        f"Символы без пробелов: {chars_without_spaces}. Предложения: {sentences}."
    )


if __name__ == "__main__":
    if is_stdio == "True":
        # уровень протокола stdio
        server.run(transport="stdio")
    else:
        # уровень протокола streamable-http
        server.run(transport="streamable-http", host="127.0.0.1", port=8000)
