import os
import logging
import json
import time
from typing import Dict, Any, Optional
import openai

# Настройка логирования
logger = logging.getLogger(__name__)

class LLMInterface:
    """Класс для взаимодействия с OpenAI API"""
    
    def __init__(self):
        """Инициализация клиента OpenAI API"""
        self.api_key = os.getenv('OPENAI_API_KEY')
        openai.api_key = self.api_key
    
    def get_analysis(self, prompt_data: Dict[str, Any], 
                    model: str = "gpt-4") -> str:
        """
        Отправка промпта в OpenAI API и получение результата анализа
        
        Args:
            prompt_data: Структурированный промпт или финальный текст промпта
            model: Модель LLM для использования
            
        Returns:
            Текст ответа от LLM
        """
        if not self.api_key:
            raise ValueError("API ключ OpenAI не настроен. Проверьте переменную OPENAI_API_KEY в .env файле")
        
        # Извлекаем финальный промпт
        final_prompt = prompt_data.get('final_prompt', '')
        
        if not final_prompt:
            raise ValueError("Финальный промпт не найден в переданных данных")
        
        # Логирование длины промпта для отладки
        logger.info(f"Отправка запроса к OpenAI API (длина промпта: {len(final_prompt)} символов)...")
        
        try:
            # Отправка запроса к OpenAI API
            response = self._send_request(final_prompt, model)
            
            # Логирование информации о полученном ответе
            token_count = len(response.split()) // 0.75  # Приблизительный подсчет токенов
            logger.info(f"Ответ получен ({int(token_count)} токенов)")
            
            return response
            
        except openai.error.APIError as e:
            logger.error(f"Ошибка API OpenAI: {str(e)}")
            raise
            
        except openai.error.RateLimitError:
            logger.warning("Достигнут лимит запросов к OpenAI API. Повторная попытка через 20 секунд...")
            time.sleep(20)
            return self.get_analysis(prompt_data, model)
            
        except Exception as e:
            logger.error(f"Ошибка при взаимодействии с OpenAI API: {str(e)}")
            raise
    
    def _send_request(self, prompt: str, model: str) -> str:
        """
        Отправка запроса к OpenAI API
        
        Args:
            prompt: Текст промпта
            model: Модель LLM
            
        Returns:
            Текст ответа
        """
        try:
            # Создание чата с указанными сообщениями
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Ты - опытный аналитик Telegram-каналов, который анализирует данные и предоставляет рекомендации."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            # Извлечение текста ответа
            return response.choices[0].message['content']
            
        except Exception as e:
            logger.error(f"Ошибка при отправке запроса: {str(e)}")
            raise
    
    def generate_comparison(self, report1: Dict[str, Any], report2: Dict[str, Any]) -> str:
        """
        Генерация сравнительного анализа двух отчетов
        
        Args:
            report1: Первый отчет
            report2: Второй отчет
            
        Returns:
            Текст сравнительного анализа
        """
        # Подготовка промпта для сравнения отчетов
        comparison_prompt = f"""
        Сравни два аналитических отчета по Telegram-каналу и выдели ключевые изменения, 
        тренды и различия в рекомендациях.
        
        ОТЧЕТ 1 (от {report1.get('date', 'неизвестной даты')}):
        {report1.get('content', 'Нет данных')}
        
        ОТЧЕТ 2 (от {report2.get('date', 'неизвестной даты')}):
        {report2.get('content', 'Нет данных')}
        
        В сравнительном анализе обрати внимание на:
        1. Изменения в ключевых метриках (просмотры, вовлеченность, рост)
        2. Эволюцию контент-стратегии и её эффективности
        3. Изменения в поведении аудитории
        4. Прогресс в выполнении предыдущих рекомендаций
        5. Новые возможности и угрозы
        
        Формат ответа должен включать:
        - Сводку основных изменений
        - Сравнение метрик и их динамики
        - Анализ выполнения предыдущих рекомендаций
        - Новые рекомендации на основе выявленных трендов
        """
        
        try:
            # Отправка запроса к OpenAI API
            response = self._send_request(comparison_prompt, "gpt-4")
            return response
            
        except Exception as e:
            logger.error(f"Ошибка при генерации сравнительного анализа: {str(e)}")
            return f"Ошибка при генерации сравнительного анализа: {str(e)}"