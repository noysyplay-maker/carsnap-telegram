import os
import json
import base64
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import random

# Загружаем переменные из .env
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем Flask приложение
app = Flask(__name__)
CORS(app)

# "База данных" в памяти (временно, для теста)
users_db = {}
cars_db = []
streaks_db = {}

# Рейтинг редкости автомобилей
CAR_RARITY = {
    'bugatti': 200, 'lamborghini': 150, 'ferrari': 150,
    'porsche': 100, 'mclaren': 140, 'aston martin': 120,
    'mercedes': 70, 'bmw': 65, 'audi': 60,
    'toyota': 35, 'honda': 35, 'ford': 40,
    'tesla': 80, 'lexus': 55,
    'default': 25
}

# Список марок для случайного выбора (упрощенное AI)
CAR_BRANDS = [
    'BMW', 'Mercedes', 'Audi', 'Toyota', 'Honda', 
    'Ford', 'Porsche', 'Ferrari', 'Lamborghini', 
    'Tesla', 'Lexus', 'Mazda', 'Volkswagen'
]

def recognize_car_ai(image_base64):
    """Распознавание автомобиля через Replicate AI"""
    try:
        import replicate
        import tempfile
        
        logger.info("Starting AI recognition...")
        
        # Декодируем base64
        if ',' in image_base64:
            image_data = base64.b64decode(image_base64.split(',')[1])
        else:
            image_data = base64.b64decode(image_base64)
        
        logger.info(f"Image decoded, size: {len(image_data)} bytes")
        
        # Проверка что изображение не пустое
        if len(image_data) < 1000:
            logger.warning("Image too small")
            return {
                'brand': 'Unknown',
                'model': 'Image too small',
                'confidence': 0,
                'success': False
            }
        
        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            tmp_file.write(image_data)
            tmp_path = tmp_file.name
        
        logger.info(f"Temporary file created: {tmp_path}")
        
        try:
            # Используем BLIP-2 для анализа изображения
            logger.info("Calling Replicate API...")
            
            output = replicate.run(
                "andreasjansson/blip-2:4b32258c42e9efd4288bb9910bc532a69727f9acd26aa08e175713a0a857a608",
                input={
                    "image": open(tmp_path, "rb"),
                    "question": "What is the car brand and model in this image? Answer with just the brand name and model.",
                    "temperature": 0.5,
                    "max_length": 50
                }
            )
            
            logger.info(f"AI Response: {output}")
            
            # Анализируем результат
            description = str(output).lower().strip()
            
            # Извлекаем бренд из ответа AI
            detected_brand = extract_brand_from_text(description)
            detected_model = extract_model_from_text(description, detected_brand)
            
            # Определяем уверенность
            if detected_brand != 'unknown':
                confidence = 85
            else:
                # Пробуем альтернативный метод - просто описание
                output2 = replicate.run(
                    "salesforce/blip:2e1dddc8621f72155f24cf2e0adbde548458d3cab9f00c0139eea840d0ac4746",
                    input={
                        "image": open(tmp_path, "rb"),
                        "task": "image_captioning"
                    }
                )
                logger.info(f"AI Caption: {output2}")
                description2 = str(output2).lower()
                detected_brand = extract_brand_from_text(description2)
                confidence = 70 if detected_brand != 'unknown' else 30
            
            return {
                'brand': detected_brand.title(),
                'model': detected_model or f'{detected_brand.title()} (AI detected)',
                'confidence': confidence,
                'success': True,
                'ai_description': description
            }
            
        finally:
            # Удаляем временный файл
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                logger.info("Temporary file deleted")
        
    except Exception as e:
        logger.error(f"AI Recognition error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Fallback на случайный выбор если AI не сработал
        brand = random.choice(CAR_BRANDS)
        return {
            'brand': brand,
            'model': f'{brand} (Fallback - AI error)',
            'confidence': 20,
            'success': False,
            'error': str(e)
        }


def extract_brand_from_text(text):
    """Извлекает бренд автомобиля из текста"""
    # Расширенный список брендов
    brands = [
        # Премиум
        'ferrari', 'lamborghini', 'porsche', 'bugatti', 'mclaren',
        'aston martin', 'bentley', 'rolls royce', 'maserati',
        
        # Немецкие
        'mercedes', 'bmw', 'audi', 'volkswagen', 'opel',
        
        # Японские
        'toyota', 'honda', 'nissan', 'mazda', 'subaru', 
        'mitsubishi', 'suzuki', 'lexus', 'infiniti', 'acura',
        
        # Американские
        'ford', 'chevrolet', 'dodge', 'jeep', 'tesla',
        'cadillac', 'lincoln', 'buick', 'gmc', 'ram',
        
        # Корейские
        'hyundai', 'kia', 'genesis',
        
        # Другие
        'volvo', 'jaguar', 'land rover', 'mini', 'fiat',
        'peugeot', 'renault', 'citroen', 'skoda', 'seat',
        'alfa romeo', 'lancia', 'saab'
    ]
    
    text = text.lower().strip()
    logger.info(f"Searching brand in: {text}")
    
    # Прямой поиск брендов
    for brand in brands:
        if brand in text:
            logger.info(f"Found brand: {brand}")
            return brand
    
    # Поиск по ключевым словам (если бренд не найден)
    if any(word in text for word in ['luxury', 'premium', 'expensive']):
        if 'german' in text:
            return random.choice(['mercedes', 'bmw', 'audi'])
        elif 'italian' in text:
            return random.choice(['ferrari', 'lamborghini', 'maserati'])
        return random.choice(['mercedes', 'bmw', 'lexus'])
    
    if any(word in text for word in ['suv', 'crossover']):
        return random.choice(['toyota', 'honda', 'nissan', 'jeep'])
    
    if any(word in text for word in ['sports car', 'race', 'racing']):
        return random.choice(['porsche', 'ferrari', 'bmw', 'corvette'])
    
    if any(word in text for word in ['sedan', 'saloon']):
        return random.choice(['toyota', 'honda', 'mercedes'])
    
    if any(word in text for word in ['truck', 'pickup']):
        return random.choice(['ford', 'chevrolet', 'ram', 'toyota'])
    
    if 'electric' in text or 'ev' in text:
        return 'tesla'
    
    logger.warning("No brand found, returning unknown")
    return 'unknown'


def extract_model_from_text(text, brand):
    """Извлекает модель автомобиля из текста"""
    text = text.lower()
    
    # Известные модели по брендам
    models = {
        'toyota': ['camry', 'corolla', 'rav4', 'highlander', 'prius', 'supra', 'land cruiser'],
        'honda': ['civic', 'accord', 'cr-v', 'pilot', 'odyssey'],
        'bmw': ['3 series', '5 series', '7 series', 'x3', 'x5', 'm3', 'm5'],
        'mercedes': ['c-class', 'e-class', 's-class', 'gle', 'glc', 'amg'],
        'audi': ['a3', 'a4', 'a6', 'q3', 'q5', 'q7'],
        'ford': ['f-150', 'mustang', 'explorer', 'escape', 'ranger'],
        'tesla': ['model s', 'model 3', 'model x', 'model y'],
        'porsche': ['911', 'cayenne', 'macan', 'panamera', 'taycan'],
    }
    
    if brand in models:
        for model in models[brand]:
            if model in text:
                return model.title()
    
    # Поиск числовых моделей (типа 320i, Q5)
    import re
    number_model = re.search(r'\b[a-z]?\d{1,3}[a-z]?\b', text)
    if number_model:
        return number_model.group().upper()
    
    return None

def calculate_points(brand, confidence, is_streak_bonus=False):
    """Расчет баллов"""
    base_points = CAR_RARITY.get(brand.lower(), CAR_RARITY['default'])
    confidence_multiplier = confidence / 100
    points = int(base_points * confidence_multiplier)
    
    if is_streak_bonus:
        points = int(points * 1.5)  # +50% за стрик
    
    return points

def check_streak(user_id):
    """Проверка стрика пользователя"""
    if user_id not in streaks_db:
        streaks_db[user_id] = {
            'count': 0,
            'last_post': None
        }
    
    streak_data = streaks_db[user_id]
    now = datetime.now()
    
    if streak_data['last_post'] is None:
        return 0, False
    
    last_post = datetime.fromisoformat(streak_data['last_post'])
    days_diff = (now.date() - last_post.date()).days
    
    if days_diff == 1:
        # Продолжение стрика
        streak_data['count'] += 1
        return streak_data['count'], True
    elif days_diff == 0:
        # Уже постил сегодня
        return streak_data['count'], False
    else:
        # Стрик сломан
        streak_data['count'] = 0
        return 0, False

# ============ API ENDPOINTS ============

@app.route('/api/init', methods=['POST'])
def init_user():
    """Инициализация пользователя"""
    try:
        data = request.json
        user_id = str(data.get('user_id'))
        username = data.get('username', 'User')
        
        if user_id not in users_db:
            users_db[user_id] = {
                'user_id': user_id,
                'username': username,
                'total_points': 0,
                'cars_spotted': 0,
                'joined_date': datetime.now().isoformat()
            }
            logger.info(f"New user created: {username}")
        
        streak_count, _ = check_streak(user_id)
        
        return jsonify({
            'success': True,
            'user': users_db[user_id],
            'streak': streak_count
        }), 200
        
    except Exception as e:
        logger.error(f"Init error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_car():
    """Загрузка фото автомобиля"""
    try:
        data = request.json
        user_id = str(data.get('user_id'))
        image_base64 = data.get('image')
        username = data.get('username', 'User')
        
        if not image_base64 or not user_id:
            return jsonify({'error': 'Missing data'}), 400
        
        logger.info(f"Upload from user: {username}")
        
        # Проверяем стрик
        streak_count, is_streak_active = check_streak(user_id)
        
        # Распознаем автомобиль через AI
car_info = recognize_car_ai(image_base64)
        
        # Рассчитываем баллы
        points = calculate_points(
            car_info['brand'], 
            car_info['confidence'],
            is_streak_bonus=is_streak_active
        )
        
        # Сохраняем в базу
        car_entry = {
            'id': len(cars_db) + 1,
            'user_id': user_id,
            'username': username,
            'brand': car_info['brand'],
            'model': car_info['model'],
            'confidence': car_info['confidence'],
            'points': points,
            'image': image_base64,
            'timestamp': datetime.now().isoformat(),
            'streak_bonus': is_streak_active
        }
        
        cars_db.insert(0, car_entry)
        
        # Обновляем пользователя
        if user_id in users_db:
            users_db[user_id]['total_points'] += points
            users_db[user_id]['cars_spotted'] += 1
        
        # Обновляем стрик
        streaks_db[user_id]['last_post'] = datetime.now().isoformat()
        if not is_streak_active and streak_count == 0:
            streaks_db[user_id]['count'] = 1
        
        logger.info(f"Car added: {car_info['brand']} (+{points} points)")
        
        return jsonify({
            'success': True,
            'car': car_entry,
            'new_total_points': users_db[user_id]['total_points'],
            'streak': streaks_db[user_id]['count']
        }), 200
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/feed', methods=['GET'])
def get_feed():
    """Лента всех автомобилей"""
    try:
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        feed = cars_db[offset:offset+limit]
        
        return jsonify({
            'success': True,
            'cars': feed,
            'total': len(cars_db)
        }), 200
        
    except Exception as e:
        logger.error(f"Feed error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """Таблица лидеров"""
    try:
        sorted_users = sorted(
            users_db.values(), 
            key=lambda x: x['total_points'], 
            reverse=True
        )[:10]
        
        leaderboard = []
        for idx, user in enumerate(sorted_users, 1):
            user_data = user.copy()
            user_data['rank'] = idx
            user_data['streak'] = streaks_db.get(user['user_id'], {}).get('count', 0)
            leaderboard.append(user_data)
        
        return jsonify({
            'success': True,
            'leaderboard': leaderboard
        }), 200
        
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    """Главная страница (проверка работы)"""
    return jsonify({
        'status': 'online',
        'message': 'CarSnap API is running!',
        'users': len(users_db),
        'cars': len(cars_db)
    })

if __name__ == '__main__':
    PORT = int(os.getenv('PORT', 5000))
    logger.info(f"Starting server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=True)


