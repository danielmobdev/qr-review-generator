from flask import Flask, render_template, jsonify
import google.generativeai as genai
import os

app = Flask(__name__)

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

model = genai.GenerativeModel('gemini-2.0-flash-exp')

fallback_review = "Dr. Suvendu Narayan Mishra is an excellent Neuropsychiatrist in Bhubaneswar. His compassionate approach and expertise make him highly recommended. Patients appreciate his dedication to their well-being."

def generate_review():
    print("Generating review")
    prompt = "Generate a unique 2-3 sentence patient review for Dr. Suvendu Narayan Mishra, a Neuropsychiatrist in Bhubaneswar. Use simple, layman English that Indians can easily understand. Make it SEO-friendly, human-sounding, positive, and do not mention any diseases, diagnoses, or medical conditions. Include the doctor name, city, and speciality naturally."
    try:
        print("Trying API")
        response = model.generate_content(prompt)
        review = response.text.strip()
        print("API success:", repr(review))
        return review
    except Exception as e:
        print("API failed:", e)
        return fallback_review

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-review')
def generate_review_route():
    review = generate_review()
    return jsonify({'review': review})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
