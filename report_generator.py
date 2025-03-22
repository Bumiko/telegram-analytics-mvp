import os
import logging
import json
import markdown
from typing import Dict, Any, List, Optional
from datetime import datetime
from llm_interface import LLMInterface

# Настройка логирования
logger = logging.getLogger(__name__)

class ReportGenerator:
    """Класс для генерации и форматирования отчетов"""
    
    def __init__(self):
        """Инициализация генератора отчетов"""
        self.llm_interface = LLMInterface()
        
        # Создаем директории для отчетов, если они не существуют
        os.makedirs('reports', exist_ok=True)
        os.makedirs('static/exports', exist_ok=True)
    
    def generate_report(self, channel_name: str, response: str, 
                       processed_data: Dict[str, Any]) -> str:
        """
        Генерация отчета на основе ответа LLM и обработанных данных
        
        Args:
            channel_name: Название канала
            response: Ответ от LLM
            processed_data: Обработанные данные канала
            
        Returns:
            Путь к созданному файлу отчета
        """
        try:
            # Получение текущей даты для имени файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{channel_name.replace(' ', '_')}_{timestamp}.html"
            filepath = os.path.join('reports', filename)
            
            # Преобразование Markdown в HTML
            html_content = markdown.markdown(response)
            
            # Формирование HTML-документа
            report_html = self._generate_html_report(channel_name, html_content, processed_data)
            
            # Сохранение отчета в файл
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_html)
                
            logger.info(f"Отчет сохранен: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {str(e)}")
            raise
    
    def _generate_html_report(self, channel_name: str, content: str, 
                             data: Dict[str, Any]) -> str:
        """
        Генерация HTML-документа отчета
        
        Args:
            channel_name: Название канала
            content: HTML-контент отчета
            data: Обработанные данные канала
            
        Returns:
            HTML-документ отчета
        """
        # Базовый шаблон HTML
        html_template = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Отчет - {channel_name}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 1px solid #eee;
                }}
                .report-date {{
                    color: #7f8c8d;
                    font-size: 0.9em;
                }}
                .content {{
                    margin-bottom: 30px;
                }}
                .recommendations {{
                    background-color: #e8f8f5;
                    border-left: 4px solid #2ecc71;
                    padding: 15px;
                    margin: 20px 0;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 15px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Аналитический отчет: {channel_name}</h1>
                <p class="report-date">Дата создания: {datetime.now().strftime("%d.%m.%Y %H:%M")}</p>
            </div>
            
            <div class="content">
                {content}
            </div>
            
            <footer>
                <p>
                    Отчет сгенерирован автоматически с использованием GPT-4 и многоуровневых промптов.<br>
                    &copy; Telegram Analytics MVP, {datetime.now().year}
                </p>
            </footer>
        </body>
        </html>
        """
        
        return html_template
    
    def export_to_pdf(self, report: Dict[str, Any]) -> str:
        """
        Экспорт отчета в PDF формат
        
        Args:
            report: Данные отчета
            
        Returns:
            Путь к созданному PDF файлу
        """
        try:
            import pdfkit
            
            # Путь к HTML файлу отчета
            html_path = report.get('file_path')
            
            if not html_path or not os.path.exists(html_path):
                raise ValueError(f"HTML файл отчета не найден: {html_path}")
            
            # Путь для сохранения PDF
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_filename = f"report_export_{timestamp}.pdf"
            pdf_path = os.path.join('static/exports', pdf_filename)
            
            # Конвертация HTML в PDF
            pdfkit.from_file(html_path, pdf_path)
            
            logger.info(f"Отчет экспортирован в PDF: {pdf_path}")
            return pdf_path
            
        except ImportError:
            logger.error("Ошибка: библиотека pdfkit не установлена")
            return ""
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте в PDF: {str(e)}")
            return ""
    
    def export_to_json(self, report: Dict[str, Any]) -> str:
        """
        Экспорт отчета в JSON формат
        
        Args:
            report: Данные отчета
            
        Returns:
            Путь к созданному JSON файлу
        """
        try:
            # Подготовка данных для экспорта
            export_data = {
                'channel_id': report.get('channel_id'),
                'channel_name': report.get('channel_name'),
                'date': str(report.get('date')),
                'content': report.get('response', '')
            }
            
            # Сохранение в JSON файл
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = f"report_export_{timestamp}.json"
            json_path = os.path.join('static/exports', json_filename)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)
                
            logger.info(f"Отчет экспортирован в JSON: {json_path}")
            return json_path
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте в JSON: {str(e)}")
            return ""
    
    def export_to_content_plan(self, report: Dict[str, Any]) -> str:
        """
        Экспорт отчета в формат контент-плана
        
        Args:
            report: Данные отчета
            
        Returns:
            Путь к созданному файлу контент-плана
        """
        try:
            # Извлечение рекомендаций из отчета
            content = report.get('response', '')
            
            # Простая эвристика для извлечения рекомендаций (для MVP)
            recommendations = []
            in_recommendations = False
            
            for line in content.split('\n'):
                if '## Рекомендации' in line or '## План действий' in line:
                    in_recommendations = True
                elif in_recommendations and line.startswith('##'):
                    in_recommendations = False
                elif in_recommendations and line.strip() and not line.startswith('#'):
                    recommendations.append(line.strip())
            
            # Формирование контент-плана
            channel_name = report.get('channel_name', 'Канал')
            content_plan = f"""# Контент-план для канала "{channel_name}"

## Рекомендации на основе аналитики

{chr(10).join(['- ' + rec for rec in recommendations])}

## Календарь публикаций

| Дата | Тема | Формат | Ключевые моменты |
|------|------|--------|-----------------|
| ДД.ММ | | | |
| ДД.ММ | | | |
| ДД.ММ | | | |
| ДД.ММ | | | |

_Этот контент-план создан автоматически на основе аналитики канала. Пожалуйста, заполните календарь публикаций согласно рекомендациям._
"""
            
            # Сохранение в файл
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plan_filename = f"content_plan_{timestamp}.md"
            plan_path = os.path.join('static/exports', plan_filename)
            
            with open(plan_path, 'w', encoding='utf-8') as f:
                f.write(content_plan)
                
            logger.info(f"Контент-план создан: {plan_path}")
            return plan_path
            
        except Exception as e:
            logger.error(f"Ошибка при создании контент-плана: {str(e)}")
            return ""
    
    def compare_reports(self, report1: Dict[str, Any], report2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Сравнение двух отчетов
        
        Args:
            report1: Первый отчет
            report2: Второй отчет
            
        Returns:
            Словарь с данными сравнения
        """
        try:
            # Генерация сравнения с помощью LLM
            comparison_text = self.llm_interface.generate_comparison(report1, report2)
            
            # Преобразование Markdown в HTML
            comparison_html = markdown.markdown(comparison_text)
            
            # Возвращаем данные сравнения
            return {
                'report1': report1,
                'report2': report2,
                'comparison_text': comparison_text,
                'comparison_html': comparison_html
            }
            
        except Exception as e:
            logger.error(f"Ошибка при сравнении отчетов: {str(e)}")
            return {
                'report1': report1,
                'report2': report2,
                'comparison_text': f"Ошибка при сравнении отчетов: {str(e)}",
                'comparison_html': f"<p>Ошибка при сравнении отчетов: {str(e)}</p>"
            }