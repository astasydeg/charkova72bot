import telebot
from telebot import types
import sqlite3
import datetime
import os
import re

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)

# РАЗДЕЛЕНИЕ АДМИНИСТРАТОРОВ
SUPER_ADMIN = 123456789  # ВАШ ID (супер-админ, разработчик)
ADMINS = [
    987654321,  # Первый обычный администратор
    555555555   # Второй обычный администратор
]

# Все администраторы (супер-админ + обычные)
ALL_ADMINS = [SUPER_ADMIN] + ADMINS

# Начальный список корпусов
DEFAULT_BUILDINGS = ["1.1", "1.2", "1.3", "1.4", "2.1", "2.2"]

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('house_chat.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            building TEXT,
            apartment TEXT,
            phone TEXT,
            registered BOOLEAN DEFAULT FALSE,
            registration_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица корпусов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS buildings (
            name TEXT PRIMARY KEY,
            added_by INTEGER,
            added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Добавляем корпуса по умолчанию, если их еще нет
    for building in DEFAULT_BUILDINGS:
        cursor.execute('''
            INSERT OR IGNORE INTO buildings (name, added_by) 
            VALUES (?, ?)
        ''', (building, SUPER_ADMIN))
    
    conn.commit()
    conn.close()

# Получение списка всех корпусов
def get_all_buildings():
    conn = sqlite3.connect('house_chat.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM buildings ORDER BY name')
    buildings = [row[0] for row in cursor.fetchall()]
    conn.close()
    return buildings

# Добавление нового корпуса
def add_building(building_name, added_by):
    conn = sqlite3.connect('house_chat.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO buildings (name, added_by) VALUES (?, ?)', (building_name, added_by))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

# Проверка является ли пользователь администратором
def is_admin(user_id):
    return user_id in ALL_ADMINS

# Проверка является ли пользователь супер-админом
def is_super_admin(user_id):
    return user_id == SUPER_ADMIN

# Сохранение пользователя
def save_user(user_id, building, apartment, phone, username="", first_name="", last_name=""):
    conn = sqlite3.connect('house_chat.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, last_name, building, apartment, phone, registered)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, building, apartment, phone, True))
    
    conn.commit()
    conn.close()

# Проверка регистрации пользователя
def is_user_registered(user_id):
    conn = sqlite3.connect('house_chat.db')
    cursor = conn.cursor()
    cursor.execute('SELECT registered FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0]

# Получение жильцов квартиры (только для админов)
def get_apartment_residents(building, apartment):
    conn = sqlite3.connect('house_chat.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT first_name, last_name, phone, username, registration_time 
        FROM users 
        WHERE building = ? AND apartment = ? AND registered = TRUE
        ORDER BY registration_time
    ''', (building, apartment))
    residents = cursor.fetchall()
    conn.close()
    
    return [{
        'first_name': resident[0],
        'last_name': resident[1],
        'phone': resident[2],
        'username': resident[3],
        'registration_time': resident[4]
    } for resident in residents]

# Проверка, есть ли уже жильцы в квартире (без показа информации)
def is_apartment_occupied(building, apartment):
    conn = sqlite3.connect('house_chat.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE building = ? AND apartment = ? AND registered = TRUE', (building, apartment))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

# Валидация номера квартиры
def validate_apartment(apartment):
    if not apartment.isdigit():
        return False, "❌ Номер квартиры должен содержать только цифры"
    
    apartment_num = int(apartment)
    if apartment_num <= 0:
        return False, "❌ Номер квартиры должен быть больше 0"
    
    if apartment_num > 1000:  # разумное ограничение
        return False, "❌ Номер квартиры слишком большой"
    
    return True, "✅ Номер квартиры корректен"

# Валидация номера телефона
def validate_phone(phone):
    # Убираем все нецифровые символы
    clean_phone = re.sub(r'\D', '', phone)
    
    # Проверяем российские номера (начинаются с 7 или 8, длина 11 цифр)
    if clean_phone.startswith('7') or clean_phone.startswith('8'):
        if len(clean_phone) == 11:
            return True, "✅ Номер телефона корректен"
        else:
            return False, "❌ Российский номер должен содержать 11 цифр"
    
    # Проверяем международные номера (начинаются не с 7/8)
    if len(clean_phone) >= 10 and len(clean_phone) <= 15:
        return True, "✅ Номер телефона корректен"
    
    return False, "❌ Неверный формат номера телефона"

# Уведомление только обычных администраторов
def notify_admins(user_info, building, apartment, phone):
    residents = get_apartment_residents(building, apartment)
    residents_count = len(residents)
    is_new_apartment = residents_count == 1
    
    if is_new_apartment:
        admin_text = f"""
🆕 НОВАЯ КВАРТИРА ЗАРЕГИСТРИРОВАНА!

🏢 Корпус: {building}
🏠 Квартира: {apartment}
👤 Первый жилец: {user_info.get('first_name', 'Не указано')}
📞 Телефон: {phone}
👥 Всего в квартире: {residents_count} чел.

🔍 Детали:
Username: @{user_info.get('username', 'Не указано')}
ID: {user_info.get('id', 'Не указано')}
Время: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """
    else:
        admin_text = f"""
👥 ДОБАВЛЕН НОВЫЙ ЖИЛЕЦ В КВАРТИРУ

🏢 Корпус: {building}
🏠 Квартира: {apartment}
👤 Новый жилец: {user_info.get('first_name', 'Не указано')}
📞 Телефон: {phone}
👥 Всего в квартире: {residents_count} чел.

📋 Все жильцы квартиры {building}-{apartment}:
"""
        for i, resident in enumerate(residents, 1):
            admin_text += f"{i}. {resident.get('first_name')} - {resident.get('phone')}\n"
    
    # Отправляем уведомление только ОБЫЧНЫМ администраторам
    for admin_id in ADMINS:
        try:
            bot.send_message(admin_id, admin_text)
            print(f"✅ Админ {admin_id} уведомлен о регистрации в квартире {building}-{apartment}")
        except Exception as e:
            print(f"❌ Ошибка отправки админу {admin_id}: {e}")

# Функция показа выбора корпуса
def show_building_selection(chat_id, user_id, is_existing_user=False):
    buildings = get_all_buildings()
    
    if not buildings:
        bot.send_message(chat_id, "❌ В системе нет доступных корпусов. Обратитесь к администратору.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Создаем кнопки для корпусов
    buttons = []
    for building in buildings:
        buttons.append(types.InlineKeyboardButton(
            f"🏢 {building}", 
            callback_data=f"select_building_{user_id}_{building}_{'existing' if is_existing_user else 'new'}"
        ))
    
    # Распределяем кнопки по 2 в строке
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])
    
    if is_existing_user:
        welcome_text = """
📝 Регистрация в домовом чате

Для продолжения общения в чате необходимо пройти регистрацию.

🏢 Выберите ваш корпус из списка:
        """
    else:
        welcome_text = """
👋 Добро пожаловать в домовой чат!

Для доступа к чату необходимо пройти регистрацию.

🏢 Выберите ваш корпус из списка:
        """
    
    bot.send_message(
        chat_id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=markup
    )

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

# Обработчик новых участников
@bot.message_handler(content_types=['new_chat_members'])
def new_member(message):
    for new_member in message.new_chat_members:
        if not new_member.is_bot:
            user_id = new_member.id
            
            # Сохраняем базовую информацию
            conn = sqlite3.connect('house_chat.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, registered)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, new_member.username, new_member.first_name, new_member.last_name, False))
            conn.commit()
            conn.close()
            
            # Показываем кнопки с корпусами для выбора
            show_building_selection(message.chat.id, user_id, is_existing_user=False)

# Команда для регистрации существующих участников
@bot.message_handler(commands=['register'])
def register_existing_user(message):
    user_id = message.from_user.id
    
    if is_user_registered(user_id):
        bot.reply_to(message, "✅ Вы уже зарегистрированы в системе!")
        return
    
    # Сохраняем базовую информацию если пользователя еще нет в базе
    conn = sqlite3.connect('house_chat.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, last_name, registered)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name, False))
    conn.commit()
    conn.close()
    
    # Показываем кнопки с корпусами для выбора
    show_building_selection(message.chat.id, user_id, is_existing_user=True)

# Обработчик выбора корпуса
@bot.callback_query_handler(func=lambda call: call.data.startswith('select_building_'))
def handle_building_selection(call):
    data_parts = call.data.split('_')
    user_id = int(data_parts[2])
    building = data_parts[3]
    user_type = data_parts[4]  # 'new' или 'existing'
    
    if is_user_registered(user_id):
        bot.answer_callback_query(call.id, "Вы уже зарегистрированы!")
        return
    
    # Сохраняем выбранный корпус
    conn = sqlite3.connect('house_chat.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET building = ? WHERE user_id = ?', (building, user_id))
    conn.commit()
    conn.close()
    
    # Удаляем сообщение с кнопками
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    # Запрашиваем номер квартиры
    msg = bot.send_message(
        call.message.chat.id,
        f"🏢 Выбран корпус: {building}\n\n🏠 Теперь введите номер квартиры:"
    )
    bot.register_next_step_handler(msg, process_apartment, user_id, building)

# Обработчик ввода номера квартиры
def process_apartment(message, user_id, building):
    apartment = message.text.strip()
    
    # Валидация номера квартиры
    is_valid, validation_message = validate_apartment(apartment)
    
    if not is_valid:
        msg = bot.send_message(
            message.chat.id,
            f"{validation_message}\n\nПожалуйста, введите номер квартиры еще раз:"
        )
        bot.register_next_step_handler(msg, process_apartment, user_id, building)
        return
    
    # Запрашиваем номер телефона (БЕЗ показа существующих жильцов)
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    phone_btn = types.KeyboardButton("📱 Отправить номер телефона", request_contact=True)
    markup.add(phone_btn)
    
    msg = bot.send_message(
        message.chat.id,
        "📞 Теперь поделитесь номером телефона:\n\nВы можете отправить номер вручную или использовать кнопку ниже:",
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, process_phone, user_id, building, apartment)

# Обработчик ввода номера телефона
def process_phone(message, user_id, building, apartment):
    phone = None
    
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
    
    # Валидация номера телефона
    is_valid, validation_message = validate_phone(phone)
    
    if not is_valid:
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        phone_btn = types.KeyboardButton("📱 Отправить номер телефона", request_contact=True)
        markup.add(phone_btn)
        
        msg = bot.send_message(
            message.chat.id,
            f"{validation_message}\n\nПожалуйста, введите номер телефона еще раз:",
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_phone, user_id, building, apartment)
        return
    
    # Сохраняем пользователя
    save_user(user_id, building, apartment, phone, 
              message.from_user.username, 
              message.from_user.first_name,
              message.from_user.last_name)
    
    # Уведомляем администраторов
    user_info = {
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name,
        'username': message.from_user.username,
        'id': user_id
    }
    
    notify_admins(user_info, building, apartment, phone)
    
    # Показываем приветственное сообщение
    residents_count = len(get_apartment_residents(building, apartment))
    success_text = f"""
✅ Регистрация завершена!

🏢 Корпус: {building}
🏠 Квартира: {apartment}
📞 Телефон: {phone}

Теперь вы можете писать сообщения в чат!

Добро пожаловать в наш домовой чат! 🏠
    """
    
    bot.send_message(message.chat.id, success_text)
    
    # Убираем клавиатуру
    bot.send_message(
        message.chat.id,
        "Клавиатура скрыта",
        reply_markup=types.ReplyKeyboardRemove()
    )

# ==================== ПРОВЕРКА СООБЩЕНИЙ ====================

# Проверка сообщений от незарегистрированных пользователей
@bot.message_handler(func=lambda message: True)
def check_registration(message):
    # Пропускаем команды
    if message.text and message.text.startswith('/'):
        return
    
    user_id = message.from_user.id
    
    # Если пользователь НЕ зарегистрирован
    if not is_user_registered(user_id):
        try:
            # Удаляем сообщение
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        # Предлагаем зарегистрироваться
        markup = types.InlineKeyboardMarkup()
        register_btn = types.InlineKeyboardButton(
            "📝 Зарегистрироваться", 
            callback_data=f"register_existing_{user_id}"
        )
        markup.add(register_btn)
        
        reminder = bot.send_message(
            message.chat.id,
            f"❌ {message.from_user.first_name}, для отправки сообщений необходимо пройти регистрацию!",
            reply_markup=markup
        )

# Обработчик кнопки регистрации для существующих пользователей
@bot.callback_query_handler(func=lambda call: call.data.startswith('register_existing_'))
def handle_existing_registration(call):
    user_id = int(call.data.split('_')[2])
    
    if is_user_registered(user_id):
        bot.answer_callback_query(call.id, "Вы уже зарегистрированы!")
        return
    
    # Удаляем сообщение с напоминанием
    bot.delete_message(call.message.chat.id, call.message.message_id)
    
    # Запускаем процесс регистрации
    show_building_selection(call.message.chat.id, user_id, is_existing_user=True)

# ==================== КОМАНДЫ АДМИНИСТРАТОРОВ ====================

@bot.message_handler(commands=['admins'])
def show_admins(message):
    if not is_admin(message.from_user.id):
        return
    
    admins_text = "👥 Список администраторов:\n\n"
    
    # Супер-админ
    try:
        super_admin_info = bot.get_chat(SUPER_ADMIN)
        admins_text += f"👑 Супер-админ: {super_admin_info.first_name} (ID: {SUPER_ADMIN})\n\n"
    except:
        admins_text += f"👑 Супер-админ: ID: {SUPER_ADMIN}\n\n"
    
    # Обычные админы
    admins_text += "👥 Обычные администраторы:\n"
    for i, admin_id in enumerate(ADMINS, 1):
        try:
            admin_info = bot.get_chat(admin_id)
            admins_text += f"{i}. {admin_info.first_name} (ID: {admin_id})\n"
        except:
            admins_text += f"{i}. ID: {admin_id}\n"
    
    bot.send_message(message.chat.id, admins_text)

# Команда для добавления нового корпуса
@bot.message_handler(commands=['add_building'])
def add_building_command(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        building_name = message.text.split()[1]
        if add_building(building_name, message.from_user.id):
            bot.reply_to(message, f"✅ Корпус '{building_name}' успешно добавлен!")
        else:
            bot.reply_to(message, f"❌ Корпус '{building_name}' уже существует!")
    
    except IndexError:
        bot.reply_to(message, "❌ Использование: /add_building номер_корпуса")

# Команда для просмотра всех корпусов
@bot.message_handler(commands=['buildings'])
def show_buildings(message):
    if not is_admin(message.from_user.id):
        return
    
    buildings = get_all_buildings()
    if not buildings:
        bot.send_message(message.chat.id, "❌ Нет доступных корпусов")
        return
    
    buildings_text = "🏢 Список всех корпусов:\n\n"
    for i, building in enumerate(sorted(buildings), 1):
        buildings_text += f"{i}. {building}\n"
    
    bot.send_message(message.chat.id, buildings_text)

# Команда для просмотра информации о квартире (только для админов)
@bot.message_handler(commands=['apartment'])
def show_apartment(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "❌ Использование: /apartment корпус номер_квартиры")
            return
            
        building = parts[1]
        apartment = parts[2]
        residents = get_apartment_residents(building, apartment)
        
        if residents:
            result_text = f"🏢 Корпус {building}, 🏠 Квартира {apartment} - {len(residents)} жильцов:\n\n"
            for i, resident in enumerate(residents, 1):
                result_text += f"{i}. {resident.get('first_name')} {resident.get('last_name', '')}\n"
                result_text += f"   📞 {resident.get('phone', 'Не указан')}\n"
                result_text += f"   🔗 @{resident.get('username', 'Нет username')}\n"
                result_text += f"   🕒 {resident.get('registration_time', 'Неизвестно')}\n\n"
        else:
            result_text = f"❌ В квартире {building}-{apartment} нет зарегистрированных жильцов"
        
        bot.send_message(message.chat.id, result_text)
    
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ==================== ЗАПУСК БОТА ====================

if __name__ == "__main__":
    init_db()
    print("🏠 Домовой бот запущен!")
    print(f"👑 Супер-админ: {SUPER_ADMIN}")
    print(f"👥 Обычные админы: {ADMINS}")
    print(f"🏢 Доступные корпуса: {get_all_buildings()}")
    bot.polling()
