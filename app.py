"""
WebSocket прокси сервер для Google Gemini Live API
Проксирует WebSocket соединения от клиента к Google API через HTTP прокси
Развертывается на Render как отдельный сервис
"""

import os
import asyncio
import websockets
import json
import logging
from urllib.parse import urlparse
from flask import Flask, request, jsonify
from flask_cors import CORS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# URL WebSocket для Google Gemini Live API
GEMINI_WS_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService/BidiGenerateContent"

# Инициализация Flask приложения
app = Flask(__name__)
CORS(app)  # Разрешаем CORS для всех доменов

# Хранилище активных WebSocket соединений
active_connections = {}

def get_proxy_config():
    """Получает конфигурацию прокси из переменных окружения"""
    proxy_url = os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY') or os.getenv('PROXY_URL') or os.getenv('PROXY')
    
    if not proxy_url:
        return None
    
    try:
        parsed = urlparse(proxy_url)
        return {
            'host': parsed.hostname,
            'port': int(parsed.port) if parsed.port else 80,
            'username': parsed.username,
            'password': parsed.password,
            'url': proxy_url,
        }
    except Exception as e:
        logger.error(f"Ошибка парсинга прокси URL: {e}")
        return None

async def proxy_websocket(client_ws, api_key: str):
    """
    Проксирует WebSocket соединение от клиента к Google API через HTTP прокси
    
    Args:
        client_ws: WebSocket соединение от клиента
        api_key: API ключ Google Gemini
    """
    google_ws = None
    try:
        # Получаем конфигурацию прокси
        proxy_config = get_proxy_config()
        
        # Создаем WebSocket соединение к Google API
        headers = {
            "x-goog-api-key": api_key,
        }
        
        google_ws_url = f"{GEMINI_WS_URL}?key={api_key}"
        
        # Подключение через прокси (если настроен)
        if proxy_config:
            logger.info(f"🔗 Подключение к Google API WebSocket через прокси {proxy_config['host']}:{proxy_config['port']}...")
            
            # Устанавливаем переменные окружения для прокси
            # websockets библиотека может использовать их через httpx/proxy-сервер
            original_http_proxy = os.environ.get('HTTP_PROXY')
            original_https_proxy = os.environ.get('HTTPS_PROXY')
            
            os.environ['HTTP_PROXY'] = proxy_config['url']
            os.environ['HTTPS_PROXY'] = proxy_config['url']
            
            try:
                # ВАЖНО: Стандартная websockets библиотека не поддерживает HTTP прокси напрямую
                # Используем библиотеку, которая поддерживает прокси, или обходной путь
                # Пока используем подключение напрямую - прокси должен быть на уровне системы/сервера
                
                logger.info("⚠️ Стандартная websockets не поддерживает HTTP прокси напрямую")
                logger.info("💡 Прокси должен быть настроен на уровне системы или использовать SOCKS прокси")
                
                async with websockets.connect(
                    google_ws_url, 
                    extra_headers=headers,
                ) as google_ws:
                    logger.info("✅ Подключено к Google API WebSocket")
                    await handle_websocket_messages(client_ws, google_ws)
                    
            except Exception as proxy_error:
                logger.error(f"❌ Ошибка подключения: {proxy_error}")
                raise
            finally:
                # Восстанавливаем переменные окружения
                if original_http_proxy:
                    os.environ['HTTP_PROXY'] = original_http_proxy
                elif 'HTTP_PROXY' in os.environ:
                    del os.environ['HTTP_PROXY']
                    
                if original_https_proxy:
                    os.environ['HTTPS_PROXY'] = original_https_proxy
                elif 'HTTPS_PROXY' in os.environ:
                    del os.environ['HTTPS_PROXY']
        else:
            logger.info("Подключение к Google API WebSocket напрямую (прокси не настроен)...")
            async with websockets.connect(google_ws_url, extra_headers=headers) as google_ws:
                logger.info("✅ Подключено к Google API WebSocket")
                await handle_websocket_messages(client_ws, google_ws)
            
    except Exception as e:
        logger.error(f"Ошибка в proxy_websocket: {e}", exc_info=True)
        try:
            await client_ws.close(code=1011, reason=f"Proxy error: {str(e)}")
        except:
            pass

async def handle_websocket_messages(client_ws, google_ws):
    """Обрабатывает двунаправленную передачу сообщений между клиентом и Google"""
    # Запускаем две задачи для двунаправленной передачи данных
    async def client_to_google():
        try:
            async for message in client_ws:
                # Пересылаем сообщение от клиента к Google
                await google_ws.send(message)
                logger.debug(f"Отправлено клиенту->Google: {len(message)} байт")
        except websockets.exceptions.ConnectionClosed:
            logger.info("Клиент отключился")
        except Exception as e:
            logger.error(f"Ошибка в client_to_google: {e}", exc_info=True)
    
    async def google_to_client():
        try:
            async for message in google_ws:
                # Пересылаем сообщение от Google к клиенту
                await client_ws.send(message)
                logger.debug(f"Отправлено Google->клиенту: {len(message)} байт")
        except websockets.exceptions.ConnectionClosed:
            logger.info("Google API отключился")
        except Exception as e:
            logger.error(f"Ошибка в google_to_client: {e}", exc_info=True)
    
    # Ждем завершения обеих задач
    await asyncio.gather(
        client_to_google(),
        google_to_client(),
        return_exceptions=True
    )

async def handle_websocket_proxy(websocket, path):
    """
    Обработчик WebSocket соединения от клиента
    """
    connection_id = None
    try:
        # Получаем API ключ из query параметров или первого сообщения
        query_params = path.split('?')[1] if '?' in path else ''
        api_key = None
        
        if query_params:
            from urllib.parse import parse_qs
            params = parse_qs(query_params)
            api_key = params.get('api_key', [None])[0]
        
        if not api_key:
            # Ждем первое сообщение с API ключом
            first_message = await websocket.recv()
            try:
                data = json.loads(first_message)
                api_key = data.get('api_key')
            except:
                await websocket.close(code=1008, reason="API key required")
                return
        
        connection_id = f"{id(websocket)}"
        active_connections[connection_id] = websocket
        
        logger.info(f"Начало проксирования WebSocket для API ключа: {api_key[:10]}... (connection: {connection_id})")
        await proxy_websocket(websocket, api_key)
        
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"WebSocket соединение закрыто (connection: {connection_id})")
    except Exception as e:
        logger.error(f"Ошибка в handle_websocket_proxy: {e}", exc_info=True)
    finally:
        if connection_id and connection_id in active_connections:
            del active_connections[connection_id]

async def start_websocket_server(port: int = 8765):
    """
    Запускает WebSocket прокси сервер
    
    Args:
        port: Порт для WebSocket сервера
    """
    proxy_config = get_proxy_config()
    if proxy_config:
        logger.info(f"✅ HTTP прокси настроен: {proxy_config['host']}:{proxy_config['port']}")
        logger.warning("⚠️ ВНИМАНИЕ: Стандартная библиотека websockets может не поддерживать HTTP прокси")
        logger.info("💡 Для работы через HTTP прокси рекомендуется использовать SOCKS5 прокси или прокси на уровне системы")
    else:
        logger.info("⚠️ HTTP прокси не настроен, подключение будет прямым")
    
    logger.info(f"Запуск WebSocket прокси сервера на порту {port}...")
    async with websockets.serve(handle_websocket_proxy, "0.0.0.0", port):
        logger.info(f"✅ WebSocket прокси сервер запущен на ws://0.0.0.0:{port}")
        await asyncio.Future()  # Запускаем бесконечно

# Flask routes
@app.route("/")
def home():
    """Главная страница"""
    proxy_config = get_proxy_config()
    return jsonify({
        "service": "WebSocket Proxy Server for Google Gemini Live API",
        "status": "running",
        "proxy": "configured" if proxy_config else "not configured",
        "proxy_host": f"{proxy_config['host']}:{proxy_config['port']}" if proxy_config else None,
        "websocket_endpoint": "/api/gemini/ws-proxy",
    })

@app.route("/health")
def health():
    """Health check endpoint для Render"""
    return jsonify({"status": "healthy"}), 200

@app.route("/api/gemini/ws-proxy-info", methods=["GET", "OPTIONS"])
def api_ws_proxy_info():
    """Возвращает информацию о WebSocket прокси для клиента"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        # Получаем API ключ из query параметров
        api_key = request.args.get('api_key')
        if not api_key:
            return jsonify({"error": "API key required"}), 400
        
        # Получаем базовый URL
        base_url = request.url_root.rstrip('/')
        ws_proxy_url = base_url.replace('http://', 'ws://').replace('https://', 'wss://') + '/api/gemini/ws-proxy'
        
        return jsonify({
            "ws_proxy_url": ws_proxy_url,
            "api_key_masked": api_key[:10] + "..." if len(api_key) > 10 else "***",
            "proxy_configured": get_proxy_config() is not None,
        }), 200
        
    except Exception as e:
        logger.error(f"[WS Proxy Info] Ошибка: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def run_server():
    """Запускает Flask сервер и WebSocket сервер"""
    import threading
    
    # Запускаем WebSocket сервер в отдельном потоке
    ws_port = int(os.getenv('WS_PORT', '8765'))
    ws_thread = threading.Thread(
        target=lambda: asyncio.run(start_websocket_server(port=ws_port)),
        daemon=True
    )
    ws_thread.start()
    
    # Запускаем Flask сервер
    flask_port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=flask_port, debug=False)

if __name__ == "__main__":
    run_server()

