from flask import Flask, render_template, jsonify, request, send_from_directory, session, redirect, url_for
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import base64
import qrcode
import re
from datetime import timedelta
import razorpay
import hmac
import hashlib

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.permanent_session_lifetime = timedelta(hours=1)

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

CATEGORY_CONTEXT = {
    "ai digital marketing": "SEO, Google Business optimization, online ads, lead generation, social media promotion",
    "digital marketing": "SEO, Google ads, social media marketing, lead generation",
    "doctor": "consultation, diagnosis, treatment, patient care, clinic hygiene",
    "clinic": "medical consultation, treatment, clean environment, polite staff",
    "hospital": "medical treatment, emergency care, nursing, hygiene",
    "photography": "wedding photography, videography, photo quality, timely delivery",
    "studio": "photoshoot, video shoot, editing, professional output",
    "restaurant": "food taste, service, ambience, hygiene",
    "hotel": "stay comfort, cleanliness, staff service, location",
    "salon": "haircut, styling, hygiene, staff behavior",
    "gym": "training, equipment, cleanliness, trainer support",
    "real estate": "property dealing, site visits, legal process, support",
    "education": "teaching quality, guidance, results, student support",
    "default": "service quality, professional staff, customer satisfaction"
}

def slugify(name):
    return re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-').replace('&', 'and'))

def is_valid_place_id(place_id):
    if not place_id or not isinstance(place_id, str):
        return False
    # Google Place IDs are typically alphanumeric strings, often starting with "ChI"
    # They should not contain template literals or special characters
    if '{' in place_id or '}' in place_id or place_id.strip() == '':
        return False
    # Basic validation: should be alphanumeric with some allowed characters
    return bool(re.match(r'^[A-Za-z0-9_-]+$', place_id.strip()))

def get_google_review_url(place_id, business_name, city):
    if is_valid_place_id(place_id):
        return f"https://search.google.com/local/writereview?placeid={place_id}"
    else:
        # Fallback to Google search for the business
        query = f"{business_name} {city} reviews".replace(' ', '+')
        return f"https://www.google.com/search?q={query}"

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
    doc = db.collection('businesses').document(slug).get()
    if not doc.exists:
        return "Business not found", 404

    business = doc.to_dict()
    if business.get("credit_balance", 0) <= 0:
        return redirect(f"/recharge/{slug}")

    return render_template('index.html', slug=slug)

@app.route("/recharge/<slug>")
def recharge_page(slug):
    doc = db.collection("businesses").document(slug).get()
    if not doc.exists:
        return "Business not found", 404
    business = doc.to_dict()
    return render_template("recharge.html", business=business, slug=slug)

@app.route('/admin')
def admin():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('admin_panel.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            user_doc = db.collection('users').document(username).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                stored_password = user_data.get('password')
                if stored_password == password:
                    session.permanent = True
                    session['user'] = username
                    return redirect(url_for('admin'))
                else:
                    return render_template('login.html', error='Invalid credentials')
            else:
                return render_template('login.html', error='User not found')
        except Exception as e:
            return render_template('login.html', error=f'Login failed: {str(e)}')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/qr/<slug>')
def serve_qr(slug):
    path = f'static/qr_{slug}.png'
    if os.path.exists(path):
        return send_from_directory('static', f'qr_{slug}.png')
    else:
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
            place_id_url = get_google_review_url(business.get('place_id', ''), business.get('name', ''), business.get('city', ''))
            return jsonify({'review': 'Credits finished. Please contact DAN AI to recharge.', 'google_link': place_id_url}), 200
        db.collection('businesses').document(slug).update({'credit_balance': firestore.Increment(-1)})
        db.collection('review_logs').add({'business_slug': slug, 'timestamp': firestore.SERVER_TIMESTAMP, 'ai_used': True})
        category = business.get("category", "service")
        custom_services = business.get("services", "").strip()
        if custom_services:
            services = custom_services
        else:
            services = CATEGORY_CONTEXT.get(category.lower(), CATEGORY_CONTEXT["default"])

        prompt = f"""
You are generating ONE genuine Google Business review written by a real Indian customer.

The review must sound natural, personal, and unplanned — like someone typing from real experience.
Do NOT sound like an advertisement.
Do NOT follow a fixed structure.

BUSINESS DETAILS:
- Name: {business['name']}
- Category: {category}
- City: {business['city']}
- Services: {services}

---------------------------------------
STRICT RULES (VERY IMPORTANT)
---------------------------------------
1. Write ONLY 2–3 natural sentences.
2. Do NOT start with the business name or the city.
3. Mention the business name EXACTLY once.
4. Mention the city EXACTLY once.
5. Mention the category ONLY indirectly (never repeat fixed phrases).
6. Convert services into real-life experiences — NEVER list services.
7. Keep simple Indian English (calm, polite, everyday tone).
8. No emojis, no exclamation marks.
9. No hype words like wow, amazing, best, honestly.
10. Every review must feel different from the previous one.

---------------------------------------
HOW TO USE SERVICES (CRITICAL)
---------------------------------------
From the provided services, PICK ONLY ONE OR TWO ideas
and convert them into a HUMAN EXPERIENCE.

Examples (DO NOT COPY, JUST UNDERSTAND):
- psychiatrist → feeling anxious, habit issues, low mood, stress
- clinic → calm discussion, clear guidance, clean environment
- restaurant → food taste, service speed, comfort
- hotel → clean room, quiet stay, helpful staff
- salon → neat results, hygiene, relaxed feel
- gym → trainer support, consistency, energy
- marketing agency → better visibility, leads, communication
- photography → quality output, coordination, delivery

NEVER mention service names directly.
ALWAYS describe how it felt for the customer.

---------------------------------------
OPENING (RANDOM, NATURAL – PICK ONE STYLE)
---------------------------------------
- A few things needed sorting out.
- Things didn’t feel clear at first.
- Someone I trust suggested this place.
- I decided to get some proper guidance.
- I was looking for a clearer way forward.
- It felt like the right time to get help.
- I wanted to understand things better.
- Things were getting a bit difficult.
- I needed a different perspective.
- I chose to approach this calmly.

---------------------------------------
BUSINESS NAME RULE
---------------------------------------
Mention {business['name']} EXACTLY once,
in sentence 2 or 3, naturally.

Examples:
- Talking to {business['name']} helped…
- The guidance at {business['name']} felt…
- Visiting {business['name']} made things clearer…

---------------------------------------
CITY RULE
---------------------------------------
Mention {business['city']} EXACTLY once,
separate from the business name.

Examples:
- here in {business['city']}
- around {business['city']}
- in this part of {business['city']}

---------------------------------------
ENDING (PICK ONE, KEEP IT SIMPLE)
---------------------------------------
- Things feel easier to manage now.
- I’m feeling more settled now.
- It helped me think clearly.
- It’s been steady and helpful.
- It made a difference for me.
- I feel more confident now.
- It worked well for my situation.
- Glad I went ahead with this.

---------------------------------------
FINAL OUTPUT RULE
---------------------------------------
Return ONLY the final review text.
No quotes.
No explanations.
No formatting.
"""
        try:
            response = model.generate_content(prompt)
            review = response.text.strip()
            review = re.sub(r"[^a-zA-Z0-9.,'\s]", "", review)  # Hard clean special chars
        except Exception as e:
            review = f"{business['name']} is an excellent {business['category']} in {business['city']}. Their services are highly recommended."
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,' "
        review = "".join(c for c in review if c in allowed)
        place_id_url = get_google_review_url(business.get('place_id', ''), business.get('name', ''), business.get('city', ''))
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
        name = data['name']
        slug = slugify(name)
        if db.collection('businesses').document(slug).get().exists:
            return jsonify({'error': 'Business already exists'}), 400
        
        place_id = data.get('place_id', '')
        if place_id and not is_valid_place_id(place_id):
            return jsonify({'error': 'Invalid Google Place ID format'}), 400
        
        business = {
            'name': name,
            'category': data['category'],
            'city': data['city'],
            'contact_person_name': data['contact_person_name'],
            'contact_number': data['contact_number'],
            'place_id': place_id,
            'services': data['services'],
            'credit_balance': data['credit_balance'],
            'price_per_credit': data['price_per_credit'],
            'active': data['active'],
            'created_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('businesses').document(slug).set(business)
        hosting_domain = os.getenv('FIREBASE_HOSTING_DOMAIN', 'qr-review-generator.onrender.com')
        url = f"https://{hosting_domain}/r/{slug}"
        qr_url = generate_qr(slug, url)
        return jsonify({'slug': slug, 'qr_url': qr_url, 'url': url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/businesses/<slug>', methods=['PUT'])
def update_business(slug):
    data = request.json
    if 'place_id' in data:
        place_id = data.get('place_id', '')
        if place_id and not is_valid_place_id(place_id):
            return jsonify({'error': 'Invalid Google Place ID format'}), 400
    db.collection('businesses').document(slug).update(data)
    return jsonify({'success': True})

@app.route('/api/businesses/<slug>/recharge', methods=['POST'])
def recharge_business(slug):
    data = request.json
    credits = data['credits']
    db.collection('businesses').document(slug).update({'credit_balance': firestore.Increment(credits)})
    return jsonify({'success': True})

@app.route('/api/businesses/<slug>/payments', methods=['GET'])
def get_business_payments(slug):
    try:
        payments = db.collection('payments').where('slug', '==', slug).order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        data = []
        for payment in payments:
            p = payment.to_dict()
            data.append({
                'credits': p.get('credits', 0),
                'amount': p.get('amount', 0),
                'unit_price': p.get('unit_price', 0),
                'timestamp': p.get('timestamp').isoformat() if p.get('timestamp') else None
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/businesses/<slug>', methods=['DELETE'])
def delete_business(slug):
    try:
        db.collection('businesses').document(slug).delete()
        qr_path = f'static/qr_{slug}.png'
        if os.path.exists(qr_path):
            os.remove(qr_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/payment/create-order", methods=["POST"])
def create_payment_order():
    data = request.json
    slug = data.get("slug")
    credits = int(data.get("credits", 0))
    business = db.collection("businesses").document(slug).get().to_dict()
    amount = int(business.get("price_per_credit", 0) * credits * 100)

    order = razor_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1,
        "notes": {"slug": slug, "credits": credits}
    })

    return jsonify({"order_id": order["id"], "key": RAZORPAY_KEY_ID, "amount": amount})

@app.route("/api/payment/verify", methods=["POST"])
def verify_payment():
    data = request.json
    payment_id = data.get("payment_id")
    order_id = data.get("order_id")
    signature = data.get("signature")
    slug = data.get("slug")
    credits = int(data.get("credits", 0))

    params_dict = {
        'razorpay_order_id': order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature
    }

    try:
        razor_client.utility.verify_payment_signature(params_dict)
    except:
        return jsonify({"error": "Payment verification failed"}), 400

    business = db.collection("businesses").document(slug).get().to_dict()

    db.collection("businesses").document(slug).update({
        "credit_balance": firestore.Increment(credits)
    })

    payment_record = {
        "slug": slug,
        "business_name": business.get("name", ""),
        "credits": credits,
        "amount": business.get("price_per_credit", 0) * credits,
        "unit_price": business.get("price_per_credit", 0),
        "razorpay_payment_id": payment_id,
        "razorpay_order_id": order_id,
        "payment_status": "success",
        "timestamp": firestore.SERVER_TIMESTAMP,
        "added_by": session.get("user", "system")
    }

    db.collection("payments").add(payment_record)

    return jsonify({"success": True})

@app.route("/api/payment/webhook", methods=["POST"])
def razorpay_webhook():
    webhook_body = request.data
    signature = request.headers.get("X-Razorpay-Signature")

    expected_sig = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        webhook_body,
        hashlib.sha256
    ).hexdigest()

    if signature != expected_sig:
        return "Invalid signature", 400

    payload = json.loads(webhook_body)
    event = payload.get("event")
    if event == "payment.captured":
        payment = payload["payload"]["payment"]["entity"]
        notes = payment.get("notes", {})
        slug = notes.get("slug")
        credits = int(notes.get("credits", 0))

        db.collection("businesses").document(slug).update({
            "credit_balance": firestore.Increment(credits)
        })
        db.collection("payments").add({
            "slug": slug,
            "credits": credits,
            "amount": payment.get("amount", 0)/100,
            "razorpay_payment_id": payment.get("id"),
            "timestamp": firestore.SERVER_TIMESTAMP
        })
    return "OK", 200

@app.route('/api/payments', methods=['GET'])
def get_all_payments():
    try:
        payments = db.collection('payments').order_by(
            'timestamp', direction=firestore.Query.DESCENDING
        ).stream()

        data = []
        for payment in payments:
            p = payment.to_dict()

            business_doc = db.collection('businesses').document(p.get('slug', '')).get()
            business_name = business_doc.to_dict().get('name', 'Unknown') if business_doc.exists else 'Unknown'

            ts = p.get('timestamp')
            formatted_time = ts.strftime('%d %b %Y • %I:%M %p') if ts else 'N/A'

            unit_price = 0
            if p.get('credits', 0) > 0:
                unit_price = p.get('amount', 0) / p.get('credits', 1)

            data.append({
                'business_name': business_name,
                'slug': p.get('slug', ''),
                'credits': p.get('credits', 0),
                'amount': p.get('amount', 0),
                'unit_price': unit_price,
                'razorpay_payment_id': p.get('razorpay_payment_id', ''),
                'timestamp': formatted_time
            })

        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
