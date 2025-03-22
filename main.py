import os
import logging
import json
import time
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, jsonify
from telegram_client import TelegramClient
from data_processor import DataProcessor
from prompt_manager import PromptManager
from llm_interface import LLMInterface
from report_generator import ReportGenerator
from database import Database
from telegram_auth import TelegramAuth
from werkzeug.serving import WSGIRequestHandler

# Увеличиваем размер очереди запросов
WSGIRequestHandler.request_queue_size = 500

# Увеличиваем таймаут для обработки запросов
class CustomRequestHandler(WSGIRequestHandler):
    timeout = 300  # Устанавливаем таймаут в 5 минут

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
app.config['TIMEOUT'] = 300  # Увеличиваем таймаут до 5 минут
db = Database()
telegram_client = TelegramClient()
data_processor = DataProcessor()
prompt_manager = PromptManager()
llm_interface = LLMInterface()
report_generator = ReportGenerator()

# Функция для проверки авторизации Telegram
async def check_telegram_auth():
    """Проверка действительности авторизации Telegram"""
    try:
        result = await TelegramAuth.check_auth_status()
        return result.get('is_authorized', False)
    except Exception as e:
        logger.error(f"Ошибка при проверке авторизации Telegram: {str(e)}")
        return False

# Функции авторизации Telegram
async def start_telegram_auth(phone, session_id):
    """Запуск процесса авторизации Telegram"""
    try:
        result = await TelegramAuth.start_auth(phone)
        return result
    except Exception as e:
        logger.error(f"Ошибка при запуске авторизации Telegram: {str(e)}")
        return {'status': 'error', 'error': str(e)}

async def verify_telegram_code_async(phone, code, session_data):
    """Асинхронная проверка кода авторизации Telegram"""
    try:
        # Получаем ID сессии из данных сессии
        session_id = session_data.get('session_id')
        if not session_id:
            return {'status': 'error', 'error': 'Отсутствует идентификатор сессии'}
            
        result = await TelegramAuth.verify_code(session_id, code, phone)
        return result
    except Exception as e:
        logger.error(f"Ошибка при проверке кода Telegram: {str(e)}")
        return {'status': 'error', 'error': str(e)}

async def verify_telegram_2fa_async(password):
    """Асинхронная проверка пароля двухфакторной аутентификации"""
    try:
        # В новой версии session_id передается напрямую из формы
        session_id = request.form.get('session_id')
        result = await TelegramAuth.verify_2fa(session_id, password)
        return result
    except Exception as e:
        logger.error(f"Ошибка при проверке 2FA: {str(e)}")
        return {'status': 'error', 'error': str(e)}

@app.route('/')
def index():
    """Главная страница с формой для запуска анализа"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Запуск процесса сбора и анализа данных"""
    channel = request.form.get('channel')
    days = int(request.form.get('days', 180))  # Увеличиваем до 180 по умолчанию
    
    if not channel:
        return jsonify({'error': 'Канал не указан'}), 400
    
    # Запуск процесса сбора данных
    try:
        logger.info(f"Начинается сбор данных для канала {channel} за {days} дней")
        
        # Получение информации о канале и постов за один запрос
        channel_info, posts = telegram_client.get_channel_info_and_posts(channel, days)
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

@app.route('/initialize')
def initialize():
    """Страница инициализации и настройки приложения"""
    # Проверяем наличие необходимых API ключей
    env_keys = {
        'TELEGRAM_API_ID': os.getenv('TELEGRAM_API_ID'),
        'TELEGRAM_API_HASH': os.getenv('TELEGRAM_API_HASH'),
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY')
    }
    
    # Проверка действительности авторизации
    result = asyncio.run(TelegramAuth.check_auth_status())
    session_exists = result.get('session_exists', False)
    
    return render_template('initialize.html', 
                          env_keys=env_keys, 
                          session_exists=session_exists)

@app.route('/check_auth_status')
def check_auth_status():
    """Проверка статуса авторизации Telegram для AJAX запросов"""
    try:
        result = asyncio.run(TelegramAuth.check_auth_status())
        
        return jsonify({
            'status': 'success',
            'is_authorized': result.get('is_authorized', False),
            'session_exists': result.get('session_exists', False)
        })
    
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса авторизации: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/save_config', methods=['POST'])
def save_config():
    """Сохранение конфигурации и API ключей"""
    try:
        # Получаем данные формы
        telegram_api_id = request.form.get('telegram_api_id')
        telegram_api_hash = request.form.get('telegram_api_hash')
        openai_api_key = request.form.get('openai_api_key')
        
        # Проверяем наличие всех необходимых данных
        if not telegram_api_id or not telegram_api_hash or not openai_api_key:
            return jsonify({'error': 'Не все поля заполнены'}), 400
        
        # Создаем или обновляем .env файл
        env_content = f'''TELEGRAM_API_ID={telegram_api_id}
TELEGRAM_API_HASH={telegram_api_hash}
OPENAI_API_KEY={openai_api_key}
'''
        
        with open('.env', 'w') as env_file:
            env_file.write(env_content)
        
        # Перезагружаем переменные окружения
        load_dotenv(override=True)
        
        return jsonify({'status': 'success', 'message': 'Конфигурация успешно сохранена'})
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении конфигурации: {str(e)}")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500

@app.route('/init_telegram', methods=['POST'])
def init_telegram():
    """Инициализация и авторизация Telegram клиента"""
    try:
        # Получаем данные
        phone = request.form.get('phone')
        
        if not phone:
            return jsonify({'error': 'Номер телефона не указан'}), 400
        
        # Запускаем процесс отправки кода авторизации
        result = asyncio.run(TelegramAuth.start_auth(phone))
        
        if result.get('status') == 'success':
            return jsonify({
                'status': 'pending', 
                'session_id': result.get('session_id'),
                'message': 'Код авторизации отправлен на указанный номер'
            })
        else:
            return jsonify({'error': result.get('error', 'Неизвестная ошибка')}), 400
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации Telegram: {str(e)}")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500

@app.route('/verify_telegram_code', methods=['POST'])
def verify_telegram_code():
    """Проверка кода авторизации Telegram"""
    try:
        # Получаем данные
        session_id = request.form.get('session_id')
        code = request.form.get('code')
        phone = request.form.get('phone')
        
        if not session_id or not code or not phone:
            return jsonify({'error': 'Не указан код, телефон или идентификатор сессии'}), 400
        
        # Проверяем код авторизации
        result = asyncio.run(TelegramAuth.verify_code(session_id, code, phone))
        
        if result.get('status') == 'success':
            return jsonify({
                'status': 'success',
                'message': 'Авторизация успешно завершена'
            })
        elif result.get('status') == '2fa_required':
            return jsonify({
                'status': '2fa_required',
                'message': 'Требуется двухфакторная аутентификация',
                'session_id': session_id
            })
        elif result.get('status') == 'restart_auth':
            return jsonify({
                'status': 'restart_auth',
                'message': 'Требуется перезапуск авторизации. Пожалуйста, повторите попытку.'
            }), 400
        elif result.get('status') == 'code_expired':
            return jsonify({
                'status': 'code_expired',
                'message': 'Код подтверждения истек. Запросите новый код.'
            }), 400
        else:
            return jsonify({'error': result.get('error', 'Неизвестная ошибка')}), 400
        
    except Exception as e:
        logger.error(f"Ошибка при проверке кода Telegram: {str(e)}")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500

@app.route('/verify_telegram_2fa', methods=['POST'])
def verify_telegram_2fa():
    """Проверка пароля двухфакторной аутентификации"""
    try:
        # Получаем данные
        session_id = request.form.get('session_id')
        password = request.form.get('password')
        
        if not session_id or not password:
            return jsonify({'error': 'Не указан пароль или идентификатор сессии'}), 400
        
        # Проверяем пароль 2FA
        result = asyncio.run(TelegramAuth.verify_2fa(session_id, password))
        
        if result.get('status') == 'success':
            return jsonify({
                'status': 'success',
                'message': 'Авторизация успешно завершена'
            })
        else:
            return jsonify({'error': result.get('error', 'Неверный пароль')}), 400
        
    except Exception as e:
        logger.error(f"Ошибка при проверке 2FA: {str(e)}")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500

@app.route('/reset_telegram_session')
def reset_telegram_session():
    """Сброс сессии Telegram"""
    try:
        result = asyncio.run(TelegramAuth.reset_session())
        
        if result.get('status') == 'success':
            return jsonify({
                'status': 'success',
                'message': 'Сессия Telegram успешно сброшена'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': result.get('error', 'Неизвестная ошибка')
            }), 500
    except Exception as e:
        logger.error(f"Ошибка при сбросе сессии Telegram: {str(e)}")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500

if __name__ == '__main__':
    # Проверка наличия необходимых API ключей
    required_keys = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'OPENAI_API_KEY']
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    
    if missing_keys:
        logger.error(f"Отсутствуют необходимые API ключи: {', '.join(missing_keys)}")
        logger.error("Пожалуйста, добавьте их в файл .env или используйте страницу /initialize")
    
    # Инициализация базы данных при запуске
    db.init_db()
    
    # Запуск Flask сервера с кастомным обработчиком запросов
    app.run(debug=True, request_handler=CustomRequestHandler)