import os
import logging
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, jsonify
from telegram_client import TelegramClient
from data_processor import DataProcessor
from prompt_manager import PromptManager
from llm_interface import LLMInterface
from report_generator import ReportGenerator
from database import Database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Инициализация компонентов
app = Flask(__name__)
db = Database()
telegram_client = TelegramClient()
data_processor = DataProcessor()
prompt_manager = PromptManager()
llm_interface = LLMInterface()
report_generator = ReportGenerator()

@app.route('/')
def index():
    """Главная страница с формой для запуска анализа"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Запуск процесса сбора и анализа данных"""
    channel = request.form.get('channel')
    days = int(request.form.get('days', 30))
    
    if not channel:
        return jsonify({'error': 'Канал не указан'}), 400
    
    # Запуск процесса сбора данных
    try:
        logger.info(f"Начинается сбор данных для канала {channel} за {days} дней")
        
        # Получение информации о канале
        channel_info = telegram_client.get_channel_info(channel)
        
        # Получение постов
        posts = telegram_client.get_posts(channel, days)
        logger.info(f"Найдено {len(posts)} постов за указанный период")
        
        # Получение комментариев
        comments = telegram_client.get_comments(posts)
        logger.info(f"Обнаружено {len(comments)} комментариев")
        
        # Сохранение данных в БД
        channel_id = db.save_channel_info(channel_info)
        db.save_posts(posts, channel_id)
        db.save_comments(comments)
        logger.info("Данные успешно сохранены в базу")
        
        return jsonify({'status': 'success', 'channel_id': channel_id})
    
    except Exception as e:
        logger.error(f"Ошибка при сборе данных: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/channel/<int:channel_id>')
def channel_data(channel_id):
    """Страница с данными канала"""
    channel_info = db.get_channel_info(channel_id)
    posts = db.get_posts(channel_id)
    
    return render_template(
        'channel.html',
        channel=channel_info,
        posts=posts
    )

@app.route('/run_analysis/<int:channel_id>', methods=['POST'])
def run_analysis(channel_id):
    """Запуск анализа данных с использованием LLM"""
    try:
        logger.info("Начинается предобработка данных для анализа...")
        
        # Получение данных из БД
        channel_info = db.get_channel_info(channel_id)
        posts = db.get_posts(channel_id)
        comments = db.get_comments_for_posts([p['id'] for p in posts])
        
        # Предобработка данных
        processed_data = data_processor.process_data(channel_info, posts, comments)
        logger.info("Предобработка завершена")
        
        # Формирование промпта
        logger.info("Формирование многоуровневого промпта...")
        prompt = prompt_manager.generate_prompt(processed_data)
        
        # Отправка запроса к OpenAI API
        logger.info("Отправка запроса к OpenAI API...")
        response = llm_interface.get_analysis(prompt)
        
        # Форматирование отчета
        logger.info("Форматирование отчета...")
        report_path = report_generator.generate_report(
            channel_info['name'],
            response,
            processed_data
        )
        
        # Сохранение отчета в БД
        report_id = db.save_report(channel_id, report_path, prompt, response)
        
        logger.info(f"Отчет сохранен: {report_path}")
        
        return jsonify({
            'status': 'success',
            'report_id': report_id,
            'report_path': report_path
        })
    
    except Exception as e:
        logger.error(f"Ошибка при анализе данных: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/report/<int:report_id>')
def view_report(report_id):
    """Просмотр сгенерированного отчета"""
    report = db.get_report(report_id)
    return render_template('report.html', report=report)

@app.route('/reports')
def list_reports():
    """Список всех сгенерированных отчетов"""
    reports = db.get_all_reports()
    return render_template('reports.html', reports=reports)

@app.route('/compare_reports', methods=['POST'])
def compare_reports():
    """Сравнение двух отчетов"""
    report1_id = request.form.get('report1')
    report2_id = request.form.get('report2')
    
    report1 = db.get_report(report1_id)
    report2 = db.get_report(report2_id)
    
    comparison = report_generator.compare_reports(report1, report2)
    
    return render_template('comparison.html', comparison=comparison)

@app.route('/export/<int:report_id>/<format>')
def export_report(report_id, format):
    """Экспорт отчета в различные форматы"""
    report = db.get_report(report_id)
    
    if format == 'pdf':
        file_path = report_generator.export_to_pdf(report)
    elif format == 'json':
        file_path = report_generator.export_to_json(report)
    elif format == 'contentplan':
        file_path = report_generator.export_to_content_plan(report)
    else:
        return jsonify({'error': 'Неподдерживаемый формат'}), 400
    
    return redirect(url_for('static', filename=file_path))

@app.route('/templates')
def list_templates():
    """Список шаблонов промптов"""
    templates = db.get_prompt_templates()
    return render_template('templates.html', templates=templates)

@app.route('/templates/<int:template_id>', methods=['GET', 'POST'])
def edit_template(template_id):
    """Редактирование шаблона промпта"""
    if request.method == 'POST':
        template_text = request.form.get('template_text')
        db.update_prompt_template(template_id, template_text)
        return redirect(url_for('list_templates'))
    
    template = db.get_prompt_template(template_id)
    return render_template('edit_template.html', template=template)

if __name__ == '__main__':
    # Проверка наличия необходимых API ключей
    required_keys = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'OPENAI_API_KEY']
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    
    if missing_keys:
        logger.error(f"Отсутствуют необходимые API ключи: {', '.join(missing_keys)}")
        logger.error("Пожалуйста, добавьте их в файл .env")
        exit(1)
    
    # Инициализация базы данных при запуске
    db.init_db()
    
    # Запуск Flask сервера
    app.run(debug=True)