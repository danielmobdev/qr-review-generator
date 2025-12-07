from flask import Flask, render_template, jsonify, request
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import qrcode
import re

app = Flask(__name__)

# Firebase init
cred_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY')
if cred_json:
    cred = credentials.Certificate(json.loads(cred_json))
    firebase_admin.initialize_app(cred)
elif os.path.exists('firebase_json_key/dan-ai-qr-firebase-adminsdk-fbsvc-434b9431b3.json'):
    with open('firebase_json_key/dan-ai-qr-firebase-adminsdk-fbsvc-434b9431b3.json') as f:
        cred = credentials.Certificate(json.load(f))
    firebase_admin.initialize_app(cred)
else:
    firebase_admin.initialize_app()

db = firestore.client()

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

def slugify(name):
    return re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-').replace('&', 'and'))

def generate_qr(slug, url):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    path = f'static/qr_{slug}.png'
    img.save(path)
    return f'/static/qr_{slug}.png'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/r/<slug>')
def review_page(slug):
    return render_template('index.html', slug=slug)

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/generate-review/<slug>')
def generate_review_route(slug):
    try:
        doc = db.collection('businesses').document(slug).get()
        if not doc.exists:
            return jsonify({'error': 'Business not found'}), 404
        business = doc.to_dict()
        if not business.get('active', False):
            return jsonify({'error': 'Business inactive'}), 403
        if business['credit_balance'] <= 0:
            return jsonify({'review': 'Credits finished. Please contact DAN AI to recharge.', 'google_link': business['google_link']}), 200
        # Deduct credit
        db.collection('businesses').document(slug).update({'credit_balance': firestore.Increment(-1)})
        # Log
        db.collection('review_logs').add({'business_slug': slug, 'timestamp': firestore.SERVER_TIMESTAMP, 'ai_used': True})
        # Generate prompt
        prompt = f"Generate a unique 2-3 sentence patient review for {business['name']}, a {business['category']} in {business['city']}. Use simple, layman English that Indians can easily understand. Make it SEO-friendly, human-sounding, positive, and do not mention any diseases, diagnoses, or medical conditions. Include the business name, city, and category naturally."
        try:
            response = model.generate_content(prompt)
            review = response.text.strip()
        except Exception as e:
            review = f"{business['name']} is an excellent {business['category']} in {business['city']}. Their services are highly recommended."
        return jsonify({'review': review, 'google_link': business['google_link']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/businesses', methods=['GET'])
def get_businesses():
    businesses = db.collection('businesses').stream()
    data = []
    for doc in businesses:
        d = doc.to_dict()
        d['slug'] = doc.id
        data.append(d)
    return jsonify(data)

@app.route('/api/businesses', methods=['POST'])
def add_business():
    try:
        data = request.json
        print("Adding business", data)
        name = data['name']
        slug = slugify(name)
        print("Slug", slug)
        if db.collection('businesses').document(slug).get().exists:
            return jsonify({'error': 'Business already exists'}), 400
        business = {
            'name': name,
            'category': data['category'],
            'city': data['city'],
            'google_link': data['google_link'],
            'credit_balance': data['credit_balance'],
            'price_per_credit': data['price_per_credit'],
            'active': data['active'],
            'created_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('businesses').document(slug).set(business)
        hosting_domain = os.getenv('FIREBASE_HOSTING_DOMAIN', 'dan-ai-qr.web.app')
        url = f"https://{hosting_domain}/r/{slug}"
        qr_url = generate_qr(slug, url)
        print("Business added", slug)
        return jsonify({'slug': slug, 'qr_url': qr_url, 'url': url})
    except Exception as e:
        print("Error adding business", e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/businesses/<slug>', methods=['PUT'])
def update_business(slug):
    data = request.json
    db.collection('businesses').document(slug).update(data)
    return jsonify({'success': True})

@app.route('/api/businesses/<slug>/recharge', methods=['POST'])
def recharge_business(slug):
    data = request.json
    credits = data['credits']
    db.collection('businesses').document(slug).update({'credit_balance': firestore.Increment(credits)})
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
