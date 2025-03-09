import sqlite3

# Функция для обновления количества запросов
def update_user_requests(user_id, new_requests):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET requests = ? WHERE user_id = ?', (new_requests, user_id))
    conn.commit()
    conn.close()

# Функция для обновления статуса оплаты
def update_user_payment_status(user_id, paid_status):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET paid = ? WHERE user_id = ?', (paid_status, user_id))
    conn.commit()
    conn.close()

# Пример использования
user_id = 12345  # Укажите user_id, для которого нужно изменить данные
update_user_requests(user_id, 15)  # Увеличьте количество запросов до 15
update_user_payment_status(user_id, True)  # Установите статус оплаты на True (проплачено)
