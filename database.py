import os
import logging
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Настройка логирования
logger = logging.getLogger(__name__)

class Database:
    """Класс для работы с базой данных SQLite"""
    
    def __init__(self, db_path: str = 'data/telegram_analytics.db'):
        """
        Инициализация подключения к базе данных
        
        Args:
            db_path: Путь к файлу базы данных
        """
        # Создание директории для БД, если не существует
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_path = db_path
        self.conn = None
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Получение подключения к базе данных
        
        Returns:
            Объект подключения к базе данных
        """
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Для получения результатов в виде словарей
        
        return self.conn
    
    def _close_connection(self):
        """Закрытие подключения к базе данных"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def init_db(self):
        """Инициализация структуры базы данных"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Таблица для информации о каналах
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                name TEXT NOT NULL,
                username TEXT,
                description TEXT,
                subscribers INTEGER,
                date_created TEXT,
                photo_url TEXT,
                is_private BOOLEAN,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Таблица для постов
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                channel_id INTEGER,
                date TEXT,
                text TEXT,
                views INTEGER,
                forwards INTEGER,
                replies INTEGER,
                has_media BOOLEAN,
                media_type TEXT,
                is_pinned BOOLEAN,
                FOREIGN KEY (channel_id) REFERENCES channels (id)
            )
            ''')
            
            # Таблица для комментариев
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                post_id INTEGER,
                channel_id INTEGER,
                user_id INTEGER,
                date TEXT,
                text TEXT,
                likes INTEGER,
                is_reply BOOLEAN,
                FOREIGN KEY (post_id) REFERENCES posts (id),
                FOREIGN KEY (channel_id) REFERENCES channels (id)
            )
            ''')
            
            # Таблица для отчетов
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                prompt TEXT,
                response TEXT,
                metrics TEXT,
                FOREIGN KEY (channel_id) REFERENCES channels (id)
            )
            ''')
            
            # Таблица для шаблонов промптов
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS prompt_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                level TEXT NOT NULL,
                template TEXT NOT NULL,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            conn.commit()
            logger.info("База данных инициализирована успешно")
            
            # Добавление стандартных шаблонов промптов, если их нет
            self._add_default_templates()
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации БД: {str(e)}")
            raise
            
        finally:
            self._close_connection()
    
    def _add_default_templates(self):
        """Добавление стандартных шаблонов промптов, если их нет в БД"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Проверка наличия шаблонов
        cursor.execute("SELECT COUNT(*) FROM prompt_templates")
        count = cursor.fetchone()[0]
        
        if count == 0:
            default_templates = [
                {
                    'name': 'Системный шаблон',
                    'description': 'Основной системный шаблон для определения роли и формата ответа',
                    'level': 'system',
                    'template': '''
                    Ты - опытный аналитик Telegram-каналов с многолетним опытом в контент-стратегии
                    и маркетинговой аналитике. Твоя задача - провести глубокий анализ Telegram-канала
                    на основе предоставленных данных и предложить конкретные рекомендации для улучшения
                    контент-стратегии, роста вовлечённости и увеличения аудитории.
                    
                    Твой анализ должен быть:
                    1. Структурированным и разделенным на логические разделы
                    2. Основанным на фактических данных и метриках
                    3. Содержать конкретные и применимые рекомендации
                    4. Написанным понятным языком с минимумом маркетинговых терминов
                    '''
                },
                {
                    'name': 'Контекстуальный шаблон',
                    'description': 'Шаблон для передачи контекста о канале',
                    'level': 'context',
                    'template': '''
                    Канал: {channel_name}
                    Описание: {channel_description}
                    Количество подписчиков: {subscribers}
                    Тематика: {channel_topic}
                    Активен: {days_active} дней
                    
                    Период анализа: последние {analysis_period} дней
                    
                    Исследуемый канал относится к категории {size_category} каналов в Telegram.
                    Средний пост получает {avg_views} просмотров, {avg_engagement} вовлечённости.
                    '''
                },
                {
                    'name': 'Инструкционный шаблон',
                    'description': 'Шаблон с инструкциями для LLM',
                    'level': 'instruction',
                    'template': '''
                    Проведи комплексный анализ предоставленных данных о Telegram-канале "{channel_name}".
                    
                    В своем анализе:
                    
                    1. Оцени общую эффективность канала
                       - Как изменилась аудитория и вовлечённость за период анализа?
                       - Какие ключевые метрики показывают потенциал для роста?
                    
                    2. Выяви сильные и слабые стороны контент-стратегии
                       - Какие типы постов получают наибольшее вовлечение?
                       - Какие темы привлекают больше внимания аудитории?
                       - Какая оптимальная длина постов для этого канала?
                    
                    3. Проанализируй поведение аудитории
                       - Когда аудитория наиболее активна?
                       - Как аудитория реагирует на разные типы контента?
                       - Какие паттерны комментирования наблюдаются?
                    
                    4. Предложи конкретные рекомендации
                       - По улучшению контент-стратегии
                       - По оптимизации графика публикаций
                       - По увеличению вовлечённости аудитории
                       - По эксперименту с новыми форматами
                    '''
                },
                {
                    'name': 'Шаблон данных',
                    'description': 'Шаблон для передачи аналитических данных',
                    'level': 'data',
                    'template': '''
                    СТАТИСТИКА КАНАЛА:
                    {channel_metrics}
                    
                    АНАЛИЗ ПОСТОВ:
                    {post_metrics}
                    
                    АНАЛИЗ КОММЕНТАРИЕВ:
                    {comment_analysis}
                    
                    АНАЛИЗ КОНТЕНТА:
                    {content_analysis}
                    
                    АНАЛИЗ ВРЕМЕНИ ПУБЛИКАЦИИ:
                    {time_analysis}
                    '''
                }
            ]
            
            for template in default_templates:
                cursor.execute('''
                INSERT INTO prompt_templates (name, description, level, template)
                VALUES (?, ?, ?, ?)
                ''', (
                    template['name'],
                    template['description'],
                    template['level'],
                    template['template']
                ))
            
            conn.commit()
            logger.info("Добавлены стандартные шаблоны промптов")
    
    def save_channel_info(self, channel_info: Dict[str, Any]) -> int:
        """
        Сохранение информации о канале в базу данных
        
        Args:
            channel_info: Информация о канале
            
        Returns:
            ID канала в базе данных
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Проверка, существует ли канал с таким telegram_id
            cursor.execute(
                "SELECT id FROM channels WHERE telegram_id = ?",
                (channel_info.get('id'),)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Обновление существующего канала
                cursor.execute('''
                UPDATE channels 
                SET name = ?, username = ?, description = ?, subscribers = ?, 
                    date_created = ?, photo_url = ?, is_private = ?
                WHERE telegram_id = ?
                ''', (
                    channel_info.get('name'),
                    channel_info.get('username'),
                    channel_info.get('description'),
                    channel_info.get('subscribers'),
                    channel_info.get('date_created'),
                    channel_info.get('photo_url'),
                    channel_info.get('is_private', False),
                    channel_info.get('id')
                ))
                conn.commit()
                return existing['id']
            else:
                # Добавление нового канала
                cursor.execute('''
                INSERT INTO channels 
                (telegram_id, name, username, description, subscribers, date_created, photo_url, is_private)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    channel_info.get('id'),
                    channel_info.get('name'),
                    channel_info.get('username'),
                    channel_info.get('description'),
                    channel_info.get('subscribers'),
                    channel_info.get('date_created'),
                    channel_info.get('photo_url'),
                    channel_info.get('is_private', False)
                ))
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"Ошибка при сохранении информации о канале: {str(e)}")
            raise
    
    def save_posts(self, posts: List[Dict[str, Any]], channel_id: int):
        """
        Сохранение постов в базу данных
        
        Args:
            posts: Список постов
            channel_id: ID канала в базе данных
        """
        if not posts:
            return
            
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for post in posts:
                # Проверка существования поста
                cursor.execute(
                    "SELECT id FROM posts WHERE telegram_id = ? AND channel_id = ?",
                    (post.get('id'), channel_id)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Обновление существующего поста
                    cursor.execute('''
                    UPDATE posts 
                    SET date = ?, text = ?, views = ?, forwards = ?, replies = ?,
                        has_media = ?, media_type = ?, is_pinned = ?
                    WHERE telegram_id = ? AND channel_id = ?
                    ''', (
                        post.get('date'),
                        post.get('text'),
                        post.get('views'),
                        post.get('forwards'),
                        post.get('replies'),
                        post.get('has_media', False),
                        post.get('media_type'),
                        post.get('is_pinned', False),
                        post.get('id'),
                        channel_id
                    ))
                else:
                    # Добавление нового поста
                    cursor.execute('''
                    INSERT INTO posts
                    (telegram_id, channel_id, date, text, views, forwards, replies, has_media, media_type, is_pinned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        post.get('id'),
                        channel_id,
                        post.get('date'),
                        post.get('text'),
                        post.get('views'),
                        post.get('forwards'),
                        post.get('replies'),
                        post.get('has_media', False),
                        post.get('media_type'),
                        post.get('is_pinned', False)
                    ))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении постов: {str(e)}")
            raise
    
    def save_comments(self, comments: List[Dict[str, Any]]):
        """
        Сохранение комментариев в базу данных
        
        Args:
            comments: Список комментариев
        """
        if not comments:
            return
            
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for comment in comments:
                # Получение внутреннего ID поста
                cursor.execute(
                    "SELECT id FROM posts WHERE telegram_id = ? AND channel_id = (SELECT id FROM channels WHERE telegram_id = ?)",
                    (comment.get('post_id'), comment.get('channel_id'))
                )
                post = cursor.fetchone()
                
                if not post:
                    # Пропускаем комментарии к несуществующим постам
                    continue
                
                post_id = post['id']
                
                # Проверка существования комментария
                cursor.execute(
                    "SELECT id FROM comments WHERE telegram_id = ? AND post_id = ?",
                    (comment.get('id'), post_id)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Обновление существующего комментария
                    cursor.execute('''
                    UPDATE comments 
                    SET user_id = ?, date = ?, text = ?, likes = ?, is_reply = ?
                    WHERE telegram_id = ? AND post_id = ?
                    ''', (
                        comment.get('user_id'),
                        comment.get('date'),
                        comment.get('text'),
                        comment.get('likes', 0),
                        comment.get('is_reply', False),
                        comment.get('id'),
                        post_id
                    ))
                else:
                    # Добавление нового комментария
                    cursor.execute('''
                    INSERT INTO comments
                    (telegram_id, post_id, channel_id, user_id, date, text, likes, is_reply)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        comment.get('id'),
                        post_id,
                        comment.get('channel_id'),
                        comment.get('user_id'),
                        comment.get('date'),
                        comment.get('text'),
                        comment.get('likes', 0),
                        comment.get('is_reply', False)
                    ))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении комментариев: {str(e)}")
            raise
    
    def save_report(self, channel_id: int, file_path: str, prompt: Dict[str, Any], 
                  response: str) -> int:
        """
        Сохранение отчета в базу данных
        
        Args:
            channel_id: ID канала
            file_path: Путь к файлу отчета
            prompt: Промпт, использованный для генерации отчета
            response: Ответ LLM
            
        Returns:
            ID созданного отчета
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Сериализация промпта в JSON
            prompt_json = json.dumps(prompt, ensure_ascii=False)
            
            # Сохранение отчета
            cursor.execute('''
            INSERT INTO reports (channel_id, file_path, prompt, response)
            VALUES (?, ?, ?, ?)
            ''', (
                channel_id,
                file_path,
                prompt_json,
                response
            ))
            
            conn.commit()
            return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении отчета: {str(e)}")
            raise
    
    def get_channel_info(self, channel_id: int) -> Dict[str, Any]:
        """
        Получение информации о канале
        
        Args:
            channel_id: ID канала в базе данных
            
        Returns:
            Словарь с информацией о канале
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM channels WHERE id = ?",
                (channel_id,)
            )
            
            channel = cursor.fetchone()
            
            if channel:
                # Преобразование объекта Row в словарь
                return dict(channel)
            
            return {}
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о канале: {str(e)}")
            return {}
    
    def get_posts(self, channel_id: int) -> List[Dict[str, Any]]:
        """
        Получение всех постов канала
        
        Args:
            channel_id: ID канала в базе данных
            
        Returns:
            Список постов
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM posts WHERE channel_id = ? ORDER BY date DESC",
                (channel_id,)
            )
            
            posts = cursor.fetchall()
            
            # Преобразование списка объектов Row в список словарей
            return [dict(post) for post in posts]
            
        except Exception as e:
            logger.error(f"Ошибка при получении постов: {str(e)}")
            return []
    
    def get_comments_for_posts(self, post_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Получение комментариев для указанных постов
        
        Args:
            post_ids: Список ID постов
            
        Returns:
            Список комментариев
        """
        if not post_ids:
            return []
            
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Формирование списка плейсхолдеров для SQL запроса
            placeholders = ', '.join(['?'] * len(post_ids))
            
            cursor.execute(
                f"SELECT * FROM comments WHERE post_id IN ({placeholders}) ORDER BY date ASC",
                post_ids
            )
            
            comments = cursor.fetchall()
            
            # Преобразование списка объектов Row в список словарей
            return [dict(comment) for comment in comments]
            
        except Exception as e:
            logger.error(f"Ошибка при получении комментариев: {str(e)}")
            return []
    
    def get_report(self, report_id: int) -> Dict[str, Any]:
        """
        Получение отчета по его ID
        
        Args:
            report_id: ID отчета
            
        Returns:
            Словарь с данными отчета
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Получение отчета
            cursor.execute(
                "SELECT * FROM reports WHERE id = ?",
                (report_id,)
            )
            
            report = cursor.fetchone()
            
            if not report:
                return {}
            
            # Преобразование в словарь
            report_dict = dict(report)
            
            # Получение информации о канале
            channel = self.get_channel_info(report_dict['channel_id'])
            report_dict['channel_name'] = channel.get('name', '')
            
            return report_dict
            
        except Exception as e:
            logger.error(f"Ошибка при получении отчета: {str(e)}")
            return {}
    
    def get_all_reports(self) -> List[Dict[str, Any]]:
        """
        Получение всех сохраненных отчетов
        
        Returns:
            Список отчетов
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT r.*, c.name as channel_name 
            FROM reports r 
            JOIN channels c ON r.channel_id = c.id 
            ORDER BY r.date DESC
            """)
            
            reports = cursor.fetchall()
            
            # Преобразование списка объектов Row в список словарей
            return [dict(report) for report in reports]
            
        except Exception as e:
            logger.error(f"Ошибка при получении всех отчетов: {str(e)}")
            return []
    
    def get_prompt_templates(self) -> List[Dict[str, Any]]:
        """
        Получение всех шаблонов промптов
        
        Returns:
            Список шаблонов
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM prompt_templates ORDER BY level, name")
            
            templates = cursor.fetchall()
            
            # Преобразование списка объектов Row в список словарей
            return [dict(template) for template in templates]
            
        except Exception as e:
            logger.error(f"Ошибка при получении шаблонов промптов: {str(e)}")
            return []
    
    def get_prompt_template(self, template_id: int) -> Dict[str, Any]:
        """
        Получение шаблона промпта по ID
        
        Args:
            template_id: ID шаблона
            
        Returns:
            Словарь с данными шаблона
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM prompt_templates WHERE id = ?",
                (template_id,)
            )
            
            template = cursor.fetchone()
            
            if template:
                return dict(template)
            
            return {}
            
        except Exception as e:
            logger.error(f"Ошибка при получении шаблона промпта: {str(e)}")
            return {}
    
    def update_prompt_template(self, template_id: int, template_text: str) -> bool:
        """
        Обновление шаблона промпта
        
        Args:
            template_id: ID шаблона
            template_text: Новый текст шаблона
            
        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE prompt_templates SET template = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                (template_text, template_id)
            )
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении шаблона промпта: {str(e)}")
            return False