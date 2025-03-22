import os
import logging
import time
from telethon import TelegramClient as TelethonClient
from telethon.errors import FloodWaitError, ChatAdminRequiredError
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Настройка логирования
logger = logging.getLogger(__name__)

class TelegramClient:
    """Класс для работы с Telegram API через Telethon"""
    
    def __init__(self):
        """Инициализация клиента Telegram API"""
        self.api_id = int(os.getenv('TELEGRAM_API_ID', 0))
        self.api_hash = os.getenv('TELEGRAM_API_HASH', '')
        self.client = None
        
    async def _connect(self):
        """Подключение к Telegram API"""
        if self.client is None or not self.client.is_connected():
            logger.info("Установка соединения с Telegram API...")
            
            # Создание клиента с именем сессии 'telegram_analytics'
            self.client = TelethonClient('telegram_analytics', self.api_id, self.api_hash)
            
            # Подключение к Telegram API
            await self.client.connect()
            
            # Проверка авторизации
            if not await self.client.is_user_authorized():
                logger.error("Телефон не авторизован. Требуется авторизация через phone_login.py")
                raise Exception("Не удалось авторизоваться в Telegram API. Запустите скрипт phone_login.py")
                
            logger.info("Соединение установлено успешно")
    
    async def _disconnect(self):
        """Отключение от Telegram API"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            self.client = None
    
    async def get_channel_info(self, channel_identifier: str) -> Dict[str, Any]:
        """
        Получение информации о канале по его username или ID
        
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
    
    async def get_posts(self, channel_identifier: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Получение постов канала за указанный период
        
        Args:
            channel_identifier: Username канала (с @ или без) или его ID
            days: Количество дней для выборки постов (по умолчанию 30)
            
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
            total_posts = None  # Узнаем после первой итерации
            
            logger.info(f"Получение постов за последние {days} дней...")
            
            async for message in self.client.iter_messages(entity, offset_date=start_date, reverse=True):
                if not total_posts:
                    # Примерная оценка количества постов
                    total_posts = message.id
                    
                # Пропуск служебных сообщений
                if message.action:
                    continue
                
                # Добавление поста в список
                post = {
                    'id': message.id,
                    'channel_id': entity.id,
                    'date': message.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'text': message.text or '',
                    'views': getattr(message, 'views', 0),
                    'forwards': getattr(message, 'forwards', 0),
                    'replies': getattr(message, 'replies', {}).get('replies', 0) if hasattr(message, 'replies') else 0,
                    'has_media': bool(message.media),
                    'media_type': self._get_media_type(message),
                    'is_pinned': message.pinned
                }
                
                posts.append(post)
                post_count += 1
                
                # Логирование прогресса
                if post_count % 10 == 0 or post_count == total_posts:
                    progress = (post_count / total_posts * 100) if total_posts else 0
                    logger.info(f"Загрузка постов: {post_count}/{total_posts} ({int(progress)}%)")
                
                # Задержка для избежания ограничений API
                if post_count % 100 == 0:
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
    
    def _get_media_type(self, message) -> Optional[str]:
        """Определение типа медиа в сообщении"""
        if not message.media:
            return None
        
        media_type = type(message.media).__name__
        return media_type.replace('MessageMedia', '').lower()
    
    async def get_comments(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Получение комментариев к постам
        
        Args:
            posts: Список постов, для которых нужно получить комментарии
            
        Returns:
            Список словарей с информацией о комментариях
        """
        try:
            await self._connect()
            
            comments = []
            total_comments = 0
            processed_comments = 0
            
            # Для каждого поста получаем комментарии
            for post in posts:
                try:
                    # Получение обсуждения для поста
                    channel_id = post['channel_id']
                    post_id = post['id']
                    
                    # Получение комментариев
                    async for comment in self.client.iter_messages(
                        entity=channel_id,
                        reply_to=post_id
                    ):
                        # Формирование структуры комментария
                        comment_data = {
                            'id': comment.id,
                            'post_id': post_id,
                            'channel_id': channel_id,
                            'user_id': comment.from_id.user_id if hasattr(comment.from_id, 'user_id') else None,
                            'date': comment.date.strftime('%Y-%m-%d %H:%M:%S'),
                            'text': comment.text or '',
                            'likes': 0,  # К сожалению, API не предоставляет количество лайков
                            'is_reply': bool(comment.reply_to_msg_id)
                        }
                        
                        comments.append(comment_data)
                        total_comments += 1
                        
                except (ChatAdminRequiredError, ValueError):
                    # Для некоторых каналов невозможно получить комментарии без прав администратора
                    continue
                
                processed_comments += 1
                
                # Логирование прогресса
                if processed_comments % 10 == 0 or processed_comments == len(posts):
                    logger.info(f"Получение комментариев: обработано {processed_comments}/{len(posts)} постов")
                
                # Задержка для избежания ограничений API
                if processed_comments % 50 == 0:
                    time.sleep(1)
            
            logger.info(f"Всего загружено {total_comments} комментариев")
            return comments
            
        except FloodWaitError as e:
            # Обработка ограничения API
            logger.warning(f"Достигнут лимит запросов. Требуется ожидание {e.seconds} секунд.")
            raise
            
        except Exception as e:
            logger.error(f"Ошибка при получении комментариев: {str(e)}")
            raise
            
        finally:
            await self._disconnect()

# Импорт необходимых классов Telethon для полного доступа к каналу
from telethon.tl.functions.channels import GetFullChannelRequest