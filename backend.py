import stripe
from flask import Flask, jsonify, render_template

# Ваш секретный ключ Stripe
stripe.api_key = ""

app = Flask(__name__)

# Главная страница, которая отдает HTML (index.html)
@app.route('/')
def index():
    return render_template('index.html')

# Маршрут для создания PaymentIntent
@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    try:
        # Создаем PaymentIntent для $10
        intent = stripe.PaymentIntent.create(
            amount=1000,  # Сумма в центах (1000 = $10)
            currency='usd',
            payment_method_types=['card', 'apple_pay', 'google_pay'],
        )

        return jsonify({
            'clientSecret': intent.client_secret
        })
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
