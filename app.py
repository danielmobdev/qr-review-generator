from flask import Flask, render_template, jsonify, request, send_from_directory
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import base64
import qrcode
import re

app = Flask(__name__)

# TEMP diagnostic
print("ENV FIREBASE_SERVICE_ACCOUNT_KEY:", bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")))
print("ENV FIREBASE_SERVICE_ACCOUNT_KEY_BASE64:", bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY_BASE64")))

# Firebase init (Safe for Render + Base64 + No Double Init)
if not firebase_admin._apps:
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY") or os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY_BASE64")

    if not raw:
        raise ValueError("Firebase not initialized. Check FIREBASE_SERVICE_ACCOUNT_KEY or BASE64")

    # Try Base64 first, fallback to plain JSON
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        cred_dict = json.loads(decoded)
    except Exception:
        cred_dict = json.loads(raw)

    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Ensure static directory exists for QR codes
os.makedirs("static", exist_ok=True)

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
    try:
        doc = db.collection('businesses').document(slug).get()
        if doc.exists:
            business = doc.to_dict()
            business_name = business.get('name', 'Review Generator')
        else:
            business_name = 'Review Generator'
    except:
        business_name = 'Review Generator'
    return render_template('index.html', slug=slug, business_name=business_name)

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/qr/<slug>')
def serve_qr(slug):
    path = f'static/qr_{slug}.png'
    if os.path.exists(path):
        return send_from_directory('static', f'qr_{slug}.png')
    else:
        # Regenerate QR
        doc = db.collection('businesses').document(slug).get()
        if doc.exists:
            business = doc.to_dict()
            hosting_domain = os.getenv('FIREBASE_HOSTING_DOMAIN', 'qr-review-generator.onrender.com')
            url = f"https://{hosting_domain}/r/{slug}"
            generate_qr(slug, url)
            return send_from_directory('static', f'qr_{slug}.png')
        else:
            return 'QR not found', 404

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
            place_id_url = f"https://search.google.com/local/writereview?placeid={business.get('place_id', '')}"
            return jsonify({'review': 'Credits finished. Please contact DAN AI to recharge.', 'google_link': place_id_url}), 200
        # Deduct credit
        db.collection('businesses').document(slug).update({'credit_balance': firestore.Increment(-1)})
        # Log
        db.collection('review_logs').add({'business_slug': slug, 'timestamp': firestore.SERVER_TIMESTAMP, 'ai_used': True})
        # Generate prompt for authentic Google Business reviews
        prompt = f"""
Write ONE realistic Google Business review for {business['name']}, an {business['category']} located in {business['city']}.

IMPORTANT RULES:
- Generate ONLY ONE review.
- Length must be 2–3 sentences only.
- Must feel like a REAL human customer wrote it.
- Must NOT look like advertising copy.
- Must sound natural, conversational, and personal.

SEO + SEARCH BEHAVIOR REQUIREMENTS (VERY IMPORTANT):
- Naturally include:
  • Business name: {business['name']}
  • City: {business['city']}
  • Service category: {business['category']}
- The wording should support how people actually search on Google, such as:
  • "digital marketing agency in {business['city']}"
  • "best {business['category']} near me"
  • "SEO and online promotion in {business['city']}"
- Include at least ONE benefit such as:
  • more customer calls
  • better Google visibility
  • more leads
  • improved online presence

MANDATORY CONTENT:
- Mention a real-type service outcome (SEO, ads, social media, Google ranking, leads, etc.)
- End with a strong recommendation like:
  "Highly recommended", "One of the best in {business['city']}", or
  "Must try for any business in {business['city']}".

STYLE:
- Human tone
- Not robotic
- Not repeated structure
- Not keyword-stuffed

Output ONLY the review text. Do NOT include quotes, bullet points, headings, or any explanation.
"""
        try:
            response = model.generate_content(prompt)
            review = response.text.strip()
        except Exception as e:
            review = f"{business['name']} is an excellent {business['category']} in {business['city']}. Their services are highly recommended."
        place_id_url = f"https://search.google.com/local/writereview?placeid={business.get('place_id', '')}"
        return jsonify({'review': review, 'google_link': place_id_url})
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

@app.route('/api/businesses/<slug>', methods=['GET'])
def get_business(slug):
    try:
        doc = db.collection('businesses').document(slug).get()
        if doc.exists:
            business = doc.to_dict()
            business['slug'] = doc.id
            return jsonify(business)
        else:
            return jsonify({'error': 'Business not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            'contact_person_name': data['contact_person_name'],
            'contact_number': data['contact_number'],
            'place_id': data['place_id'],
            'credit_balance': data['credit_balance'],
            'price_per_credit': data['price_per_credit'],
            'active': data['active'],
            'created_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('businesses').document(slug).set(business)
        hosting_domain = os.getenv('FIREBASE_HOSTING_DOMAIN', 'qr-review-generator.onrender.com')
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

@app.route('/api/businesses/<slug>', methods=['DELETE'])
def delete_business(slug):
    try:
        db.collection('businesses').document(slug).delete()
        # Optionally delete QR file
        qr_path = f'static/qr_{slug}.png'
        if os.path.exists(qr_path):
            os.remove(qr_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
