# WebSocket Proxy Server для Google Gemini Live API

Отдельный сервер для проксирования WebSocket соединений к Google Gemini Live API через HTTP прокси.

## Назначение

Этот сервер проксирует WebSocket соединения от клиента к Google API, используя HTTP прокси для обхода блокировок в РФ/Беларуси.

## Деплой на Render

### 1. Подготовка

1. Создайте новый Web Service на Render
2. Подключите этот репозиторий или загрузите папку `proxy-server`

### 2. Настройка переменных окружения

В Render Dashboard → Environment Variables добавьте:

```
HTTP_PROXY=http://1aAtT9:Z5ZY3C@196.19.122.247:8000
HTTPS_PROXY=http://1aAtT9:Z5ZY3C@196.19.122.247:8000
PORT=5000
WS_PORT=8765
```

### 3. Настройки сервиса

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python app.py`
- **Python Version:** 3.13.0 (или совместимая)

### 4. После деплоя

После деплоя сервер будет доступен по адресу:
```
https://your-service.onrender.com
```

WebSocket endpoint:
```
wss://your-service.onrender.com/api/gemini/ws-proxy?api_key=YOUR_API_KEY
```

## Использование

### Endpoints

- `GET /` - Информация о сервисе
- `GET /health` - Health check
- `GET /api/gemini/ws-proxy-info?api_key=YOUR_KEY` - Информация о WebSocket прокси
- `WS /api/gemini/ws-proxy?api_key=YOUR_KEY` - WebSocket прокси

### Пример подключения

```javascript
const ws = new WebSocket('wss://your-service.onrender.com/api/gemini/ws-proxy?api_key=YOUR_API_KEY');
```

## Локальный запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл

# Запуск
python app.py
```

Сервер будет доступен:
- Flask API: http://localhost:5000
- WebSocket: ws://localhost:8765/api/gemini/ws-proxy

## Важно

⚠️ Стандартная библиотека `websockets` в Python может не поддерживать HTTP прокси напрямую. Для полной поддержки HTTP прокси рекомендуется:

1. Использовать SOCKS5 прокси вместо HTTP
2. Настроить прокси на уровне системы/сервера
3. Использовать библиотеку с поддержкой прокси (например, через `httpx`)

## Структура проекта

```
proxy-server/
├── app.py              # Основной файл приложения
├── requirements.txt    # Зависимости Python
├── runtime.txt        # Версия Python
├── render.yaml        # Конфигурация для Render
├── .env.example       # Пример переменных окружения
└── README.md          # Этот файл
```

