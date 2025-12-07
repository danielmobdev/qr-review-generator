# QR Review Generator

## Overview

The QR Review Generator is a web application built with Flask that generates AI-powered patient reviews for Dr. Suvendu Narayan Mishra, a Neuropsychiatrist at Serenity Clinic in Bhubaneswar, Odisha, India. The application uses Google's Gemini AI to create unique, SEO-friendly reviews in simple English suitable for Indian audiences. It features a simple web interface where users can generate and automatically copy reviews to their clipboard, then share them via a predefined Google link.

## Features

- **AI-Generated Reviews**: Utilizes Google's Gemini 2.0 Flash Exp model to generate authentic-sounding patient reviews.
- **Fallback Mechanism**: If the AI API is unavailable or quota is exceeded, provides a static fallback review.
- **Automatic Clipboard Copy**: Reviews are automatically copied to the user's clipboard upon generation.
- **One-Click Sharing**: Redirects to a Google share link after generating a review.
- **Simple UI**: Clean, responsive web interface with minimal design.
- **Docker Support**: Includes a Dockerfile for containerized deployment.

## Project Structure

```
qr-review-generator/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker configuration
├── README.md              # This documentation
└── templates/
    └── index.html         # Web interface template
```

## Firebase Setup

- Project Name: DAN AI QR
- Project ID: dan-ai-qr
- Project Number: 909101030556

Create a Firestore database in this project. Create collections as per schema below.

For deployment, generate a Service Account Key (JSON) and set `FIREBASE_SERVICE_ACCOUNT_KEY` environment variable to the JSON content as string.

Set `FIREBASE_HOSTING_DOMAIN` to your Firebase Hosting domain (e.g., dan-ai-qr.web.app).

## Firebase Hosting Deployment

1. Install Firebase CLI: `npm install -g firebase-tools`
2. Login: `firebase login`
3. Use project: `firebase use dan-ai-qr`
4. Deploy: `firebase deploy --only hosting`

The frontend will be hosted at `https://dan-ai-qr.web.app`

## Installation

### Prerequisites

- Python 3.7+
- Google Gemini API Key (sign up at [Google AI Studio](https://makersuite.google.com/app/apikey))
- Firebase Project (see above)

### Local Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/danielmobdev/qr-review-generator.git
   cd qr-review-generator
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set the Gemini API key:
   ```bash
   export GEMINI_API_KEY=your_api_key_here
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to `http://127.0.0.1:8080`

### Docker Setup

1. Build the Docker image:
   ```bash
   docker build -t qr-review-generator .
   ```

2. Run the container:
   ```bash
   docker run -p 8080:8080 -e GEMINI_API_KEY=your_api_key_here qr-review-generator
   ```

## Usage

1. Access the web application in your browser.
2. The page will automatically load and display a generated review.
3. The review is automatically copied to your clipboard.
4. Click "New Review" to generate another review.
5. The application redirects to a Google share link for easy sharing.

## API Endpoints

- `GET /`: Serves the main web interface.
- `GET /generate-review`: Returns a JSON response with a generated review.
  - Response format: `{"review": "Generated review text"}`

## Configuration

### Environment Variables

- `GEMINI_API_KEY`: Your Google Gemini API key (required for AI generation).
- `PORT`: Port number for the Flask server (default: 8080).

### AI Prompt

The application uses the following prompt to generate reviews:

"Generate a unique 2-3 sentence patient review for Dr. Suvendu Narayan Mishra, a Neuropsychiatrist in Bhubaneswar. Use simple, layman English that Indians can easily understand. Make it SEO-friendly, human-sounding, positive, and do not mention any diseases, diagnoses, or medical conditions. Include the doctor name, city, and speciality naturally."

## Dependencies

- Flask: Web framework
- google-generativeai: Google Gemini AI SDK

## Deployment

### Production Considerations

- Use a production WSGI server like Gunicorn instead of Flask's development server.
- Set `debug=False` in production.
- Secure the API key properly (use environment variables or secret management).
- Consider rate limiting and authentication for the API endpoints.

### Example Production Deployment

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test thoroughly.
5. Submit a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support or questions, please open an issue on the GitHub repository.
