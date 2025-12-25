# QR Review Generator

A Flask-based SaaS application that generates AI-powered Google reviews using QR codes. Businesses can create review links that customers can scan to generate authentic reviews powered by Google's Gemini AI.

## Features

- QR code generation for review links
- AI-powered review generation using Gemini 2.0
- Firebase Firestore for data storage
- Razorpay integration for payments
- Admin panel for business management
- Credit-based system for review generation

## Tech Stack

- **Backend**: Flask (Python)
- **AI**: Google Gemini 2.0
- **Database**: Firebase Firestore
- **Payments**: Razorpay
- **Deployment**: Google Cloud Run
- **Frontend**: HTML/CSS/JavaScript

## Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/danielmobdev/qr-review-generator.git
   cd qr-review-generator
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file or set environment variables:

   ```bash
   # Firebase (use base64 encoded service account JSON)
   FIREBASE_SERVICE_ACCOUNT_KEY_BASE64=your_base64_encoded_json

   # Gemini AI
   GEMINI_API_KEY=your_gemini_api_key

   # Razorpay (optional for local development)
   RAZORPAY_KEY_ID=your_razorpay_key_id
   RAZORPAY_KEY_SECRET=your_razorpay_key_secret
   RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

   # Flask
   FLASK_SECRET_KEY=your_secret_key
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

   The app will be available at `http://localhost:8080`

## Firebase Setup

1. **Create a Firebase project** at [Firebase Console](https://console.firebase.google.com/)

2. **Enable Firestore Database**

3. **Create a service account**:
   - Go to Project Settings → Service Accounts
   - Generate new private key (JSON file)
   - Encode the JSON file to base64:
     ```bash
     base64 -w 0 your-service-account.json
     ```
   - Set the output as `FIREBASE_SERVICE_ACCOUNT_KEY_BASE64`

## Gemini AI Setup

1. **Get API key** from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Set as `GEMINI_API_KEY` environment variable

## Razorpay Setup

1. **Create Razorpay account** at [Razorpay Dashboard](https://dashboard.razorpay.com/)

2. **Get API Keys**:
   - Go to Settings → API Keys
   - Copy Key ID and Key Secret

3. **Create Webhook**:
   - Go to Settings → Webhooks
   - Add new webhook: `https://your-domain.com/api/payment/webhook`
   - Select event: `payment.captured`
   - Copy the webhook secret

4. **Set environment variables**:
   ```
   RAZORPAY_KEY_ID=rzp_test_...
   RAZORPAY_KEY_SECRET=your_secret
   RAZORPAY_WEBHOOK_SECRET=whsec_...
   ```

## Google Cloud Run Deployment

### Prerequisites

- Google Cloud SDK installed
- Project created in Google Cloud Console
- APIs enabled: Cloud Run, Cloud Build

### Deploy Steps

1. **Build and deploy**:
   ```bash
   gcloud run deploy qr-review-generator \
     --source . \
     --platform managed \
     --region asia-south1 \
     --allow-unauthenticated \
     --set-env-vars="FIREBASE_SERVICE_ACCOUNT_KEY_BASE64=your_base64,FIREBASE_HOSTING_DOMAIN=app.danai.in,GEMINI_API_KEY=your_key,RAZORPAY_KEY_ID=your_id,RAZORPAY_KEY_SECRET=your_secret,RAZORPAY_WEBHOOK_SECRET=your_webhook_secret,FLASK_SECRET_KEY=your_flask_secret"
   ```

2. **Update webhook URL** in Razorpay dashboard with your Cloud Run URL

### Environment Variables for Cloud Run

| Variable | Description | Required |
|----------|-------------|----------|
| `FIREBASE_SERVICE_ACCOUNT_KEY_BASE64` | Base64 encoded Firebase service account JSON | Yes |
| `FIREBASE_HOSTING_DOMAIN` | Your deployment domain | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `RAZORPAY_KEY_ID` | Razorpay Key ID | No* |
| `RAZORPAY_KEY_SECRET` | Razorpay Key Secret | No* |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay Webhook Secret | No* |
| `FLASK_SECRET_KEY` | Flask session secret | Yes |

*Required for payment functionality

## Project Structure

```
qr-review-generator/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── pyproject.toml        # Poetry configuration
├── static/               # Static files (QR codes)
├── templates/            # HTML templates
│   ├── index.html
│   ├── admin_panel.html
│   ├── recharge.html
│   └── login.html
├── public/               # Public static files
└── firebase_json_key/    # Firebase keys (gitignored)
```

## API Endpoints

- `GET /` - Home page
- `GET /r/<slug>` - Review page for business
- `GET /admin` - Admin panel
- `POST /api/businesses` - Create business
- `GET /api/businesses/<slug>` - Get business details
- `PUT /api/businesses/<slug>` - Update business
- `DELETE /api/businesses/<slug>` - Delete business
- `POST /api/payment/create-order` - Create Razorpay order
- `POST /api/payment/verify` - Verify payment
- `POST /api/payment/webhook` - Razorpay webhook

## Recent Updates

- **Razorpay Integration Fix**: Added proper client initialization with graceful error handling for missing credentials
- **Cloud Run Compatibility**: Ensured proper binding and environment variable handling
- **Production Dockerfile**: Updated to use gunicorn for better performance

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is proprietary software. All rights reserved.
