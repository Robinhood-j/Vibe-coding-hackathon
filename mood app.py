# ===================================================================
# VIBE CHECK MOOD JOURNAL - FLASK BACKEND API (FIXED VERSION)
# SDG 3: Good Health & Well-being for Millennials & Gen Z
# ===================================================================

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime, date, timedelta
import requests
import json
import os
from functools import wraps
import statistics

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'  # Change in production

# Fixed CORS configuration for credentials
CORS(app, supports_credentials=True, origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5500"])

# ===================================================================
# DATABASE CONNECTION (UPDATE THESE VALUES!)
# ===================================================================

def get_db_connection():
    """Create database connection - UPDATE THESE VALUES!"""
    try:
        return mysql.connector.connect(
            host='localhost',
            user='root',              # ← Change to your MySQL username
            password='',              # ← Change to your MySQL password (empty if no password)
            database='mood_journal_db', # ← Make sure this database exists
            autocommit=True
        )
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# ===================================================================
# DATABASE SETUP - CREATE TABLES IF THEY DON'T EXIST
# ===================================================================

def init_database():
    """Initialize database tables"""
    conn = get_db_connection()
    if not conn:
        print("Cannot connect to database!")
        return False
    
    cursor = conn.cursor()
    
    try:
        # Create database if it doesn't exist
        cursor.execute("CREATE DATABASE IF NOT EXISTS mood_journal_db")
        cursor.execute("USE mood_journal_db")
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                first_name VARCHAR(50),
                age_range VARCHAR(20),
                wellness_goals JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create mood_entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mood_entries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                mood_value INT NOT NULL,
                mood_label VARCHAR(50),
                mood_emoji VARCHAR(10),
                sleep_hours DECIMAL(3,1),
                exercise_minutes INT,
                social_interaction BOOLEAN,
                work_stress_level INT,
                quick_note TEXT,
                sentiment_score DECIMAL(3,2),
                entry_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        print("Database tables created successfully!")
        return True
        
    except mysql.connector.Error as err:
        print(f"Database setup error: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

# ===================================================================
# HUGGING FACE AI INTEGRATION
# ===================================================================

HUGGING_FACE_API_KEY = "your_hugging_face_api_key"  # Optional - leave as is for now
HF_SENTIMENT_URL = "https://api-inference.huggingface.co/models/cardiffnlp/twitter-roberta-base-sentiment-latest"

def analyze_sentiment(text):
    """Analyze sentiment using Hugging Face API"""
    # For now, return a simple mock sentiment since API key is placeholder
    if not text:
        return {'score': 0.0, 'label': 'neutral', 'confidence': 0.5}
    
    # Simple keyword-based sentiment (replace with real API when you have key)
    positive_words = ['good', 'great', 'happy', 'amazing', 'wonderful', 'excited', 'love']
    negative_words = ['bad', 'sad', 'terrible', 'awful', 'hate', 'stressed', 'tired']
    
    text_lower = text.lower()
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    if pos_count > neg_count:
        return {'score': 0.7, 'label': 'positive', 'confidence': 0.8}
    elif neg_count > pos_count:
        return {'score': -0.7, 'label': 'negative', 'confidence': 0.8}
    else:
        return {'score': 0.0, 'label': 'neutral', 'confidence': 0.6}

# ===================================================================
# AUTHENTICATION HELPERS
# ===================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ===================================================================
# API ENDPOINTS
# ===================================================================

@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    # Validate input
    if not data or not all(k in data for k in ['username', 'email', 'password']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
        
    cursor = conn.cursor()
    
    try:
        password_hash = generate_password_hash(data['password'])
        query = """
        INSERT INTO users (username, email, password_hash, first_name, age_range, wellness_goals)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data['username'],
            data['email'], 
            password_hash,
            data.get('first_name', ''),
            data.get('age_range', '25-34'),
            json.dumps(data.get('wellness_goals', []))
        ))
        
        user_id = cursor.lastrowid
        session['user_id'] = user_id
        session['first_name'] = data.get('first_name', data['username'])
        
        return jsonify({
            'success': True, 
            'user_id': user_id, 
            'first_name': data.get('first_name', data['username']),
            'message': 'Welcome to Vibe Check!'
        })
        
    except mysql.connector.IntegrityError as e:
        if 'username' in str(e):
            return jsonify({'error': 'Username already exists'}), 400
        elif 'email' in str(e):
            return jsonify({'error': 'Email already exists'}), 400
        else:
            return jsonify({'error': 'User already exists'}), 400
            
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()
    
    if not data or not all(k in data for k in ['email', 'password']):
        return jsonify({'error': 'Email and password required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
        
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (data['email'],))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password_hash'], data['password']):
            session['user_id'] = user['id']
            session['first_name'] = user['first_name'] or user['username']
            
            return jsonify({
                'success': True,
                'user_id': user['id'],
                'first_name': user['first_name'] or user['username'],
                'message': 'Login successful!'
            })
        else:
            return jsonify({'error': 'Invalid email or password'}), 401
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/create-demo', methods=['POST'])
def create_demo_user():
    """Create demo user for testing"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
        
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if demo user already exists
        cursor.execute("SELECT * FROM users WHERE username = %s", ("demo_user",))
        user = cursor.fetchone()

        if not user:
            password_hash = generate_password_hash("demo123")
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, first_name, age_range, wellness_goals)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                "demo_user",
                "demo@test.com",
                password_hash,
                "Demo",
                "18-24",
                json.dumps(["Stress management", "Better sleep"])
            ))
            user_id = cursor.lastrowid
        else:
            user_id = user["id"]

        return jsonify({
            "success": True,
            "demo_user": {
                "username": "demo_user",
                "email": "demo@test.com",
                "password": "demo123"
            },
            "message": "Demo user is ready!"
        })

    except Exception as e:
        print(f"Demo creation error: {e}")
        return jsonify({"error": "Failed to create demo user"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/mood-entry', methods=['POST'])
@login_required
def create_mood_entry():
    """Create a new mood entry"""
    data = request.get_json()
    user_id = session['user_id']
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
        
    cursor = conn.cursor()
    
    try:
        # Analyze sentiment if there's a note
        sentiment_data = {'score': 0.0}
        if data.get('quick_note'):
            sentiment_data = analyze_sentiment(data['quick_note'])
        
        # Get activities data
        activities = data.get('activities', {})
        
        query = """
        INSERT INTO mood_entries 
        (user_id, mood_value, mood_label, mood_emoji, sleep_hours, exercise_minutes, 
         social_interaction, work_stress_level, quick_note, sentiment_score, entry_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            user_id,
            data.get('mood_value', 5),
            data.get('mood_label', 'Okay'),
            data.get('emoji', '😐'),
            activities.get('sleep_hours'),
            activities.get('exercise_minutes', 0),
            activities.get('social_interaction', False),
            activities.get('work_stress_level', 5),
            data.get('quick_note', ''),
            sentiment_data['score'],
            date.today()
        ))
        
        return jsonify({
            'success': True,
            'message': 'Mood logged successfully!',
            'ai_analysis': {
                'message': f"Thanks for sharing! {get_sentiment_interpretation(sentiment_data['score'])}"
            }
        })
        
    except Exception as e:
        print(f"Mood entry error: {e}")
        return jsonify({'error': 'Failed to save mood entry'}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    """Get dashboard data for user"""
    user_id = session['user_id']
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
        
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get recent mood entries
        cursor.execute("""
            SELECT * FROM mood_entries 
            WHERE user_id = %s 
            ORDER BY entry_date DESC 
            LIMIT 7
        """, (user_id,))
        
        mood_entries = cursor.fetchall()
        
        if not mood_entries:
            return jsonify({
                'mood_data': [],
                'stats': {'current_streak': 0, 'average_mood': 0.0, 'trend': '--'},
                'insights': []
            })
        
        # Calculate stats
        mood_values = [entry['mood_value'] for entry in mood_entries]
        avg_mood = round(sum(mood_values) / len(mood_values), 1)
        
        # Simple trend calculation
        if len(mood_values) >= 3:
            recent_avg = sum(mood_values[:3]) / 3
            older_avg = sum(mood_values[3:]) / len(mood_values[3:]) if len(mood_values) > 3 else recent_avg
            trend = "↗️" if recent_avg > older_avg else "↘️" if recent_avg < older_avg else "→"
        else:
            trend = "→"
        
        # Format mood data for chart
        mood_data = []
        for entry in reversed(mood_entries):
            mood_data.append({
                'day': entry['entry_date'].strftime('%a'),
                'mood_value': entry['mood_value'],
                'mood_label': entry['mood_label']
            })
        
        # Generate simple insights
        insights = []
        if avg_mood >= 7:
            insights.append({
                'title': 'Great Vibes!',
                'description': f'Your average mood this week is {avg_mood}/10. Keep up the positive energy!',
                'confidence_level': 'high'
            })
        elif avg_mood < 5:
            insights.append({
                'title': 'Gentle Reminder',
                'description': 'Your mood has been lower lately. Consider self-care activities you enjoy.',
                'confidence_level': 'medium'
            })
        
        return jsonify({
            'mood_data': mood_data,
            'stats': {
                'current_streak': calculate_streak(user_id, cursor),
                'average_mood': avg_mood,
                'trend': trend
            },
            'insights': insights
        })
        
    except Exception as e:
        print(f"Dashboard error: {e}")
        return jsonify({'error': 'Failed to load dashboard'}), 500
        
    finally:
        cursor.close()
        conn.close()

# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

def calculate_streak(user_id, cursor):
    """Calculate current streak of consecutive days"""
    cursor.execute("""
        SELECT entry_date FROM mood_entries 
        WHERE user_id = %s 
        ORDER BY entry_date DESC 
        LIMIT 30
    """, (user_id,))
    
    dates = [row['entry_date'] for row in cursor.fetchall()]
    if not dates: 
        return 0
    
    streak = 1
    current_date = dates[0]
    
    for i in range(1, len(dates)):
        expected_date = current_date - timedelta(days=i)
        if dates[i] == expected_date:
            streak += 1
        else:
            break
    
    return streak

def get_sentiment_interpretation(score):
    """Get human-readable sentiment interpretation"""
    if score >= 0.5: 
        return "Your writing shows positive energy and optimism!"
    elif score >= 0.1: 
        return "Generally positive vibes with some mixed feelings"
    elif score >= -0.1: 
        return "Neutral tone - processing thoughts and feelings"
    elif score >= -0.5: 
        return "Some challenging emotions coming through"
    else:
        return "Sounds like a tough day. Remember, this feeling will pass"

# ===================================================================
# HEALTH CHECK ENDPOINT
# ===================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Check if server and database are working"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    else:
        return jsonify({'status': 'unhealthy', 'database': 'disconnected'}), 500

# ===================================================================
# RUN APP
# ===================================================================

if __name__ == '__main__':
    print("Starting Vibe Check Flask Server...")
    
    # Initialize database tables
    if init_database():
        print("Database initialized successfully!")
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("Failed to initialize database. Please check your MySQL connection settings.")