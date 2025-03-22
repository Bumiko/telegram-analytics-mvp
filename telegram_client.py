import os
import logging
import time
import asyncio
from telethon import TelegramClient as TelethonClient
from telethon.errors import FloodWaitError, ChatAdminRequiredError, MessageIdInvalidError
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

# Настройка логирования
logger = logging.getLogger(__name__)

# Абсолютный путь к директории проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, 'telegram_analytics_bot')

class TelegramClient:
    """Класс для работы с Telegram API через Telethon"""
    
    def __init__(self):
        """Инициализация клиента Telegram API"""
        self.api_id = int(os.getenv('TELEGRAM_API_ID', 0))
        self.api_hash = os.getenv('TELEGRAM_API_HASH', '')
        self.client = None
        self.SESSION_FILE = SESSION_FILE  # Сделать SESSION_FILE доступным как свойство класса
        logger.info(f"Используется файл сессии: {SESSION_FILE}")
    
    def _run_async(self, coro):
        """Запускает корутину в синхронном контексте, создавая новый цикл событий при необходимости"""
        try:
            # Попытка получить текущий цикл событий
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Если цикла нет, создаем новый
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
    
    async def _connect(self):
        """Подключение к Telegram API"""
        if self.client is None or not self.client.is_connected():
            logger.info("Установка соединения с Telegram API...")
            
            # Создание клиента с именем сессии 'telegram_analytics_bot' и device_model
            self.client = TelethonClient(SESSION_FILE, self.api_id, self.api_hash, device_model="Analytics Tool")
            
            # Подключение к Telegram API
            await self.client.connect()
            
            # Проверка авторизации
            if not await self.client.is_user_authorized():
                logger.error("Телефон не авторизован. Требуется авторизация через веб-интерфейс или phone_login.py")
                raise Exception("Не удалось авторизоваться в Telegram API. Перейдите на страницу /initialize для авторизации")
                
            logger.info("Соединение установлено успешно")
    
    async def _disconnect(self):
        """Отключение от Telegram API"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            self.client = None
    
    async def _get_channel_info_and_posts_async(self, channel_identifier: str, days: int = 180) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Получение информации о канале и его постах за один раз
        
        Args:
            channel_identifier: Username канала (с @ или без) или его ID
            days: Количество дней для выборки постов
            
        Returns:
            Кортеж (channel_info, posts)
        """
        try:
            await self._connect()
            
            # Получение информации о канале
            logger.info(f"Получение информации о канале {channel_identifier}...")
            entity = await self.client.get_entity(channel_identifier)
            
            # Получение полной информации
            full_entity = await self.client(GetFullChannelRequest(entity))
            
            # Формирование структуры данных о канале
            channel_info = {
                'id': entity.id,
                'name': entity.title,
                'username': entity.username,
                'description': full_entity.full_chat.about,
                'subscribers': full_entity.full_chat.participants_count,
                'date_created': entity.date.strftime('%Y-%m-%d'),
                'photo_url': None,
                'is_private': getattr(entity, 'restricted', False)
            }
            
            # Получение URL фото канала, если есть
            if hasattr(entity, 'photo') and entity.photo:
                channel_info['photo_url'] = f"https://t.me/{entity.username}"
            
            # Вычисление даты начала периода
            start_date = datetime.now() - timedelta(days=days)
            
            # Получение постов
            posts = []
            post_count = 0
            total_posts = 1  # Начальное значение
            
            logger.info(f"Получение постов за последние {days} дней...")
            
            async for message in self.client.iter_messages(entity, offset_date=start_date, reverse=True):
                if post_count == 0:
                    # Примерная оценка количества постов
                    try:
                        total_posts = message.id
                    except:
                        total_posts = 100  # Примерная оценка, если не удалось получить ID
                
                # Пропуск служебных сообщений
                if message.action:
                    continue
                
                # Добавление поста в список
                post = {
                    'id': message.id,
                    'channel_id': entity.id,
                    'date': message.date.strftime('%Y-%m-%d %H:%m:%С'),
                    'text': message.text or '',
                    'views': getattr(message, 'views', 0),
                    'forwards': getattr(message, 'forwards', 0),
                    'replies': message.replies.replies if hasattr(message, 'replies') and message.replies else 0,
                    'has_media': bool(message.media),
                    'media_type': self._get_media_type(message),
                    'is_pinned': message.pinned
                }
                
                posts.append(post)
                post_count += 1
                
                # Логирование прогресса
                if post_count % 10 == 0 or post_count == 1:
                    progress = (post_count / max(total_posts, 1) * 100)
                    logger.info(f"Загрузка постов: {post_count}/{total_posts} ({int(progress)}%)")
                
                # Задержка для избежания ограничений API (менее частая)
                if post_count % 200 == 0:
                    time.sleep(1)
            
            logger.info(f"Загружено {len(posts)} постов")
            return channel_info, posts
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных канала: {str(e)}")
            raise
            
        finally:
            await self._disconnect()
    
    def get_channel_info_and_posts(self, channel_identifier: str, days: int = 180) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Синхронная обертка для получения информации о канале и его постах за один запрос
        
        Args:
            channel_identifier: Username канала (с @ или без) или его ID
            days: Количество дней для выборки постов
            
        Returns:
            Кортеж (channel_info, posts)
        """
        return self._run_async(self._get_channel_info_and_posts_async(channel_identifier, days))
    
    def _get_media_type(self, message) -> Optional[str]:
        """Определение типа медиа в сообщении"""
        if not message.media:
            return None
        
        media_type = type(message.media).__name__
        return media_type.replace('MessageMedia', '').lower()
    
    async def _get_channel_info_async(self, channel_identifier: str) -> Dict[str, Any]:
        """
        Асинхронная версия получения информации о канале
        
        Args:
            channel_identifier: Username канала (с @ или без) или его ID
            
        Returns:
            Словарь с информацией о канале
        """
        try:
            await self._connect()
            
            # Получение информации о канале
            logger.info(f"Получение информации о канале {channel_identifier}...")
            entity = await self.client.get_entity(channel_identifier)
            
            # Получение полной информации
            full_entity = await self.client(GetFullChannelRequest(entity))
            
            # Формирование структуры данных
            channel_info = {
                'id': entity.id,
                'name': entity.title,
                'username': entity.username,
                'description': full_entity.full_chat.about,
                'subscribers': full_entity.full_chat.participants_count,
                'date_created': entity.date.strftime('%Y-%m-%d'),
                'photo_url': None,
                'is_private': getattr(entity, 'restricted', False)
            }
            
            # Получение URL фото канала, если есть
            if hasattr(entity, 'photo') and entity.photo:
                channel_info['photo_url'] = f"https://t.me/{entity.username}"
                
            return channel_info
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о канале: {str(e)}")
            raise
            
        finally:
            await self._disconnect()
    
    def get_channel_info(self, channel_identifier: str) -> Dict[str, Any]:
        """
        Синхронная обертка для получения информации о канале
        
        Args:
            channel_identifier: Username канала (с @ или без) или его ID
            
        Returns:
            Словарь с информацией о канале
        """
        return self._run_async(self._get_channel_info_async(channel_identifier))
    
    async def _get_posts_async(self, channel_identifier: str, days: int = 180) -> List[Dict[str, Any]]:
        """
        Асинхронная версия получения постов канала
        
        Args:
            channel_identifier: Username канала (с @ или без) или его ID
            days: Количество дней для выборки постов (по умолчанию 180)
            
        Returns:
            Список словарей с информацией о постах
        """
        try:
            await self._connect()
            
            # Вычисление даты начала периода
            start_date = datetime.now() - timedelta(days=days)
            
            # Получение сущности канала
            entity = await self.client.get_entity(channel_identifier)
            
            # Получение постов
            posts = []
            post_count = 0
            total_posts = 1  # Начальное значение
            
            logger.info(f"Получение постов за последние {days} дней...")
            
            async for message in self.client.iter_messages(entity, offset_date=start_date, reverse=True):
                if post_count == 0:
                    # Примерная оценка количества постов
                    try:
                        total_posts = message.id
                    except:
                        total_posts = 100  # Примерная оценка, если не удалось получить ID
                
                # Пропуск служебных сообщений
                if message.action:
                    continue
                
                # Добавление поста в список
                post = {
                    'id': message.id,
                    'channel_id': entity.id,
                    'date': message.date.strftime('%Y-%m-%d %H:%m:%С'),
                    'text': message.text or '',
                    'views': getattr(message, 'views', 0),
                    'forwards': getattr(message, 'forwards', 0),
                    'replies': message.replies.replies if hasattr(message, 'replies') and message.replies else 0,
                    'has_media': bool(message.media),
                    'media_type': self._get_media_type(message),
                    'is_pinned': message.pinned
                }
                
                posts.append(post)
                post_count += 1
                
                # Логирование прогресса
                if post_count % 10 == 0 or post_count == 1:
                    progress = (post_count / max(total_posts, 1) * 100)
                    logger.info(f"Загрузка постов: {post_count}/{total_posts} ({int(progress)}%)")
                
                # Задержка для избежания ограничений API
                if post_count % 200 == 0:
                    time.sleep(1)
            
            logger.info(f"Загружено {len(posts)} постов")
            return posts
            
        except FloodWaitError as e:
            # Обработка ограничения API
            logger.warning(f"Достигнут лимит запросов. Требуется ожидание {e.seconds} секунд.")
            raise
            
        except Exception as e:
            logger.error(f"Ошибка при получении постов: {str(e)}")
            raise
            
        finally:
            await self._disconnect()
    
    def get_posts(self, channel_identifier: str, days: int = 180) -> List[Dict[str, Any]]:
        """
        Синхронная обертка для получения постов канала
        
        Args:
            channel_identifier: Username канала (с @ или без) или его ID
            days: Количество дней для выборки постов (по умолчанию 180)
            
        Returns:
            Список словарей с информацией о постах
        """
        return self._run_async(self._get_posts_async(channel_identifier, days))
    
    async def _get_comments_async(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Асинхронная версия получения комментариев к постам
        """
        try:
            await self._connect()
            
            comments = []
            channel_entity = await self.client.get_entity(posts[0]['channel_id'])  # Получаем сущность канала
            
            for idx, post in enumerate(posts):
                try:
                    result = await self.client(GetRepliesRequest(
                        peer=channel_entity,
                        msg_id=post['id'],
                        offset_id=0,
                        offset_date=None,
                        add_offset=0,
                        limit=50,  # Ограничение на количество комментариев на пост
                        max_id=0,
                        min_id=0,
                        hash=0
                    ))

                    for comment in result.messages:
                        comments.append({
                            'id': comment.id,
                            'post_id': post['id'],
                            'channel_id': post['channel_id'],
                            'user_id': getattr(comment.from_id, 'user_id', None),
                            'date': comment.date.strftime('%Y-%m-%d %H:%m:%С'),
                            'text': comment.text or '',
                            'likes': 0,
                            'is_reply': bool(comment.reply_to_msg_id)
                        })
                    logger.info(f"[✅] Пост {post['id']}: получено {len(result.messages)} комментариев")

                except MessageIdInvalidError:
                    logger.warning(f"[⚠️] Пост {post['id']}: комментарии отключены или нет обсуждения.")
                    continue
                except FloodWaitError as e:
                    logger.warning(f"[⏳] FLOOD WAIT {e.seconds} сек... Ждём.")
                    await asyncio.sleep(e.seconds)
                    continue
                except Exception as e:
                    logger.error(f"[❌] Ошибка при посте {post['id']}: {e}")
                    continue

            logger.info(f"[✅] Всего загружено комментариев: {len(comments)}")
            return comments

        except Exception as e:
            logger.error(f"Ошибка при получении комментариев: {str(e)}")
            raise

        finally:
            await self._disconnect()
    
    def get_comments(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Синхронная обертка для получения комментариев к постам
        
        Args:
            posts: Список постов, для которых нужно получить комментарии
            
        Returns:
            Список словарей с информацией о комментариях
        """
        return self._run_async(self._get_comments_async(posts))

# Импорт необходимых классов Telethon для полного доступа к каналу
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.errors import MessageIdInvalidError, FloodWaitError
from telethon.tl.functions.messages import GetRepliesRequest
import asyncio