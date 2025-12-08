# QR Review Generator SaaS

## Overview

The QR Review Generator is a comprehensive SaaS application built with Flask that allows businesses to generate AI-powered customer reviews. It uses Google's Gemini AI to create unique, SEO-friendly reviews tailored to each business. The system includes a credit-based monetization model, admin panel for management, QR code generation for easy sharing, and is deployed with Firebase Hosting for the frontend and Render for the backend.

## Features

- **Multi-Business Support**: Dynamic business management with unique slugs (/r/<slug>)
- **AI-Generated Reviews**: Uses Gemini 2.0 Flash Exp for authentic, human-sounding reviews
- **Credit System**: Pay-per-review with configurable pricing
- **Admin Panel**: Full CRUD interface for business management
- **QR Code Generation**: Automatic QR codes for review pages
- **Firebase Integration**: Firestore for data storage, Hosting for frontend
- **Responsive UI**: Clean, mobile-friendly interface
- **Secure Authentication**: Service account-based Firebase access

## Architecture

### Backend (Flask + Render)
- **app.py**: Main application with routes for reviews, admin API, QR generation
- **Firebase Firestore**: Stores businesses, review logs
- **Gemini AI**: Generates dynamic reviews based on business details
- **QR Code Library**: Creates QR images for sharing

### Frontend (HTML/JS + Firebase Hosting)
- **index.html**: Review generation page with dynamic slug support
- **admin.html**: Admin interface for managing businesses
- **Firebase Hosting**: Serves static files with URL rewrites

### Deployment
- **Render**: Hosts Flask backend with environment variables
- **Firebase Hosting**: Hosts frontend with rewrites for SPA routing

## Project Structure

```
qr-review-generator/
├── app.py                          # Flask backend application
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Poetry configuration
├── firebase.json                   # Firebase Hosting config
├── .gitignore                      # Git ignore rules
├── README.md                       # This documentation
├── public/                         # Firebase Hosting files
│   ├── index.html
│   └── admin.html
├── templates/                      # Flask templates (for local dev)
│   ├── index.html
│   └── admin.html
├── static/                         # Generated QR codes
└── firebase_json_key/              # Service account keys (ignored)
```

## Installation & Setup

### Prerequisites
- Python 3.8+
- Node.js (for Firebase CLI)
- Google Cloud Project with Firestore enabled
- Gemini API Key

### Local Development

1. **Clone Repository**
   ```bash
   git clone https://github.com/danielmobdev/qr-review-generator.git
   cd qr-review-generator
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   # or
   poetry install
   ```

3. **Firebase Setup**
   - Create project: dan-ai-qr
   - Enable Firestore Database
   - Generate service account key
   - Save key as firebase_json_key/[filename].json

4. **Environment Variables**
   ```bash
   export GEMINI_API_KEY=your_gemini_key
   export FIREBASE_HOSTING_DOMAIN=qr-review-generator.onrender.com
   ```

5. **Run Locally**
   ```bash
   python app.py
   # Access: http://127.0.0.1:8080
   ```

### Firebase Hosting Setup

1. **Install Firebase CLI**
   ```bash
   npm install -g firebase-tools
   firebase login
   ```

2. **Deploy Frontend**
   ```bash
   firebase use dan-ai-qr
   cp templates/* public/
   firebase deploy --only hosting
   ```

### Render Deployment

1. **Connect Repository**
   - Create Render Web Service
   - Connect GitHub repo
   - Set Build Command: `poetry install` or `pip install -r requirements.txt`
   - Set Start Command: `python app.py`

2. **Environment Variables**
   - GEMINI_API_KEY
   - FIREBASE_SERVICE_ACCOUNT_KEY (full JSON)
   - FIREBASE_HOSTING_DOMAIN

3. **Deploy**
   - Manual deploy latest commit

## API Documentation

### Endpoints

#### GET /
Serves the main review page.

#### GET /r/<slug>
Serves review page for specific business.

#### GET /admin
Serves admin panel.

#### GET /generate-review/<slug>
Generates AI review for business.
- **Parameters**: slug (string)
- **Response**: `{"review": "text", "google_link": "url"}`
- **Errors**: 404 (business not found), 403 (inactive), 200 (insufficient credits)

#### GET /api/businesses
Lists all businesses.
- **Response**: Array of business objects

#### POST /api/businesses
Creates new business.
- **Body**: Business data (name, category, city, google_link, credit_balance, price_per_credit, active)
- **Response**: `{"slug": "slug", "qr_url": "url", "url": "url"}`

#### PUT /api/businesses/<slug>
Updates business credits.
- **Body**: `{"credit_balance": number}`

#### POST /api/businesses/<slug>/recharge
Adds credits to business.
- **Body**: `{"credits": number}`

### Data Models

#### Business
```json
{
  "name": "Business Name",
  "category": "Category",
  "city": "City",
  "google_link": "https://...",
  "credit_balance": 100,
  "price_per_credit": 10.0,
  "active": true,
  "created_at": "timestamp"
}
```

#### Review Log
```json
{
  "business_slug": "slug",
  "timestamp": "timestamp",
  "ai_used": true
}
```

## Configuration

### Environment Variables
- `GEMINI_API_KEY`: Google Gemini API key
- `FIREBASE_SERVICE_ACCOUNT_KEY`: Service account JSON
- `FIREBASE_HOSTING_DOMAIN`: Hosting domain (default: qr-review-generator.onrender.com)
- `PORT`: Server port (default: 8080)

### Firebase Config
```javascript
const firebaseConfig = {
  apiKey: "AIzaSyDgJx0B_dsEGbxjvcY74qgh3PfBHm1adrA",
  authDomain: "dan-ai-qr.firebaseapp.com",
  projectId: "dan-ai-qr",
  storageBucket: "dan-ai-qr.firebasestorage.app",
  messagingSenderId: "909101030556",
  appId: "1:909101030556:web:56b397c96dbfe912806159",
  measurementId: "G-ZFCNZ65NS2"
};
```

## Usage

### For Businesses
1. Admin adds business via /admin
2. Gets QR code and review URL
3. Customers scan QR to generate reviews
4. Reviews deduct credits

### For Admins
1. Access /admin
2. Add/edit businesses
3. Monitor credits
4. Recharge as needed

## Security

- Service account authentication for Firebase
- Environment variables for secrets
- No user authentication (admin panel open)
- Firestore security rules restrict access

## Monitoring

- Review logs track usage
- Credit balance monitoring
- Firebase console for analytics

## Troubleshooting

### Common Issues
- **Invalid JWT**: Check service account key
- **No collection created**: Enable Firestore
- **CORS errors**: Ensure backend URL correct
- **QR not loading**: Check static file serving

### Logs
- Flask logs errors
- Firebase console for Firestore issues
- Render logs for deployment

## Contributing

1. Fork repository
2. Create feature branch
3. Make changes
4. Test locally
5. Submit PR

## License

MIT License

## Support

Create GitHub issue for support
