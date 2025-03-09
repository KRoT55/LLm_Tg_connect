import sqlite3

# Создание базы данных
def create_db():
    conn = sqlite3.connect('users.db')  # Имя базы данных
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (user_id INTEGER PRIMARY KEY, requests INTEGER, paid BOOLEAN)''')
    conn.commit()
    conn.close()

# Проверка количества запросов пользователя
def get_user_requests(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT requests FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    else:
        return 0

# Увеличение количества запросов
def increment_user_requests(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, requests, paid) VALUES (?, ?, ?)',
                   (user_id, get_user_requests(user_id) + 1, False))  # Платеж по умолчанию не оплачен
    conn.commit()
    conn.close()

# Проверка, оплатил ли пользователь
def check_payment(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT paid FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]  # Если платил, возвращаем True, иначе False
    return False

# Обновление статуса оплаты
def update_payment_status(user_id, paid):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET paid = ? WHERE user_id = ?', (paid, user_id))
    conn.commit()
    conn.close()
