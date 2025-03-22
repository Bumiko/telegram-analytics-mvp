import os
import sys
import logging
import asyncio
import json
import time
from typing import Dict, Any, Optional
import shutil
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, AuthRestartError, PhoneCodeExpiredError, \
    PhoneCodeInvalidError, FloodWaitError

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Базовая директория проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, 'telegram_analytics_bot')
SESSION_DIR = os.path.join(BASE_DIR, 'sessions')

# Создаем директорию для хранения сессионных файлов, если она не существует
os.makedirs(SESSION_DIR, exist_ok=True)

class TelegramAuthHandler:
    """Класс для управления авторизацией в Telegram API"""
    
    def __init__(self, api_id: str = None, api_hash: str = None, session_name: str = 'telegram_analytics_bot'):
        """
        Инициализация обработчика авторизации
        
        Args:
            api_id: API ID для Telegram
            api_hash: API Hash для Telegram
            session_name: Имя файла сессии
        """
        self.api_id = int(api_id) if api_id else int(os.getenv('TELEGRAM_API_ID', 0))
        self.api_hash = api_hash or os.getenv('TELEGRAM_API_HASH', '')
        self.session_name = session_name
        self.session_path = os.path.join(BASE_DIR, f"{session_name}.session")
        self._client = None
        self._session_lock = asyncio.Lock()
    
    async def _get_client(self) -> TelegramClient:
        """
        Получение клиента Telegram API с синхронизацией
        
        Returns:
            Клиент Telegram API
        """
        async with self._session_lock:
            if self._client is None or not self._client.is_connected():
                # Создаем клиент с указанным именем сессии
                self._client = TelegramClient(
                    self.session_path, 
                    self.api_id, 
                    self.api_hash, 
                    device_model="Telegram Analytics",
                    system_version="1.0",
                    app_version="1.0",
                    timeout=30  # Увеличенный таймаут для операций
                )
            
            if not self._client.is_connected():
                try:
                    await self._client.connect()
                    logger.info(f"Клиент Telegram подключен успешно")
                except Exception as e:
                    logger.error(f"Ошибка при подключении клиента Telegram: {str(e)}")
                    # Повторим попытку один раз после короткой задержки
                    await asyncio.sleep(1)
                    try:
                        await self._client.connect()
                    except Exception as e2:
                        logger.error(f"Повторная ошибка при подключении: {str(e2)}")
                        raise
            
            return self._client
    
    async def _disconnect_client(self):
        """Отключение клиента Telegram API с синхронизацией"""
        async with self._session_lock:
            if self._client and self._client.is_connected():
                try:
                    await self._client.disconnect()
                    logger.info("Клиент Telegram отключен успешно")
                except Exception as e:
                    logger.error(f"Ошибка при отключении клиента Telegram: {str(e)}")
                self._client = None
    
    async def check_authorization(self) -> bool:
        """
        Проверка статуса авторизации
        
        Returns:
            True если авторизация выполнена, иначе False
        """
        try:
            client = await self._get_client()
            is_authorized = await client.is_user_authorized()
            return is_authorized
        except Exception as e:
            logger.error(f"Ошибка при проверке авторизации: {str(e)}")
            return False
        finally:
            # Не отключаем клиент сразу, пусть работает механизм управления сессией
            pass
    
    async def start_auth_process(self, phone: str) -> Dict[str, Any]:
        """
        Начало процесса авторизации с отправкой кода
        
        Args:
            phone: Номер телефона для авторизации
            
        Returns:
            Словарь с результатом операции
        """
        # Очищаем старые файлы сессий
        await self.clear_session()
        
        try:
            client = await self._get_client()
            
            # Подготавливаем данные сессии
            session_id = str(int(time.time()))
            session_data = {
                'phone': phone,
                'timestamp': time.time(),
                'step': 'phone_sent'
            }
            
            # Отправляем запрос кода
            try:
                phone_code_hash = await self._send_code_request(client, phone)
                if phone_code_hash:
                    session_data['phone_code_hash'] = phone_code_hash
                    
                    # Сохраняем данные сессии
                    session_file = os.path.join(SESSION_DIR, f"session_{session_id}.json")
                    with open(session_file, 'w') as f:
                        json.dump(session_data, f)
                    
                    return {
                        'status': 'success',
                        'session_id': session_id,
                        'message': 'Код авторизации отправлен'
                    }
                else:
                    return {
                        'status': 'error',
                        'error': 'Не удалось получить phone_code_hash'
                    }
            except FloodWaitError as e:
                return {
                    'status': 'error',
                    'error': f'Слишком много запросов. Попробуйте снова через {e.seconds} секунд'
                }
            except Exception as e:
                return {
                    'status': 'error',
                    'error': f'Ошибка при отправке кода: {str(e)}'
                }
        except Exception as e:
            logger.error(f"Ошибка при начале процесса авторизации: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
        finally:
            await self._disconnect_client()
    
    async def _send_code_request(self, client: TelegramClient, phone: str) -> Optional[str]:
        """
        Отправка запроса на код подтверждения
        
        Args:
            client: Клиент Telegram API
            phone: Номер телефона
            
        Returns:
            Хэш кода подтверждения или None в случае ошибки
        """
        try:
            # Отправляем запрос на получение кода
            logger.info(f"Отправка запроса кода на номер {phone}")
            sent_code = await client.send_code_request(phone)
            logger.info(f"Код отправлен успешно")
            return sent_code.phone_code_hash
        except Exception as e:
            logger.error(f"Ошибка при отправке запроса кода: {str(e)}")
            raise
    
    async def verify_code(self, session_id: str, code: str, phone: str) -> Dict[str, Any]:
        """
        Проверка кода подтверждения
        
        Args:
            session_id: ID сессии авторизации
            code: Код подтверждения
            phone: Номер телефона
            
        Returns:
            Словарь с результатом операции
        """
        try:
            # Загружаем данные сессии
            session_file = os.path.join(SESSION_DIR, f"session_{session_id}.json")
            if not os.path.exists(session_file):
                return {
                    'status': 'error',
                    'error': 'Сессия не найдена или истекла'
                }
            
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # Проверяем срок действия сессии (30 минут)
            if time.time() - session_data.get('timestamp', 0) > 1800:
                os.remove(session_file)
                return {
                    'status': 'error',
                    'error': 'Сессия истекла, начните процесс авторизации заново'
                }
            
            # Проверяем код
            client = await self._get_client()
            
            phone_code_hash = session_data.get('phone_code_hash')
            if not phone_code_hash:
                logger.warning("phone_code_hash отсутствует в данных сессии")
                
            try:
                # Попытка входа с кодом
                logger.info(f"Попытка входа с кодом {code} для номера {phone}")
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                
                # Проверяем результат
                is_authorized = await client.is_user_authorized()
                
                if is_authorized:
                    # Очищаем временный файл сессии
                    os.remove(session_file)
                    
                    return {
                        'status': 'success',
                        'message': 'Авторизация успешно завершена'
                    }
                else:
                    return {
                        'status': 'error',
                        'error': 'Авторизация не удалась, несмотря на успешную отправку кода'
                    }
                
            except PhoneCodeExpiredError:
                # Код истек, нужно запросить новый
                return {
                    'status': 'code_expired',
                    'error': 'Код подтверждения истек. Пожалуйста, запросите новый код'
                }
                
            except PhoneCodeInvalidError:
                # Неверный код
                return {
                    'status': 'code_invalid',
                    'error': 'Неверный код подтверждения. Пожалуйста, проверьте и попробуйте снова'
                }
                
            except SessionPasswordNeededError:
                # Требуется двухфакторная аутентификация
                # Обновляем данные сессии
                session_data['step'] = '2fa_required'
                
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)
                
                return {
                    'status': '2fa_required',
                    'message': 'Требуется двухфакторная аутентификация',
                    'session_id': session_id
                }
                
            except AuthRestartError:
                # Требуется перезапуск авторизации
                if os.path.exists(session_file):
                    os.remove(session_file)
                    
                return {
                    'status': 'restart_auth',
                    'error': 'Требуется перезапуск авторизации. Пожалуйста, начните процесс заново'
                }
                
            except Exception as e:
                logger.error(f"Ошибка при проверке кода: {str(e)}")
                return {
                    'status': 'error',
                    'error': str(e)
                }
                
        except Exception as e:
            logger.error(f"Общая ошибка при проверке кода: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
        finally:
            await self._disconnect_client()
    
    async def verify_2fa_password(self, session_id: str, password: str) -> Dict[str, Any]:
        """
        Проверка пароля двухфакторной аутентификации
        
        Args:
            session_id: ID сессии авторизации
            password: Пароль 2FA
            
        Returns:
            Словарь с результатом операции
        """
        try:
            # Загружаем данные сессии
            session_file = os.path.join(SESSION_DIR, f"session_{session_id}.json")
            if not os.path.exists(session_file):
                return {
                    'status': 'error',
                    'error': 'Сессия не найдена или истекла'
                }
            
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # Проверяем срок действия сессии (30 минут)
            if time.time() - session_data.get('timestamp', 0) > 1800:
                os.remove(session_file)
                return {
                    'status': 'error',
                    'error': 'Сессия истекла, начните процесс авторизации заново'
                }
            
            # Проверяем, находимся ли на этапе 2FA
            if session_data.get('step') != '2fa_required':
                return {
                    'status': 'error',
                    'error': 'Некорректное состояние сессии'
                }
            
            # Проверяем пароль 2FA
            client = await self._get_client()
            
            try:
                # Попытка входа с паролем 2FA
                logger.info("Попытка входа с паролем 2FA")
                await client.sign_in(password=password)
                
                # Проверяем результат
                is_authorized = await client.is_user_authorized()
                
                if is_authorized:
                    # Очищаем временный файл сессии при успешной авторизации
                    if os.path.exists(session_file):
                        os.remove(session_file)
                    
                    return {
                        'status': 'success',
                        'message': 'Авторизация успешно завершена'
                    }
                else:
                    return {
                        'status': 'error',
                        'error': 'Авторизация не удалась, несмотря на успешную отправку пароля'
                    }
                
            except Exception as e:
                logger.error(f"Ошибка при проверке пароля 2FA: {str(e)}")
                return {
                    'status': 'error',
                    'error': f'Ошибка при проверке пароля: {str(e)}'
                }
                
        except Exception as e:
            logger.error(f"Общая ошибка при проверке пароля 2FA: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
        finally:
            await self._disconnect_client()
    
    async def clear_session(self, remove_session_file: bool = True) -> Dict[str, Any]:
        """
        Полная очистка сессии и отключение клиента
        
        Args:
            remove_session_file: Удалять ли файл сессии Telegram
            
        Returns:
            Словарь с результатом операции
        """
        try:
            # Отключаем клиент, если он подключен
            await self._disconnect_client()
            
            # Удаляем файл сессии, если он существует и указан флаг удаления
            if remove_session_file и os.path.exists(self.session_path):
                # Подождем немного для освобождения файлов
                await asyncio.sleep(0.5)
                
                try:
                    # Сначала пробуем просто удалить файл
                    os.remove(self.session_path)
                    logger.info(f"Сессия Telegram успешно удалена: {self.session_path}")
                except (PermissionError, OSError) as e:
                    # Если не удалось удалить, пробуем сначала переименовать
                    logger.warning(f"Не удалось напрямую удалить файл сессии: {str(e)}")
                    try:
                        temp_path = f"{self.session_path}.old"
                        shutil.move(self.session_path, temp_path)
                        os.remove(temp_path)
                        logger.info(f"Сессия Telegram успешно удалена через переименование")
                    except Exception as e2:
                        logger.error(f"Не удалось удалить файл сессии даже после переименования: {str(e2)}")
            
            # Удаляем временные файлы сессий
            for filename in os.listdir(SESSION_DIR):
                if filename.startswith('session_') and filename.endswith('.json'):
                    file_path = os.path.join(SESSION_DIR, filename)
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить временный файл сессии {file_path}: {str(e)}")
            
            return {
                'status': 'success',
                'message': 'Сессия успешно очищена'
            }
        except Exception as e:
            logger.error(f"Ошибка при очистке сессии: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }


# Простой интерфейс для использования в Flask
class TelegramAuth:
    """Фасад для использования TelegramAuthHandler в Flask"""
    
    @staticmethod
    async def check_auth_status() -> Dict[str, Any]:
        """Проверка статуса авторизации"""
        handler = TelegramAuthHandler()
        client = None
        try:
            client = await handler._get_client()
            is_authorized = await client.is_user_authorized()
            session_exists = os.path.exists(f"{SESSION_FILE}.session") and is_authorized
            
            return {
                'status': 'success',
                'is_authorized': is_authorized,
                'session_exists': session_exists
            }
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса авторизации: {str(e)}")
            return {
                'status': 'error',
                'is_authorized': False,
                'session_exists': False
            }
        finally:
            # Обязательно отключить клиент в любом случае
            if client and client.is_connected():
                await client.disconnect()
    
    @staticmethod
    async def start_auth(phone: str) -> Dict[str, Any]:
        """Запуск процесса авторизации"""
        handler = TelegramAuthHandler()
        return await handler.start_auth_process(phone)
    
    @staticmethod
    async def verify_code(session_id: str, code: str, phone: str) -> Dict[str, Any]:
        """Проверка кода подтверждения"""
        handler = TelegramAuthHandler()
        return await handler.verify_code(session_id, code, phone)
    
    @staticmethod
    async def verify_2fa(session_id: str, password: str) -> Dict[str, Any]:
        """Проверка пароля 2FA"""
        handler = TelegramAuthHandler()
        return await handler.verify_2fa_password(session_id, password)
    
    @staticmethod
    async def reset_session() -> Dict[str, Any]:
        """Сброс сессии"""
        handler = TelegramAuthHandler()
        return await handler.clear_session()


# Для тестирования
async def main():
    """Тестирование модуля авторизации"""
    # Проверка наличия API ключей
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    
    if not api_id или not api_hash:
        logger.error("API ID или Hash не указаны. Пожалуйста, добавьте их в файл .env")
        sys.exit(1)
    
    # Простой интерактивный тест
    auth_handler = TelegramAuthHandler()
    
    # Проверяем текущий статус авторизации
    is_authorized = await auth_handler.check_authorization()
    logger.info(f"Текущий статус авторизации: {'авторизован' if is_authorized else 'не авторизован'}")
    
    if is_authorized:
        logger.info("Вы уже авторизованы. Хотите сбросить сессию? (y/n)")
        response = input().lower()
        if response == 'y':
            result = await auth_handler.clear_session()
            logger.info(f"Результат сброса сессии: {result}")
        else:
            logger.info("Тест завершен.")
            return
    
    # Запрашиваем номер телефона
    logger.info("Введите ваш номер телефона (с кодом страны, например +7XXXXXXXXXX):")
    phone = input()
    
    # Запускаем процесс авторизации
    result = await auth_handler.start_auth_process(phone)
    logger.info(f"Результат запуска авторизации: {result}")
    
    if result['status'] != 'success':
        logger.error("Не удалось начать процесс авторизации. Тест завершен.")
        return
    
    session_id = result['session_id']
    
    # Запрашиваем код подтверждения
    logger.info("Введите код подтверждения, который вы получили:")
    code = input()
    
    # Проверяем код
    result = await auth_handler.verify_code(session_id, code, phone)
    logger.info(f"Результат проверки кода: {result}")
    
    if result['status'] == '2fa_required':
        # Запрашиваем пароль 2FA
        logger.info("Требуется двухфакторная аутентификация. Введите ваш пароль:")
        password = input()
        
        # Проверяем пароль 2FA
        result = await auth_handler.verify_2fa_password(session_id, password)
        logger.info(f"Результат проверки пароля 2FA: {result}")
    
    # Проверяем итоговый статус авторизации
    is_authorized = await auth_handler.check_authorization()
    logger.info(f"Итоговый статус авторизации: {'авторизован' if is_authorized else 'не авторизован'}")
    
    logger.info("Тест завершен.")

if __name__ == "__main__":
    asyncio.run(main())
