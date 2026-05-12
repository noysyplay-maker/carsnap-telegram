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

def recognize_car_simple(image_base64):
    """Упрощенное распознавание (случайный выбор)"""
    # Для теста просто выбираем случайную марку
    # Потом заменим на настоящее AI
    brand = random.choice(CAR_BRANDS)
    confidence = random.randint(75, 98)
    
    return {
        'brand': brand,
        'model': f'{brand} Model {random.randint(1, 9)}',
        'confidence': confidence,
        'success': True
    }

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
        
        # "Распознаем" автомобиль
        car_info = recognize_car_simple(image_base64)
        
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
