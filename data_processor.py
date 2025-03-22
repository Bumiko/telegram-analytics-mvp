import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from collections import Counter
import re
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk

# Настройка логирования
logger = logging.getLogger(__name__)

# Загрузка необходимых ресурсов для NLTK
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class DataProcessor:
    """Класс для предобработки собранных данных и вычисления метрик"""
    
    def __init__(self):
        """Инициализация обработчика данных"""
        self.russian_stopwords = set(stopwords.words('russian'))
        self.english_stopwords = set(stopwords.words('english'))
        self.all_stopwords = self.russian_stopwords.union(self.english_stopwords)
    
    def process_data(self, channel_info: Dict[str, Any], posts: List[Dict[str, Any]], 
                    comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Обработка данных канала и вычисление метрик
        
        Args:
            channel_info: Информация о канале
            posts: Список постов
            comments: Список комментариев
            
        Returns:
            Словарь с обработанными данными и рассчитанными метриками
        """
        logger.info("Вычисление базовых метрик...")
        
        # Преобразование в DataFrame для удобства анализа
        posts_df = pd.DataFrame(posts)
        comments_df = pd.DataFrame(comments) if comments else pd.DataFrame()
        
        # Расчет базовых метрик канала
        channel_metrics = self._calculate_channel_metrics(channel_info, posts_df)
        
        # Расчет метрик постов
        post_metrics = self._calculate_post_metrics(posts_df, comments_df)
        
        # Анализ комментариев
        comment_analysis = self._analyze_comments(comments_df)
        
        # Тематический анализ контента
        content_analysis = self._analyze_content(posts_df)
        
        # Анализ времени публикации
        time_analysis = self._analyze_posting_time(posts_df)
        
        # Агрегация всех данных в один словарь
        processed_data = {
            'channel_info': channel_info,
            'channel_metrics': channel_metrics,
            'post_metrics': post_metrics,
            'comment_analysis': comment_analysis,
            'content_analysis': content_analysis,
            'time_analysis': time_analysis,
            'raw_data': {
                'posts_count': len(posts),
                'comments_count': len(comments)
            }
        }
        
        logger.info("Предобработка данных завершена")
        return processed_data
    
    def _calculate_channel_metrics(self, channel_info: Dict[str, Any], 
                                  posts_df: pd.DataFrame) -> Dict[str, Any]:
        """Расчет общих метрик канала"""
        metrics = {}
        
        # Базовая информация
        metrics['name'] = channel_info['name']
        metrics['subscribers'] = channel_info['subscribers']
        metrics['days_active'] = self._calculate_days_active(channel_info)
        
        if not posts_df.empty:
            # Очистка дат от потенциальных проблем
            posts_df['date'] = posts_df['date'].astype(str).str.replace(',', '')
            posts_df['date'] = posts_df['date'].str.strip()
            
            # Конвертация строковых дат в datetime
            posts_df['datetime'] = pd.to_datetime(posts_df['date'], errors='coerce')
            
            # Обрабатываем числовые поля, заменяя NaN на 0
            num_columns = ['views', 'forwards', 'replies']
            for col in num_columns:
                if col in posts_df.columns:
                    posts_df[col] = posts_df[col].fillna(0)
            
            # Удаляем строки с неправильной датой
            valid_posts = posts_df.dropna(subset=['datetime'])
            
            # Общие метрики активности
            metrics['total_posts'] = len(posts_df)
            
            if not valid_posts.empty:
                days_span = max(1, (datetime.now() - valid_posts['datetime'].min()).days)
                metrics['posts_per_day'] = round(len(valid_posts) / days_span, 2)
            else:
                metrics['posts_per_day'] = 0
            
            # Средние значения метрик
            metrics['avg_views'] = int(posts_df['views'].mean()) if not posts_df['views'].isna().all() else 0
            metrics['avg_forwards'] = int(posts_df['forwards'].mean()) if not posts_df['forwards'].isna().all() else 0
            metrics['avg_replies'] = int(posts_df['replies'].mean()) if not posts_df['replies'].isna().all() else 0
            
            # Медианные значения (часто более репрезентативны, чем средние)
            metrics['median_views'] = int(posts_df['views'].median()) if not posts_df['views'].isna().all() else 0
            metrics['median_forwards'] = int(posts_df['forwards'].median()) if not posts_df['forwards'].isna().all() else 0
            metrics['median_replies'] = int(posts_df['replies'].median()) if not posts_df['replies'].isna().all() else 0
            
            # Динамика роста просмотров
            metrics['views_growth'] = self._calculate_growth(posts_df, 'views')
            
            # Проверяем, что 'has_media' существует и содержит числовые значения
            if 'has_media' in posts_df.columns and not posts_df['has_media'].isna().all():
                # Заменяем non-boolean значения на False
                if posts_df['has_media'].dtype != bool:
                    posts_df['has_media'] = posts_df['has_media'].fillna(False).astype(bool)
                media_percentage = round(posts_df['has_media'].sum() / len(posts_df) * 100, 2)
            else:
                media_percentage = 0
                
            metrics['media_percentage'] = media_percentage
            
            # Распределение типов медиа
            if 'media_type' in posts_df.columns:
                media_counts = posts_df['media_type'].value_counts(dropna=True).to_dict()
                metrics['media_types'] = media_counts
        
        return metrics
    
    def _calculate_days_active(self, channel_info: Dict[str, Any]) -> int:
        """Расчет количества дней существования канала"""
        try:
            creation_date = datetime.strptime(channel_info['date_created'], '%Y-%m-%d')
            days_active = (datetime.now() - creation_date).days
            return max(1, days_active)  # Минимум 1 день
        except (ValueError, KeyError):
            return 1  # Возвращаем 1 день, если не удалось определить
    
    def _calculate_growth(self, df: pd.DataFrame, metric: str) -> float:
        """Расчет процента роста метрики за период"""
        if len(df) < 10 or metric not in df.columns or df[metric].isna().all():
            return 0.0
            
        # Формируем копию с заполненными NaN значениями
        df_copy = df.copy()
        df_copy[metric] = df_copy[metric].fillna(0)
        
        # Разбиваем на две половины для сравнения
        df_copy = df_copy.sort_values('datetime')
        half_point = len(df_copy) // 2
        
        first_half = df_copy.iloc[:half_point][metric].mean()
        second_half = df_copy.iloc[half_point:][metric].mean()
        
        if first_half == 0:
            return 0.0
            
        growth = (second_half - first_half) / first_half * 100
        return round(growth, 2)
    
    def _calculate_post_metrics(self, posts_df: pd.DataFrame, 
                               comments_df: pd.DataFrame) -> Dict[str, Any]:
        """Расчет метрик для постов"""
        if posts_df.empty:
            return {}
            
        # Создаем копию DataFrame с преобразованными датами
        df = posts_df.copy()
        
        # Очистка дат от потенциальных проблем
        df['date'] = df['date'].astype(str).str.replace(',', '')
        df['date'] = df['date'].str.strip()
        
        # Обрабатываем числовые поля, заменяя NaN на 0
        num_columns = ['views', 'forwards', 'replies']
        for col in num_columns:
            if col in df.columns:
                df[col] = df[col].fillna(0)
        
        # Конвертация строковых дат в datetime
        df['datetime'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Удаляем строки с неправильной датой
        df = df.dropna(subset=['datetime'])
        
        # Расчет ER (Engagement Rate) для каждого поста
        if 'views' in df.columns and df['views'].sum() > 0:
            df['er'] = ((df['forwards'] + df['replies']) / df['views'] * 100).round(2)
        else:
            df['er'] = 0
            
        # Нахождение лучших и худших постов
        metrics = {
            'best_posts': self._get_top_posts(df, 'er', 5),
            'worst_posts': self._get_top_posts(df, 'er', 5, ascending=True),
            'most_viewed': self._get_top_posts(df, 'views', 5),
            'most_commented': self._get_top_posts(df, 'replies', 5)
        }
        
        # Анализ длины постов и ее влияния на вовлеченность
        if 'text' in df.columns:
            df['text'] = df['text'].fillna('')  # Заменяем NaN на пустую строку
            df['text_length'] = df['text'].apply(len)
            length_analysis = self._analyze_text_length_impact(df)
            metrics.update(length_analysis)
        else:
            metrics.update({'length_impact': [], 'optimal_length': 'Не определено'})
        
        # Динамика публикаций по времени
        metrics['posting_frequency'] = self._analyze_posting_frequency(df)
        
        return metrics
    
    def _get_top_posts(self, df: pd.DataFrame, sort_by: str, n: int = 5, 
                      ascending: bool = False) -> List[Dict[str, Any]]:
        """Получение топ-N постов по указанной метрике"""
        if df.empty or sort_by not in df.columns:
            return []
            
        # Создаем копию и заполняем пропущенные значения
        df_copy = df.copy()
        
        # Если сортировка по числовому полю, заменяем NaN на 0
        if pd.api.types.is_numeric_dtype(df_copy[sort_by]):
            df_copy[sort_by] = df_copy[sort_by].fillna(0)
        
        # Если колонка text содержит NaN, заменяем на пустую строку
        if 'text' in df_copy.columns:
            df_copy['text'] = df_copy['text'].fillna('')
            
        # Сортировка и выбор топ-N
        result = df_copy.sort_values(sort_by, ascending=ascending).head(n).copy()
        
        # Преобразование в список словарей с ограниченным текстом
        result['text_preview'] = result['text'].apply(
            lambda x: x[:100] + '...' if len(x) > 100 else x
        )
        
        columns = ['id', 'date', 'text_preview', 'views', 'forwards', 'replies']
        if 'er' in result.columns:
            columns.append('er')
        
        # Проверяем, что все необходимые колонки существуют
        columns = [col for col in columns if col in result.columns]
        
        return result[columns].to_dict('records')
    
    def _analyze_text_length_impact(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ влияния длины текста на вовлеченность"""
        # Создаем копию DataFrame для избежания предупреждений
        df_copy = df.copy()
        
        # Заполняем пропущенные значения
        if 'text_length' not in df_copy.columns:
            return {'length_impact': [], 'optimal_length': 'Не определено'}
            
        df_copy['text_length'] = df_copy['text_length'].fillna(0)
        
        # Создаем категории длины текста
        bins = [0, 100, 500, 1000, 5000, float('inf')]
        labels = ['Очень короткие', 'Короткие', 'Средние', 'Длинные', 'Очень длинные']
        
        df_copy['length_category'] = pd.cut(df_copy['text_length'], bins=bins, labels=labels)
        
        # Заполняем числовые поля
        for col in ['views', 'forwards', 'replies', 'er']:
            if col in df_copy.columns:
                df_copy[col] = df_copy[col].fillna(0)
        
        # Анализ вовлеченности по категориям длины
        agg_cols = {col: 'mean' for col in ['views', 'forwards', 'replies', 'er'] if col in df_copy.columns}
        agg_cols['id'] = 'count'
        
        try:
            length_stats = df_copy.groupby('length_category').agg(agg_cols).reset_index()
            
            # Преобразование в словарь
            length_impact = length_stats.to_dict('records')
            
            # Определение оптимальной длины
            if not length_stats.empty and 'er' in length_stats.columns:
                optimal_idx = length_stats['er'].idxmax()
                optimal_category = length_stats.loc[optimal_idx, 'length_category']
                optimal_range = {
                    'Очень короткие': '0-100 символов',
                    'Короткие': '100-500 символов',
                    'Средние': '500-1000 символов',
                    'Длинные': '1000-5000 символов',
                    'Очень длинные': 'более 5000 символов'
                }
                
                return {
                    'length_impact': length_impact,
                    'optimal_length': optimal_range.get(optimal_category, 'Не определено')
                }
        except Exception as e:
            logger.error(f"Ошибка при анализе влияния длины текста: {str(e)}")
        
        return {'length_impact': [], 'optimal_length': 'Не определено'}
    
    def _analyze_posting_frequency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ частоты публикаций"""
        if df.empty:
            return {}
            
        # Добавляем день недели и час публикации
        try:
            df['day_of_week'] = df['datetime'].dt.day_name()
            df['hour'] = df['datetime'].dt.hour
            
            # Количество постов по дням недели
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_counts = df['day_of_week'].value_counts().reindex(days_order).fillna(0).to_dict()
            
            # Количество постов по часам
            hour_counts = df['hour'].value_counts().sort_index().to_dict()
            
            # Заполняем пропущенные значения ER
            if 'er' in df.columns:
                df['er'] = df['er'].fillna(0)
                
                # Определение лучшего времени для публикации по ER
                best_days = df.groupby('day_of_week')['er'].mean().sort_values(ascending=False).to_dict()
                best_hours = df.groupby('hour')['er'].mean().sort_values(ascending=False).to_dict()
            else:
                best_days = {}
                best_hours = {}
            
            return {
                'posts_by_day': day_counts,
                'posts_by_hour': hour_counts,
                'best_days': best_days,
                'best_hours': best_hours
            }
        except Exception as e:
            logger.error(f"Ошибка при анализе частоты публикаций: {str(e)}")
            return {}
    
    def _analyze_comments(self, comments_df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ комментариев"""
        if comments_df.empty:
            return {'comments_count': 0}
            
        # Создаем копию DataFrame
        df = comments_df.copy()
        
        # Очистка дат от потенциальных проблем
        if 'date' in df.columns:
            df['date'] = df['date'].astype(str).str.replace(',', '')
            df['date'] = df['date'].str.strip()
            
            # Преобразование дат
            df['datetime'] = pd.to_datetime(df['date'], errors='coerce')
            
            # Удаляем строки с неправильной датой
            df = df.dropna(subset=['datetime'])
        
        # Основные метрики комментариев
        metrics = {
            'comments_count': len(df),
            'unique_users': df['user_id'].nunique() if 'user_id' in df.columns else 0,
        }
        
        # Процент ответов на комментарии
        if 'is_reply' in df.columns and len(df) > 0:
            # Заполняем пропущенные значения
            df['is_reply'] = df['is_reply'].fillna(False)
            metrics['replies_percentage'] = round(df['is_reply'].sum() / len(df) * 100, 2)
        else:
            metrics['replies_percentage'] = 0
        
        # Анализ активности комментаторов
        if 'user_id' in df.columns:
            # Топ пользователей по количеству комментариев
            top_users = df['user_id'].value_counts().head(10).to_dict()
            metrics['top_commenters'] = top_users
            
            # Анализ лояльности (сколько пользователей оставили более одного комментария)
            user_counts = df['user_id'].value_counts()
            loyal_users = user_counts[user_counts > 1].count()
            metrics['loyal_commenters'] = loyal_users
            metrics['loyal_percentage'] = round(
                loyal_users / metrics['unique_users'] * 100, 2
            ) if metrics['unique_users'] > 0 else 0
        
        # Анализ ключевых слов в комментариях
        if 'text' in df.columns:
            # Заполняем пустые значения
            df['text'] = df['text'].fillna('')
            keywords = self._extract_keywords(df['text'].tolist(), 20)
            metrics['comment_keywords'] = keywords
        
        # Динамика комментариев по времени
        if 'datetime' in df.columns and not df.empty:
            comments_by_date = df.groupby(df['datetime'].dt.date).size().to_dict()
            metrics['comments_by_date'] = {str(k): v for k, v in comments_by_date.items()}
        else:
            metrics['comments_by_date'] = {}
        
        return metrics
    
    def _analyze_content(self, posts_df: pd.DataFrame) -> Dict[str, Any]:
        """Тематический анализ содержимого постов"""
        if posts_df.empty:
            return {}
        
        # Создаем копию данных
        df = posts_df.copy()
        
        # Заполняем пропущенные значения
        if 'text' in df.columns:
            df['text'] = df['text'].fillna('')
            
            # Извлечение ключевых слов из текста постов
            all_text = ' '.join(df['text'].tolist())
            keywords = self._extract_keywords([all_text], 30)
            
            # Анализ использования хэштегов
            hashtags = self._extract_hashtags(df['text'].tolist())
            
            # Анализ упоминаний
            mentions = self._extract_mentions(df['text'].tolist())
            
            # Определение основных тем
            topics = self._identify_topics(df)
            
            return {
                'keywords': keywords,
                'hashtags': hashtags,
                'mentions': mentions,
                'topics': topics
            }
        
        return {
            'keywords': {},
            'hashtags': {},
            'mentions': {},
            'topics': []
        }
    
    def _extract_keywords(self, texts: List[str], limit: int = 20) -> Dict[str, int]:
        """Извлечение ключевых слов из текстов"""
        words = []
        
        for text in texts:
            if not text:
                continue
                
            # Очистка текста
            clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
            
            # Токенизация
            tokens = word_tokenize(clean_text)
            
            # Фильтрация стоп-слов и коротких слов
            filtered_words = [word for word in tokens 
                             if word not in self.all_stopwords and len(word) > 3]
            
            words.extend(filtered_words)
        
        # Подсчет частоты слов
        word_counts = Counter(words)
        
        # Возвращаем top-N слов
        return dict(word_counts.most_common(limit))
    
    def _extract_hashtags(self, texts: List[str]) -> Dict[str, int]:
        """Извлечение хэштегов из текстов"""
        hashtags = []
        
        for text in texts:
            if not text:
                continue
                
            # Извлечение хэштегов регулярным выражением
            found_hashtags = re.findall(r'#(\w+)', text)
            hashtags.extend(found_hashtags)
        
        # Подсчет частоты хэштегов
        hashtag_counts = Counter(hashtags)
        
        # Возвращаем топ-20 хэштегов
        return dict(hashtag_counts.most_common(20))
    
    def _extract_mentions(self, texts: List[str]) -> Dict[str, int]:
        """Извлечение упоминаний из текстов"""
        mentions = []
        
        for text in texts:
            if not text:
                continue
                
            # Извлечение упоминаний регулярным выражением
            found_mentions = re.findall(r'@(\w+)', text)
            mentions.extend(found_mentions)
        
        # Подсчет частоты упоминаний
        mention_counts = Counter(mentions)
        
        # Возвращаем топ-20 упоминаний
        return dict(mention_counts.most_common(20))
    
    def _identify_topics(self, posts_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Примитивная идентификация тем на основе кластеризации ключевых слов"""
        topics = []
        
        # Проверяем обязательные колонки
        required_cols = ['text', 'views']
        if not all(col in posts_df.columns for col in required_cols):
            return topics
            
        # Заполняем пропущенные значения
        df = posts_df.copy()
        df['text'] = df['text'].fillna('')
        df['views'] = df['views'].fillna(0)
        df['forwards'] = df['forwards'].fillna(0)
        df['replies'] = df['replies'].fillna(0)
        
        # В MVP используем простой подход - группируем посты по словам и их метрикам
        if len(df) > 10:
            # Сортируем посты по просмотрам
            top_posts = df.sort_values('views', ascending=False).head(10)
            
            for _, post in top_posts.iterrows():
                # Извлекаем ключевые слова из поста
                if post['text']:
                    keywords = self._extract_keywords([post['text']], 5)
                    
                    if keywords:
                        if post['views'] > 0:
                            er = round(((post['forwards'] + post['replies']) / post['views'] * 100), 2)
                        else:
                            er = 0
                        
                        topics.append({
                            'keywords': list(keywords.keys()),
                            'views': int(post['views']),
                            'er': er
                        })
        
        return topics
    
    def _analyze_posting_time(self, posts_df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ времени публикации"""
        if posts_df.empty:
            return {}
            
        # Преобразование дат
        df = posts_df.copy()
        
        # Очистка дат от потенциальных проблем
        df['date'] = df['date'].astype(str).str.replace(',', '')
        df['date'] = df['date'].str.strip()
        
        # Конвертация строковых дат в datetime
        df['datetime'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Удаляем строки с неправильной датой
        df = df.dropna(subset=['datetime'])
        
        # Заполняем пропущенные числовые значения
        if 'views' in df.columns:
            df['views'] = df['views'].fillna(0)
        
        if df.empty:  # Если все строки были удалены из-за неправильных дат
            return {'heatmap': {}, 'best_posting_times': []}
        
        # Добавление колонок с днем недели и часом
        df['day_of_week'] = df['datetime'].dt.day_name()
        df['hour'] = df['datetime'].dt.hour
        
        # Тепловая карта активности по дням недели и часам
        heatmap_data = {}
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        for day in days_order:
            day_data = {}
            day_posts = df[df['day_of_week'] == day]
            
            for hour in range(24):
                hour_posts = day_posts[day_posts['hour'] == hour]
                count = len(hour_posts)
                avg_views = int(hour_posts['views'].mean()) if not hour_posts.empty else 0
                
                day_data[hour] = {
                    'count': count,
                    'avg_views': avg_views
                }
            
            heatmap_data[day] = day_data
        
        # Рекомендуемое время публикации
        if 'views' in df.columns:
            # Группировка по дню и часу, вычисление среднего количества просмотров
            time_performance = df.groupby(['day_of_week', 'hour'])['views'].mean().reset_index()
            
            # Сортировка по просмотрам
            best_times = time_performance.sort_values('views', ascending=False).head(5)
            
            # Преобразование в список рекомендаций
            recommendations = []
            for _, row in best_times.iterrows():
                recommendations.append({
                    'day': row['day_of_week'],
                    'hour': int(row['hour']),
                    'avg_views': int(row['views'])
                })
            
            return {
                'heatmap': heatmap_data,
                'best_posting_times': recommendations
            }
        
        return {'heatmap': heatmap_data, 'best_posting_times': []}