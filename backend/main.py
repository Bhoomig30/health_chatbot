from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
from functools import wraps
import json
from waitress import serve
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Create uploads folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Mock database
users_db = {}
sessions_db = {}
chat_history = {}

# ============================================================================
# AUTHENTICATION MIDDLEWARE
# ============================================================================

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token.split(' ')[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data['user_id']
        except:
            return jsonify({'message': 'Token is invalid'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# ============================================================================
# ROOT ROUTE
# ============================================================================

@app.route('/')
def index():
    return jsonify({
        'message': 'HealthCare AI API is running!',
        'version': '1.0.0',
        'endpoints': {
            'auth': '/api/auth/login, /api/auth/register',
            'chat': '/api/chat',
            'upload': '/api/upload',
            'news': '/api/health-news',
            'helplines': '/api/emergency-helplines'
        }
    }), 200

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        name = data.get('name', email.split('@')[0])
        
        if not email or not password:
            return jsonify({'message': 'Email and password required'}), 400
        
        if email in users_db:
            return jsonify({'message': 'User already exists'}), 400
        
        user_id = str(len(users_db) + 1)
        users_db[email] = {
            'id': user_id,
            'password': generate_password_hash(password),
            'name': name,
            'email': email
        }
        
        return jsonify({
            'message': 'User registered successfully',
            'email': email
        }), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'message': 'Email and password required'}), 400
        
        # For demo: create user if doesn't exist
        if email not in users_db:
            user_id = str(len(users_db) + 1)
            users_db[email] = {
                'id': user_id,
                'password': generate_password_hash(password),
                'name': email.split('@')[0],
                'email': email
            }
        
        user = users_db[email]
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user['id'],
            'email': email,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        session_id = f"session_{user['id']}_{datetime.datetime.now().timestamp()}"
        sessions_db[session_id] = {
            'user_id': user['id'],
            'created_at': datetime.datetime.now().isoformat()
        }
        
        return jsonify({
            'token': token,
            'sessionId': session_id,
            'user': {
                'id': user['id'],
                'name': user['name'],
                'email': email
            }
        }), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# ============================================================================
# CHAT ROUTES
# ============================================================================

@app.route('/api/chat', methods=['POST'])
@token_required
def chat(current_user):
    try:
        data = request.get_json()
        message = data.get('message')
        session_id = data.get('sessionId')
        
        if not message:
            return jsonify({'message': 'Message is required'}), 400
        
        # Store chat history
        if session_id not in chat_history:
            chat_history[session_id] = []
        
        chat_history[session_id].append({
            'role': 'user',
            'message': message,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
        # Generate AI response
        response = generate_response(message)
        
        chat_history[session_id].append({
            'role': 'bot',
            'message': response,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
        return jsonify({
            'response': response,
            'sessionId': session_id
        }), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

def generate_response(message):
    """Generate health-related responses"""
    msg_lower = message.lower()
    
    responses = {
        'cold': "Common cold symptoms include runny nose, sore throat, cough, and mild fever. Rest, stay hydrated, and consider OTC medications. If symptoms persist beyond 10 days, consult a doctor. 🤧",
        'fever': "For fever: Rest, drink fluids, take fever-reducing medication if needed. Seek medical attention if fever exceeds 103°F (39.4°C) or lasts more than 3 days. 🌡️",
        'stress': "To reduce stress: Practice deep breathing, exercise regularly, get 7-8 hours of sleep, meditate, and talk to someone you trust. Consider professional help if needed. 😌",
        'diet': "Healthy diet tips: Eat colorful fruits and vegetables, choose whole grains, include lean proteins, stay hydrated with 8-10 glasses of water, limit processed foods. 🥗",
        'exercise': "Exercise recommendations: Aim for 150 minutes of moderate activity weekly, include strength training 2x/week, start slowly, stay consistent, and always warm up. 💪",
        'sleep': "Better sleep tips: Maintain consistent sleep schedule, avoid screens before bed, keep room cool and dark, limit caffeine after 2 PM, try relaxation exercises. 😴",
        'headache': "For headaches: Rest in quiet dark room, apply compress, stay hydrated, avoid screens. If severe or frequent, consult a doctor. 🧠",
        'diabetes': "Diabetes management: Monitor blood sugar regularly, follow prescribed medication, eat balanced meals, exercise, manage stress. Work with your healthcare team. 🩺",
        'heart': "Heart health: Exercise regularly, eat heart-healthy diet, don't smoke, limit alcohol, manage stress, maintain healthy weight, get regular check-ups. ❤️",
        'anxiety': "Managing anxiety: Practice deep breathing, try grounding exercises, exercise regularly, get adequate sleep, limit caffeine. Seek professional help if needed. 💙"
    }
    
    # Check for keywords
    for keyword, response in responses.items():
        if keyword in msg_lower:
            return response
    
    # Check for greetings
    if any(word in msg_lower for word in ['hi', 'hello', 'hey']):
        return "Hello! 👋 How can I help you today? I can assist with health questions, diet advice, exercise tips, and finding healthcare providers."
    
    # Check for thanks
    if any(word in msg_lower for word in ['thank', 'thanks']):
        return "You're welcome! 😊 Is there anything else you'd like to know about your health?"
    
    # Default response
    return "I'm here to help with your health questions! Ask me about symptoms, diet, exercise, stress management, or use the sidebar to find hospitals and doctors. 💙"

# ============================================================================
# FILE UPLOAD ROUTES
# ============================================================================

@app.route('/api/upload', methods=['POST'])
@token_required
def upload_file(current_user):
    try:
        if 'file' not in request.files:
            return jsonify({'message': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'message': 'No file selected'}), 400
        
        file_type = request.form.get('type', 'unknown')
        
        # Save file (optional)
        # filename = secure_filename(file.filename)
        # file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Generate response based on file type
        if file_type == 'image':
            analysis = "📷 Image received! For accurate medical diagnosis from images, please consult a healthcare professional. I can provide general health information."
        elif file_type == 'pdf':
            analysis = "📄 PDF received! For detailed interpretation of medical reports, please consult your doctor. I can answer general questions about medical terminology."
        else:
            analysis = "📎 File uploaded successfully! For medical document analysis, please consult a healthcare professional."
        
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': file.filename,
            'analysis': analysis
        }), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# ============================================================================
# HEALTH NEWS ROUTES
# ============================================================================

@app.route('/api/health-news', methods=['GET'])
@token_required
def get_health_news(current_user):
    try:
        news = [
            {
                'title': 'WHO Updates COVID-19 Guidelines for 2025',
                'url': 'https://www.who.int',
                'source': 'WHO',
                'publishedAt': datetime.datetime.now().isoformat()
            },
            {
                'title': 'Mediterranean Diet Reduces Heart Disease Risk by 30%',
                'url': '#',
                'source': 'Health Journal',
                'publishedAt': datetime.datetime.now().isoformat()
            },
            {
                'title': 'New Breakthrough in Cancer Immunotherapy',
                'url': '#',
                'source': 'Medical News',
                'publishedAt': datetime.datetime.now().isoformat()
            },
            {
                'title': 'Mental Health: Addressing Workplace Stress',
                'url': '#',
                'source': 'Psychology Today',
                'publishedAt': datetime.datetime.now().isoformat()
            },
            {
                'title': 'India Launches National Diabetes Prevention Program',
                'url': '#',
                'source': 'Ministry of Health',
                'publishedAt': datetime.datetime.now().isoformat()
            }
        ]
        
        return jsonify({'news': news}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# ============================================================================
# LOCATION-BASED SERVICES
# ============================================================================

@app.route('/api/nearby-hospitals', methods=['POST'])
@token_required
def nearby_hospitals(current_user):
    try:
        hospitals = [
            {
                'name': 'Apollo Hospital',
                'distance': '2.3 km',
                'phone': '+91-80-2692-2222',
                'address': 'Bannerghatta Road, Bangalore',
                'specialties': ['Emergency', 'Cardiac', 'Neurology'],
                'rating': 4.5
            },
            {
                'name': 'Fortis Hospital',
                'distance': '3.1 km',
                'phone': '+91-80-6621-4444',
                'address': 'Cunningham Road, Bangalore',
                'specialties': ['Cardiac Care', 'Orthopedics', 'ICU'],
                'rating': 4.3
            },
            {
                'name': 'Manipal Hospital',
                'distance': '4.5 km',
                'phone': '+91-80-2502-4444',
                'address': 'HAL Airport Road, Bangalore',
                'specialties': ['Emergency', 'Trauma Care', 'Surgery'],
                'rating': 4.4
            }
        ]
        
        return jsonify({'hospitals': hospitals}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/nearby-doctors', methods=['POST'])
@token_required
def nearby_doctors(current_user):
    try:
        doctors = [
            {
                'name': 'Dr. Rajesh Kumar',
                'specialty': 'General Physician',
                'clinic': 'Apollo Clinic',
                'distance': '1.8 km',
                'phone': '+91-98765-43210',
                'availability': '9 AM - 6 PM',
                'rating': 4.6
            },
            {
                'name': 'Dr. Priya Sharma',
                'specialty': 'Cardiologist',
                'clinic': 'Heart Care Center',
                'distance': '2.5 km',
                'phone': '+91-98765-43211',
                'availability': '10 AM - 5 PM',
                'rating': 4.7
            },
            {
                'name': 'Dr. Amit Patel',
                'specialty': 'Pediatrician',
                'clinic': 'Kids Health Clinic',
                'distance': '3.2 km',
                'phone': '+91-98765-43212',
                'availability': '9 AM - 7 PM',
                'rating': 4.5
            }
        ]
        
        return jsonify({'doctors': doctors}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# ============================================================================
# EMERGENCY HELPLINES
# ============================================================================

@app.route('/api/emergency-helplines', methods=['GET'])
def emergency_helplines():
    try:
        helplines = {
            'india': [
                {'name': 'National Emergency', 'number': '112'},
                {'name': 'Ambulance', 'number': '108'},
                {'name': 'Ambulance (Alternative)', 'number': '102'},
                {'name': 'Police', 'number': '100'},
                {'name': 'Fire', 'number': '101'},
                {'name': 'Women Helpline', 'number': '1091'},
                {'name': 'Child Helpline', 'number': '1098'},
                {'name': 'Mental Health (KIRAN)', 'number': '1800-599-0019'},
                {'name': 'Senior Citizens', 'number': '1291'},
                {'name': 'Poison Control', 'number': '1066'}
            ]
        }
        
        return jsonify(helplines), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'message': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'message': 'Internal server error'}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("🏥 HealthCare AI Backend Server Starting...")
    print("📍 Server running on: http://localhost:5000")
    print("📚 API Documentation: http://localhost:5000/")
    print("\n✅ Available Endpoints:")
    print("   - POST /api/auth/login")
    print("   - POST /api/auth/register")
    print("   - POST /api/chat")
    print("   - POST /api/upload")
    print("   - GET  /api/health-news")
    print("   - GET  /api/emergency-helplines")
    print("   - POST /api/nearby-hospitals")
    print("   - POST /api/nearby-doctors")
    print("\n🚀 Press CTRL+C to stop the server\n")
    
    # app.run(debug=True, host='0.0.0.0', port=5000)
    # serve(app, host='0.0.0.0', port=5000)
    try:
        # Try to use Waitress (production server)
        serve(app, host='0.0.0.0', port=5000, threads=4)
    except ImportError:
        # Fallback to Flask dev server
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)