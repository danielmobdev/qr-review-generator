from flask import Flask, render_template, jsonify, request, send_from_directory, session, redirect, url_for
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import base64
import qrcode
import re
from datetime import timedelta, datetime
import razorpay
import hmac
import hashlib
import random

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

        # Deduct credit
        db.collection('businesses').document(slug).update({'credit_balance': firestore.Increment(-1)})
        db.collection('review_logs').add({'business_slug': slug, 'timestamp': firestore.SERVER_TIMESTAMP, 'ai_used': True})

        category = business.get("category", "service")
        custom_services = business.get("services", "").strip()
        if custom_services:
            services = custom_services
        else:
            services = CATEGORY_CONTEXT.get(category.lower(), CATEGORY_CONTEXT["default"])

        # Generate unique seed for maximum variation
        timestamp = datetime.now().isoformat()
        device_id = request.headers.get('User-Agent', 'unknown')
        ip_hash = hashlib.md5(request.remote_addr.encode()).hexdigest() if request.remote_addr else 'local'
        unique_seed = hashlib.md5(f"{slug}{timestamp}{device_id}{ip_hash}{random.randint(1000,9999)}".encode()).hexdigest()

        # ULTIMATE 2025 SEO-OPTIMIZED PROMPT
        # Based on research: 100+ words (ideally 200+ characters) stay at top longer, more visibility
        prompt = f"""You are writing ONE authentic Google Business review as a real Indian customer.

BUSINESS DETAILS:
Name: {business['name']}
Category: {category}
City: {business['city']}
Services Available: {services}

UNIQUENESS SEED: {unique_seed}
(This seed MUST influence your word choices, sentence structure, and approach to create completely different output)

═══════════════════════════════════════════════════════════════════════════
GOOGLE 2025 SEO OPTIMIZATION REQUIREMENTS (PROVEN BY RESEARCH)
═══════════════════════════════════════════════════════════════════════════

📊 LENGTH REQUIREMENT (CRITICAL FOR SEO):
✓ TARGET: 100-150 words (this is the SWEET SPOT for Google ranking)
✓ MINIMUM: 75 words (never go below this)
✓ Research proves: Reviews 100+ words stay at top of listings LONGER
✓ Character count: Aim for 200+ characters minimum

WHY THIS LENGTH MATTERS:
• Longer reviews rank higher in "Most Relevant" section
• Google's algorithm favors detailed, informative reviews
• More visibility = more impact on local SEO
• 5-star reviews average 74 words, but 100+ gets better placement

═══════════════════════════════════════════════════════════════════════════
SEO KEYWORD INTEGRATION (NATURAL & ORGANIC)
═══════════════════════════════════════════════════════════════════════════

MUST INCLUDE (distributed naturally across the review):

1. BUSINESS NAME: "{business['name']}" - mention ONCE, naturally placed

2. LOCATION KEYWORDS (pick 2-3 variations):
   ✓ "in {business['city']}"
   ✓ "near me in {business['city']}"
   ✓ "around {business['city']}"
   ✓ "{business['city']} area"
   ✓ "local {category} in {business['city']}"

3. CATEGORY KEYWORDS (use variations, not exact):
   ✓ Primary: {category}
   ✓ Related searches: "best {category}", "reliable {category}", "professional {category}"
   ✓ Long-tail: "{category} services", "{category} expert"

4. SERVICE-SPECIFIC KEYWORDS (from services list):
   Pick 2-3 specific services from: {services}
   Mention them as RESULTS/EXPERIENCES, not just list them

5. CREDIBILITY MARKERS (use 2-3):
   professional, expert, experienced, reliable, thorough, effective, quality,
   systematic, comprehensive, skilled, knowledgeable, competent

6. OUTCOME WORDS (include 1-2):
   results, improvement, difference, impact, change, progress, outcome,
   success, benefit, solution, helped, resolved

7. SEARCH INTENT PHRASES (naturally embed 1-2):
   "looking for {category} in {business['city']}"
   "needed {category} services"
   "searching for reliable {category}"
   "wanted professional help with"

═══════════════════════════════════════════════════════════════════════════
REVIEW STRUCTURE (100-150 WORDS FORMAT)
═══════════════════════════════════════════════════════════════════════════

PARAGRAPH 1 (35-50 words):
• Start with WHY you needed the service (problem/situation)
• Include search intent phrase naturally
• Mention location and how you found them
• Set context for the experience

PARAGRAPH 2 (40-60 words):
• Describe the SPECIFIC service/experience in detail
• Mention business name naturally
• Include 2-3 service-related keywords
• Talk about the professional approach/process
• Add credibility markers

PARAGRAPH 3 (25-40 words):
• Focus on RESULTS and OUTCOMES achieved
• Include category keyword variation
• Add timeframe if relevant (recently, last month, etc.)
• End with natural recommendation
• Show genuine satisfaction

═══════════════════════════════════════════════════════════════════════════
TONE & LANGUAGE RULES
═══════════════════════════════════════════════════════════════════════════

PROFESSIONAL BUT CONVERSATIONAL:
✓ Simple Indian English (everyday language, not formal)
✓ First-person perspective (I, my, me)
✓ Past tense for experiences
✓ Present tense for results/current state
✓ Clear, direct sentences
✓ Genuine and sincere tone

FORBIDDEN WORDS/PHRASES (NEVER USE):
❌ "I recently visited" or "I went to"
❌ "amazing", "fantastic", "awesome", "incredible"
❌ "highly recommend" (use natural alternatives)
❌ "best ever", "life-changing"
❌ "honestly", "literally"
❌ Emojis or exclamation marks
❌ Marketing buzzwords
❌ Repetitive patterns from previous reviews

APPROVED VOCABULARY (Use varied combinations):
✓ Adjectives: professional, reliable, effective, thorough, systematic, clear, helpful,
  patient, knowledgeable, experienced, skilled, competent, attentive, responsive

✓ Outcome verbs: helped, improved, resolved, addressed, clarified, guided, supported,
  facilitated, enabled, achieved, delivered, provided

✓ Experience words: consultation, guidance, approach, process, treatment, service,
  discussion, assessment, analysis, strategy, plan

═══════════════════════════════════════════════════════════════════════════
VARIATION STRATEGIES (FORCE UNIQUENESS)
═══════════════════════════════════════════════════════════════════════════

Based on SEED {unique_seed}, RANDOMIZE:

OPENING STYLE (Pick ONE, never repeat):
A) Start with the problem/need
B) Start with discovery/search process
C) Start with decision to seek help
D) Start with someone's recommendation
E) Start with comparison to other options
F) Start with initial hesitation/concern
G) Start with specific situation/context
H) Start with timeframe reference

MIDDLE FLOW (Pick ONE):
A) Chronological: First visit → Process → Follow-up
B) Thematic: Service quality → Professional approach → Results
C) Comparative: Expected vs Actual experience
D) Problem-Solution: Challenge → How they helped → Outcome
E) Detailed: Specific aspects → Overall impression → Impact

ENDING STYLE (Pick ONE):
A) Result-focused conclusion
B) Future commitment (will continue/return)
C) Recommendation with specific reason
D) Gratitude with outcome mention
E) Current state/improvement description

SENTENCE VARIETY:
- Mix short (5-8 words) and longer sentences (15-20 words)
- Use 2-3 compound sentences with "and", "but", "while"
- Include 1-2 complex sentences with context
- Vary where business name appears (early/middle/late)

═══════════════════════════════════════════════════════════════════════════
SPECIFIC EXAMPLES BY CATEGORY (UNDERSTAND, DON'T COPY)
═══════════════════════════════════════════════════════════════════════════

DOCTOR/PSYCHIATRIST/CLINIC:
"I was dealing with persistent anxiety and sleep issues when I started searching for professional help in {{city}}. A colleague mentioned {{business name}}, and their approach to mental health care proved to be exactly what I needed. The consultation was thorough and unhurried, focusing on understanding my specific situation rather than offering generic solutions. Dr. {{name}} took time to explain different treatment options and helped me develop practical coping strategies. Over the past three months, I've noticed significant improvement in managing daily stress and my sleep patterns have normalized considerably. The clinic environment is calm and private, which helps during sessions. For anyone looking for genuine psychiatric care in {{city}} that combines professional expertise with a patient-centered approach, this has been the right choice. The systematic method and clear communication made the entire process feel manageable and effective."

RESTAURANT:
"Finding authentic North Indian cuisine in {{city}} had been a challenge until someone recommended {{business name}} during a work lunch discussion. What stands out immediately is their attention to flavor balance and spice levels. We tried their butter chicken and dal makhani, both prepared with techniques that brought out authentic taste without overwhelming heat. The paneer was fresh and the naan came straight from the tandoor. Service was prompt without being rushed, and the staff actually asked about spice preferences rather than assuming. The portion sizes were generous and pricing felt reasonable for the quality delivered. We've been back twice in the past month, and consistency has been maintained across visits. The ambience is simple but clean, with comfortable seating and good ventilation. For reliable Indian food in {{city}} that doesn't compromise on authentic preparation methods, this place delivers on expectations. The kitchen clearly understands regional cooking styles and maintains quality standards."

DIGITAL MARKETING/SEO:
"Our small business struggled with online visibility for over a year despite having a decent website and social media presence. We researched several marketing agencies in {{city}} before connecting with {{business name}}, and their data-driven approach to digital strategy made sense from the first discussion. Rather than promising overnight results, they conducted a thorough audit of our current online assets and identified specific gaps in our SEO and Google Business optimization. Over the following three months, they implemented systematic improvements to our content structure, local search presence, and ad targeting. We saw measurable increases in website traffic and the quality of leads improved noticeably. The team provided regular updates with clear analytics and explained changes in terms we could understand. Their expertise in local SEO particularly helped our {{city}} market visibility. The results justified the investment, and we've continued working with them for six months now. For businesses in {{city}} needing practical digital marketing support backed by actual performance metrics, their professional and transparent approach delivers consistent value."

═══════════════════════════════════════════════════════════════════════════
FINAL QUALITY CHECKLIST
═══════════════════════════════════════════════════════════════════════════

Before generating, verify:
☑ Word count: 100-150 words (count carefully)
☑ Business name mentioned exactly once
☑ City mentioned 1-2 times naturally
☑ Category keywords integrated (not forced)
☑ 2-3 specific services described as experiences
☑ At least 2 credibility markers included
☑ Outcome/result clearly stated
☑ No forbidden phrases used
☑ No repetitive patterns from typical reviews
☑ Sounds genuinely human and personal
☑ Professional but conversational tone
☑ Location keywords naturally embedded
☑ Search intent phrases included
☑ Clear paragraph structure (3 sections)

═══════════════════════════════════════════════════════════════════════════
YOUR TASK NOW
═══════════════════════════════════════════════════════════════════════════

Write ONE unique, SEO-optimized Google review that:
• Is 100-150 words (this is critical for Google ranking)
• Uses the unique seed to force completely different structure
• Includes all SEO elements naturally
• Tells a genuine, detailed story
• Provides specific value to future readers
• Ranks high in Google's "Most Relevant" algorithm

OUTPUT ONLY THE REVIEW TEXT.
No quotes. No explanation. No formatting. Just the review.

Begin now:"""

        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=1.2,  # Higher creativity
                    top_p=0.95,
                    top_k=50,
                    max_output_tokens=200,
                )
            )
            review = response.text.strip()

            # Clean up the review
            review = review.strip('"').strip("'").strip('`')
            review = review.replace('\n', ' ').replace('  ', ' ')

            # Remove any markdown or formatting
            review = re.sub(r'\*\*', '', review)
            review = re.sub(r'__', '', review)

            # Ensure proper punctuation
            if not review.endswith('.'):
                review += '.'

            # Final quality check - if too short or too long, regenerate with fallback
            word_count = len(review.split())
            if word_count < 30 or word_count > 100:
                review = f"The professional service at {business['name']} in {business['city']} has consistently delivered excellent results for {category} needs. Their systematic approach and expertise in {services.split(',')[0].strip()} made a significant difference. The quality of work and attention to detail reflects their commitment to client satisfaction."

        except Exception as e:
            # Professional fallback review
            review = f"Seeking reliable {category} services in {business['city']} led me to {business['name']}, where the professional approach and expertise in {services.split(',')[0].strip() if services else category} delivered exceptional results. The systematic process and quality standards exceeded my expectations."

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
