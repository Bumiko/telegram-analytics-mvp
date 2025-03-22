import logging
import json
from typing import Dict, Any, List
from datetime import datetime

# Настройка логирования
logger = logging.getLogger(__name__)

class PromptManager:
    """Управление шаблонами промптов и генерация финального промпта для LLM"""
    
    def __init__(self):
        """Инициализация менеджера промптов"""
        # Базовые шаблоны для разных уровней промптов
        self.system_template = self._get_system_template()
        self.context_template = self._get_context_template()
        self.instruction_template = self._get_instruction_template()
        self.data_template = self._get_data_template()
    
    def generate_prompt(self, processed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерация многоуровневого промпта на основе обработанных данных
        
        Args:
            processed_data: Предобработанные данные канала
            
        Returns:
            Словарь со структурированным промптом для LLM
        """
        logger.info("Формирование многоуровневого промпта...")
        
        # Заполняем каждый уровень промпта данными
        system_level = self._fill_system_template()
        context_level = self._fill_context_template(processed_data)
        instruction_level = self._fill_instruction_template(processed_data)
        data_level = self._fill_data_template(processed_data)
        
        # Формируем финальный промпт
        prompt = {
            "system": system_level,
            "context": context_level,
            "instruction": instruction_level,
            "data": data_level
        }
        
        # Компоновка финального сообщения для отправки в LLM
        final_prompt = self._compose_final_prompt(prompt)
        
        logger.info("Многоуровневый промпт сформирован успешно")
        return {
            "structured_prompt": prompt,
            "final_prompt": final_prompt
        }
    
    def _get_system_template(self) -> str:
        """Шаблон системного промпта"""
        return """
        Ты - опытный аналитик Telegram-каналов с многолетним опытом в контент-стратегии
        и маркетинговой аналитике. Твоя задача - провести глубокий анализ Telegram-канала
        на основе предоставленных данных и предложить конкретные рекомендации для улучшения
        контент-стратегии, роста вовлечённости и увеличения аудитории.
        
        Твой анализ должен быть:
        1. Структурированным и разделенным на логические разделы
        2. Основанным на фактических данных и метриках
        3. Содержать конкретные и применимые рекомендации
        4. Написанным понятным языком с минимумом маркетинговых терминов
        
        Формат ответа должен содержать:
        - Общий анализ канала
        - Анализ контента и его эффективности
        - Анализ аудитории и её вовлечённости
        - Рекомендации по улучшению стратегии контента
        - Рекомендации по оптимизации времени публикаций
        - Идеи для экспериментов с новыми форматами
        """
    
    def _get_context_template(self) -> str:
        """Шаблон контекстуального промпта"""
        return """
        Канал: {channel_name}
        Описание: {channel_description}
        Количество подписчиков: {subscribers}
        Тематика: {channel_topic}
        Активен: {days_active} дней
        
        Период анализа: последние {analysis_period} дней
        
        Исследуемый канал относится к категории {size_category} каналов в Telegram.
        Средний пост получает {avg_views} просмотров, {avg_engagement} вовлечённости.
        """
    
    def _get_instruction_template(self) -> str:
        """Шаблон инструкционного промпта"""
        return """
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
        
        5. Составь план действий на ближайший месяц
           - 3-5 конкретных шагов с обоснованием
           - Метрики для отслеживания результатов
        
        Старайся быть максимально конкретным и основывай все рекомендации на данных.
        Если в данных есть противоречия или аномалии, обязательно отметь их и предложи
        возможные объяснения.
        """
    
    def _get_data_template(self) -> str:
        """Шаблон промпта с данными"""
        return """
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
        """
    
    def _fill_system_template(self) -> str:
        """Заполнение системного шаблона"""
        return self.system_template.strip()
    
    def _fill_context_template(self, data: Dict[str, Any]) -> str:
        """Заполнение контекстуального шаблона"""
        channel_info = data.get('channel_info', {})
        channel_metrics = data.get('channel_metrics', {})
        
        # Определение категории канала по размеру
        subscribers = channel_info.get('subscribers', 0)
        size_category = "маленьких"
        if subscribers > 100000:
            size_category = "крупных"
        elif subscribers > 10000:
            size_category = "средних"
        
        # Расчет средней вовлеченности
        avg_views = channel_metrics.get('avg_views', 0)
        avg_replies = channel_metrics.get('avg_replies', 0)
        avg_forwards = channel_metrics.get('avg_forwards', 0)
        
        if avg_views > 0:
            avg_engagement = f"{round((avg_replies + avg_forwards) / avg_views * 100, 2)}%"
        else:
            avg_engagement = "0%"
        
        context = self.context_template.format(
            channel_name=channel_info.get('name', 'Неизвестный канал'),
            channel_description=channel_info.get('description', 'Нет описания'),
            subscribers=subscribers,
            channel_topic=self._determine_topic(data),
            days_active=channel_metrics.get('days_active', 0),
            analysis_period=30,  # По умолчанию анализируем за 30 дней
            size_category=size_category,
            avg_views=avg_views,
            avg_engagement=avg_engagement
        )
        
        return context.strip()
    
    def _determine_topic(self, data: Dict[str, Any]) -> str:
        """Определение тематики канала на основе ключевых слов"""
        content_analysis = data.get('content_analysis', {})
        keywords = content_analysis.get('keywords', {})
        
        if not keywords:
            return "Разное"
        
        # В будущих версиях здесь можно реализовать более сложную логику
        # определения тематики на основе ключевых слов
        top_keywords = list(keywords.keys())[:5]
        return ", ".join(top_keywords)
    
    def _fill_instruction_template(self, data: Dict[str, Any]) -> str:
        """Заполнение инструкционного шаблона"""
        channel_name = data.get('channel_info', {}).get('name', 'Неизвестный канал')
        
        instruction = self.instruction_template.format(
            channel_name=channel_name
        )
        
        return instruction.strip()
    
    def _fill_data_template(self, data: Dict[str, Any]) -> str:
        """Заполнение шаблона с данными"""
        # Форматирование метрик канала
        channel_metrics = self._format_channel_metrics(data.get('channel_metrics', {}))
        
        # Форматирование метрик постов
        post_metrics = self._format_post_metrics(data.get('post_metrics', {}))
        
        # Форматирование анализа комментариев
        comment_analysis = self._format_comment_analysis(data.get('comment_analysis', {}))
        
        # Форматирование анализа контента
        content_analysis = self._format_content_analysis(data.get('content_analysis', {}))
        
        # Форматирование анализа времени публикации
        time_analysis = self._format_time_analysis(data.get('time_analysis', {}))
        
        data_section = self.data_template.format(
            channel_metrics=channel_metrics,
            post_metrics=post_metrics,
            comment_analysis=comment_analysis,
            content_analysis=content_analysis,
            time_analysis=time_analysis
        )
        
        return data_section.strip()
    
    def _format_channel_metrics(self, metrics: Dict[str, Any]) -> str:
        """Форматирование метрик канала"""
        result = []
        
        metrics_to_include = [
            ('total_posts', 'Всего постов'),
            ('posts_per_day', 'Постов в день'),
            ('avg_views', 'Среднее количество просмотров'),
            ('median_views', 'Медианное количество просмотров'),
            ('avg_forwards', 'Среднее количество репостов'),
            ('avg_replies', 'Среднее количество комментариев'),
            ('views_growth', 'Рост просмотров за период (%)'),
            ('media_percentage', 'Процент постов с медиа')
        ]
        
        for key, label in metrics_to_include:
            if key in metrics:
                result.append(f"- {label}: {metrics[key]}")
        
        # Добавляем распределение типов медиа, если доступно
        if 'media_types' in metrics and metrics['media_types']:
            result.append("- Распределение типов медиа:")
            for media_type, count in metrics['media_types'].items():
                result.append(f"  - {media_type}: {count}")
        
        return "\n".join(result)
    
    def _format_post_metrics(self, metrics: Dict[str, Any]) -> str:
        """Форматирование метрик постов"""
        result = []
        
        # Информация о лучших постах
        if 'best_posts' in metrics and metrics['best_posts']:
            result.append("Лучшие посты по вовлечённости:")
            for i, post in enumerate(metrics['best_posts'], 1):
                result.append(f"  {i}. ID: {post['id']}, Дата: {post['date']}")
                result.append(f"     Просмотры: {post['views']}, ER: {post.get('er', 'N/A')}%")
                result.append(f"     Текст: {post['text_preview']}")
                result.append("")
        
        # Информация о самых просматриваемых постах
        if 'most_viewed' in metrics and metrics['most_viewed']:
            result.append("Самые просматриваемые посты:")
            for i, post in enumerate(metrics['most_viewed'], 1):
                result.append(f"  {i}. ID: {post['id']}, Просмотры: {post['views']}")
                result.append(f"     Текст: {post['text_preview']}")
                result.append("")
        
        # Влияние длины поста
        if 'length_impact' in metrics and metrics['length_impact']:
            result.append("Влияние длины поста на вовлечённость:")
            for category in metrics['length_impact']:
                result.append(f"  - {category['length_category']}: {category.get('id', 0)} постов, ER: {category.get('er', 0):.2f}%")
            
            result.append(f"  - Оптимальная длина поста: {metrics.get('optimal_length', 'Не определено')}")
            result.append("")
        
        # Частота публикаций
        if 'posting_frequency' in metrics:
            freq = metrics['posting_frequency']
            
            if 'best_days' in freq and freq['best_days']:
                result.append("Лучшие дни для публикации (по ER):")
                for day, er in list(freq['best_days'].items())[:3]:
                    result.append(f"  - {day}: {er:.2f}%")
                result.append("")
                
            if 'best_hours' in freq and freq['best_hours']:
                result.append("Лучшие часы для публикации (по ER):")
                for hour, er in list(freq['best_hours'].items())[:3]:
                    result.append(f"  - {hour}:00: {er:.2f}%")
        
        return "\n".join(result)
    
    def _format_comment_analysis(self, analysis: Dict[str, Any]) -> str:
        """Форматирование анализа комментариев"""
        result = []
        
        # Основные метрики
        result.append(f"- Всего комментариев: {analysis.get('comments_count', 0)}")
        result.append(f"- Уникальных комментаторов: {analysis.get('unique_users', 0)}")
        result.append(f"- Процент ответов на комментарии: {analysis.get('replies_percentage', 0)}%")
        result.append(f"- Лояльных комментаторов: {analysis.get('loyal_commenters', 0)} ({analysis.get('loyal_percentage', 0)}%)")
        result.append("")
        
        # Ключевые слова в комментариях
        if 'comment_keywords' in analysis and analysis['comment_keywords']:
            result.append("Часто используемые слова в комментариях:")
            for word, count in list(analysis['comment_keywords'].items())[:10]:
                result.append(f"  - {word}: {count}")
            result.append("")
        
        # Динамика комментариев по времени
        if 'comments_by_date' in analysis and analysis['comments_by_date']:
            result.append("Динамика комментирования:")
            dates = sorted(analysis['comments_by_date'].keys())
            for date in dates[-5:]:  # Последние 5 дат
                result.append(f"  - {date}: {analysis['comments_by_date'][date]} комментариев")
        
        return "\n".join(result)
    
    def _format_content_analysis(self, analysis: Dict[str, Any]) -> str:
        """Форматирование анализа контента"""
        result = []
        
        # Ключевые слова
        if 'keywords' in analysis and analysis['keywords']:
            result.append("Ключевые слова в постах:")
            for word, count in list(analysis['keywords'].items())[:15]:
                result.append(f"  - {word}: {count}")
            result.append("")
        
        # Хэштеги
        if 'hashtags' in analysis and analysis['hashtags']:
            result.append("Популярные хэштеги:")
            for tag, count in list(analysis['hashtags'].items())[:10]:
                result.append(f"  - #{tag}: {count}")
            result.append("")
        
        # Упоминания
        if 'mentions' in analysis and analysis['mentions']:
            result.append("Частые упоминания:")
            for mention, count in list(analysis['mentions'].items())[:10]:
                result.append(f"  - @{mention}: {count}")
            result.append("")
        
        # Темы
        if 'topics' in analysis and analysis['topics']:
            result.append("Выявленные тематические кластеры:")
            for i, topic in enumerate(analysis['topics'], 1):
                keywords = ", ".join(topic.get('keywords', []))
                result.append(f"  {i}. Тема: {keywords}")
                result.append(f"     Средние просмотры: {topic.get('views', 0)}, ER: {topic.get('er', 0)}%")
                result.append("")
        
        return "\n".join(result)
    
    def _format_time_analysis(self, analysis: Dict[str, Any]) -> str:
        """Форматирование анализа времени публикации"""
        result = []
        
        # Рекомендуемое время публикации
        if 'best_posting_times' in analysis and analysis['best_posting_times']:
            result.append("Рекомендуемое время публикации (на основе просмотров):")
            for i, time_slot in enumerate(analysis['best_posting_times'], 1):
                result.append(f"  {i}. {time_slot['day']}, {time_slot['hour']}:00 - Среднее количество просмотров: {time_slot['avg_views']}")
            result.append("")
        
        # Примитивное представление тепловой карты (в текстовом формате)
        if 'heatmap' in analysis and analysis['heatmap']:
            result.append("Тепловая карта активности (количество постов):")
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            # Выводим самые активные часы для каждого дня
            for day in days_order:
                if day in analysis['heatmap']:
                    day_data = analysis['heatmap'][day]
                    active_hours = sorted(
                        [(hour, data['count']) for hour, data in day_data.items()],
                        key=lambda x: x[1],
                        reverse=True
                    )[:3]  # Топ-3 активных часа
                    
                    if active_hours and active_hours[0][1] > 0:
                        hour_str = ", ".join([f"{hour}:00 ({count})" for hour, count in active_hours])
                        result.append(f"  - {day}: {hour_str}")
        
        return "\n".join(result)
    
    def _compose_final_prompt(self, prompt: Dict[str, str]) -> str:
        """Компоновка финального промпта для отправки в LLM"""
        final_prompt = f"""
        {prompt['system']}
        
        ### КОНТЕКСТ
        {prompt['context']}
        
        ### ИНСТРУКЦИИ
        {prompt['instruction']}
        
        ### ДАННЫЕ
        {prompt['data']}
        
        ### ФОРМАТ ОТВЕТА
        Твой ответ должен быть структурирован следующим образом:
        
        # АНАЛИЗ TELEGRAM-КАНАЛА
        
        ## Общая оценка эффективности
        [Общий анализ канала, основные метрики, сравнение с ожидаемыми показателями]
        
        ## Анализ контента
        [Анализ успешности разных типов контента, тем, форматов]
        
        ## Анализ аудитории
        [Характеристики и поведение аудитории]
        
        ## Рекомендации
        [Конкретные, измеримые рекомендации по улучшению канала]
        
        ## План действий на месяц
        [3-5 конкретных шагов с обоснованием и ожидаемыми результатами]
        """
        
        return final_prompt.strip()