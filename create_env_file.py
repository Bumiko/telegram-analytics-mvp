import os
import sys
import logging
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

async def main():
    """
    Скрипт для авторизации в Telegram API через телефонный номер.
    Создает файл сессии, который потом используется в основном приложении.
    """
    # Получение API ID и Hash из переменных окружения
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    
    if not api_id or not api_hash:
        logger.error("API ID или Hash не указаны. Пожалуйста, добавьте их в файл .env")
        sys.exit(1)
    
    # Конвертация строкового API ID в целое число
    api_id = int(api_id)
    
    # Создание клиента с отдельным именем сессии и device_model
    client = TelegramClient('telegram_analytics_bot', api_id, api_hash, device_model="Config Tool")
    
    # Запуск клиента
    await client.start()
    
    # Проверка, авторизован ли уже пользователь
    if await client.is_user_authorized():
        logger.info("Авторизация уже выполнена. Файл сессии готов к использованию.")
        await client.disconnect()
        return
    
    # Запрос номера телефона у пользователя
    phone = input("Введите ваш номер телефона (с кодом страны, например +7XXXXXXXXXX): ")
    
    try:
        # Отправка кода подтверждения
        logger.info("Отправка кода подтверждения...")
        await client.send_code_request(phone)
        
        # Ожидание ввода кода
        code = input("Введите код, который вы получили: ")
        
        try:
            # Авторизация с полученным кодом
            await client.sign_in(phone, code)
            logger.info("Авторизация успешно выполнена!")
            
        except SessionPasswordNeededError:
            # Если включена двухфакторная аутентификация
            password = input("Требуется двухфакторная аутентификация. Введите ваш пароль: ")
            await client.sign_in(password=password)
            logger.info("Двухфакторная аутентификация успешна!")
            
    except Exception as e:
        logger.error(f"Ошибка при авторизации: {str(e)}")
        sys.exit(1)
        
    finally:
        # Отключение от Telegram API
        await client.disconnect()
        
    logger.info("Файл сессии создан. Теперь вы можете запустить основное приложение.")

if __name__ == "__main__":
    asyncio.run(main())