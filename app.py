from flask import Flask, request, jsonify, session
from flask_cors import CORS
import mysql.connector
from datetime import datetime, date, timedelta
import requests
import json
import os
from functools import wraps
import statistics
import bcrypt
from dotenv import load_dotenv

# Load settings from .env file
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
CORS(app, supports_credentials=True, origins=['http://127.0.0.1:5500', 'http://localhost:5500', 'file://*'])

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'mood_journal_db'),
    'autocommit': True
}

# AI API configuration
HUGGING_FACE_API_KEY = os.getenv('HUGGING_FACE_API_KEY')
AI_URL = "https://api-inference.huggingface.co/models/cardiffnlp/twitter-roberta-base-sentiment-latest"

# Connect to database
def get_db():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return None

# Check if user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Please log in first'}), 401
        return f(*args, **kwargs)
    return decorated_function

# AI sentiment analysis
def analyze_sentiment(text):
    if not HUGGING_FACE_API_KEY or HUGGING_FACE_API_KEY == 'hf_your_token_here':
        return {
            'score': 0.0,
            'label': 'neutral',
            'message': 'Add Hugging Face API key for AI analysis'
        }
    
    headers = {"Authorization": f"Bearer {HUGGING_FACE_API_KEY}"}
    
    try:
        response = requests.post(AI_URL, headers=headers, json={"inputs": text}, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and result:
                best = max(result[0], key=lambda x: x['score'])
                
                # Convert to readable format
                sentiment_map = {
                    'LABEL_0': {'score': -0.7, 'label': 'negative'},
                    'LABEL_1': {'score': 0.0, 'label': 'neutral'},
                    'LABEL_2': {'score': 0.7, 'label': 'positive'}
                }
                
                mapped = sentiment_map.get(best['label'], {'score': 0.0, 'label': 'neutral'})
                
                # Create friendly message
                if mapped['score'] >= 0.5:
                    message = "Your writing shows positive vibes!"
                elif mapped['score'] >= -0.1:
                    message = "Neutral feelings - totally normal"
                else:
                    message = "Some tough emotions there - you're not alone"
                
                return {
                    'score': mapped['score'],
                    'label': mapped['label'],
                    'confidence': best['score'],
                    'message': message
                }
    except Exception as e:
        print(f"AI error: {e}")
    
    return {'score': 0.0, 'label': 'neutral', 'message': 'AI temporarily unavailable'}

# Generate insights from user data
def generate_insights(user_id, cursor):
    try:
        # Get last 14 days of data
        cursor.execute("""
        SELECT m.mood_value, a.exercise_minutes, a.social_interaction, a.sleep_hours,
               DAYNAME(m.entry_date) as day_name
        FROM mood_entries m
        LEFT JOIN activities a ON m.user_id = a.user_id AND m.entry_date = a.entry_date
        WHERE m.user_id = %s AND m.entry_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
        """, (user_id,))
        
        data = cursor.fetchall()
        insights = []
        
        if len(data) >= 3:
            # Exercise insight
            exercise_days = [d for d in data if d[1] and d[1] > 0]
            no_exercise_days = [d for d in data if not d[1] or d[1] == 0]
            
            if len(exercise_days) >= 2 and len(no_exercise_days) >= 1:
                exercise_avg = statistics.mean([d[0] for d in exercise_days])
                no_exercise_avg = statistics.mean([d[0] for d in no_exercise_days])
                
                if exercise_avg > no_exercise_avg + 0.5:
                    insights.append({
                        'title': 'Exercise Mood Boost',
                        'description': f'Your mood is {exercise_avg - no_exercise_avg:.1f} points higher on workout days!',
                        'confidence_level': 'high'
                    })
            
            # Sleep insight
            sleep_data = [d for d in data if d[3]]  # Has sleep data
            if len(sleep_data) >= 3:
                good_sleep = [d for d in sleep_data if d[3] >= 7.5]
                poor_sleep = [d for d in sleep_data if d[3] < 6.5]
                
                if len(good_sleep) >= 1 and len(poor_sleep) >= 1:
                    good_avg = statistics.mean([d[0] for d in good_sleep])
                    poor_avg = statistics.mean([d[0] for d in poor_sleep])
                    
                    if good_avg > poor_avg + 0.5:
                        insights.append({
                            'title': 'Sleep Quality Impact',
                            'description': f'Good sleep improves your mood by {good_avg - poor_avg:.1f} points!',
                            'confidence_level': 'medium'
                        })
            
            # Social insight
            social_days = [d for d in data if d[2]]  # Had social interaction
            solo_days = [d for d in data if not d[2]]
            
            if len(social_days) >= 2 and len(solo_days) >= 1:
                social_avg = statistics.mean([d[0] for d in social_days])
                solo_avg = statistics.mean([d[0] for d in solo_days])
                
                if social_avg > solo_avg + 0.3:
                    insights.append({
                        'title': 'Social Connection Power',
                        'description': 'Social activities consistently boost your energy!',
                        'confidence_level': 'high'
                    })
        
        return insights[:3]  # Return top 3 insights
        
    except Exception as e:
        print(f"Insight error: {e}")
        return []

# API ENDPOINTS

@app.route('/api/health', methods=['GET'])
def health_check():
    """Test if app is working"""
    db = get_db()
    db_status = "connected" if db else "failed"
    if db:
        db.close()
    
    ai_status = "ready" if HUGGING_FACE_API_KEY else "no key"
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'ai': ai_status,
        'message': 'Mood Journal API is running!'
    })

@app.route('/api/register', methods=['POST'])
def register():
    """Register new user"""
    data = request.get_json()
    
    # Validate required fields
    required = ['username', 'email', 'password', 'first_name']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    if len(data['password']) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    db = get_db()
    if not db:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = db.cursor()
    
    try:
        # Hash password
        password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Insert user
        cursor.execute("""
        INSERT INTO users (username, email, password_hash, first_name, age_range)
        VALUES (%s, %s, %s, %s, %s)
        """, (data['username'], data['email'], password_hash, data['first_name'], data.get('age_range', '25-34')))
        
        user_id = cursor.lastrowid
        session['user_id'] = user_id
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'message': f'Welcome {data["first_name"]}!'
        })
        
    except mysql.connector.IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 400
    except Exception as e:
        return jsonify({'error': 'Registration failed'}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/api/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()
    
    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password required'}), 400
    
    db = get_db()
    if not db:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = db.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (data['email'],))
        user = cursor.fetchone()
        
        if user and bcrypt.checkpw(data['password'].encode('utf-8'), user['password_hash'].encode('utf-8')):
            session['user_id'] = user['id']
            return jsonify({
                'success': True,
                'user_id': user['id'],
                'first_name': user['first_name']
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        return jsonify({'error': 'Login failed'}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/api/mood-entry', methods=['POST'])
@login_required
def save_mood():
    """Save mood entry with AI analysis"""
    data = request.get_json()
    user_id = session['user_id']
    
    db = get_db()
    if not db:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = db.cursor()
    
    try:
        today = date.today()
        now = datetime.now().time()
        
        # Save mood entry
        cursor.execute("""
        INSERT INTO mood_entries (user_id, mood_value, mood_label, entry_date, entry_time, quick_note)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
        mood_value = VALUES(mood_value), mood_label = VALUES(mood_label), quick_note = VALUES(quick_note)
        """, (user_id, data['mood_value'], data['mood_label'], today, now, data.get('quick_note', '')))
        
        # Save activities if provided
        if 'activities' in data:
            act = data['activities']
            cursor.execute("""
            INSERT INTO activities (user_id, entry_date, sleep_hours, exercise_minutes, social_interaction, caffeine_intake, work_stress_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            sleep_hours = VALUES(sleep_hours), exercise_minutes = VALUES(exercise_minutes), 
            social_interaction = VALUES(social_interaction), caffeine_intake = VALUES(caffeine_intake), 
            work_stress_level = VALUES(work_stress_level)
            """, (user_id, today, act.get('sleep_hours'), act.get('exercise_minutes', 0), 
                  act.get('social_interaction', False), act.get('caffeine_intake', 0), act.get('work_stress_level', 5)))
        
        # AI analysis
        ai_result = None
        if data.get('quick_note'):
            ai_result = analyze_sentiment(data['quick_note'])
        
        # Generate insights
        insights = generate_insights(user_id, cursor)
        
        return jsonify({
            'success': True,
            'message': 'Mood saved successfully!',
            'ai_analysis': ai_result,
            'insights': insights[:2]
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to save mood'}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    """Get dashboard with mood trends and insights"""
    user_id = session['user_id']
    
    db = get_db()
    if not db:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = db.cursor(dictionary=True)
    
    try:
        # Get last 7 days
        cursor.execute("""
        SELECT m.entry_date, m.mood_value, m.mood_label, m.quick_note,
               a.sleep_hours, a.exercise_minutes, a.social_interaction, a.work_stress_level
        FROM mood_entries m
        LEFT JOIN activities a ON m.user_id = a.user_id AND m.entry_date = a.entry_date
        WHERE m.user_id = %s AND m.entry_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        ORDER BY m.entry_date DESC
        """, (user_id,))
        
        mood_data = cursor.fetchall()
        
        # Convert dates to strings
        for entry in mood_data:
            entry['entry_date'] = entry['entry_date'].strftime('%Y-%m-%d')
            entry['day'] = datetime.strptime(entry['entry_date'], '%Y-%m-%d').strftime('%a')
        
        # Calculate stats
        if mood_data:
            moods = [entry['mood_value'] for entry in mood_data]
            avg_mood = statistics.mean(moods)
            streak = calculate_streak(user_id, cursor)
            trend = "improving" if len(mood_data) > 2 and moods[0] > moods[-1] else "stable"
        else:
            avg_mood = 0
            streak = 0
            trend = "starting"
        
        # Get insights
        insights = generate_insights(user_id, cursor)
        
        return jsonify({
            'mood_data': mood_data,
            'insights': insights,
            'stats': {
                'current_streak': streak,
                'average_mood': round(avg_mood, 1),
                'trend': trend,
                'total_entries': len(mood_data)
            }
        })
        
    except Exception as e:
        return jsonify({'error': 'Dashboard failed'}), 500
    finally:
        cursor.close()
        db.close()

def calculate_streak(user_id, cursor):
    """Calculate consecutive check-in days"""
    try:
        cursor.execute("""
        SELECT entry_date FROM mood_entries 
        WHERE user_id = %s 
        ORDER BY entry_date DESC LIMIT 30
        """, (user_id,))
        
        dates = [row[0] for row in cursor.fetchall()]
        if not dates:
            return 0
        
        streak = 1
        current = dates[0]
        
        for i in range(1, len(dates)):
            expected = current - timedelta(days=i)
            if dates[i] == expected:
                streak += 1
            else:
                break
        
        return streak
    except:
        return 0

# Test endpoint to create sample data
@app.route('/api/create-demo', methods=['POST'])
def create_demo():
    """Create demo user with sample data"""
    db = get_db()
    if not db:
        return jsonify({'error': 'Database error'}), 500
    
    cursor = db.cursor()
    
    try:
        # Create demo user
        password_hash = bcrypt.hashpw('demo123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute("""
        INSERT IGNORE INTO users (username, email, password_hash, first_name, age_range)
        VALUES (%s, %s, %s, %s, %s)
        """, ('demo_user', 'demo@test.com', password_hash, 'Demo', '25-34'))
        
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = 'demo_user'")
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Failed to create demo user'}), 500
        
        user_id = result[0]
        
        # Create sample mood entries (last 7 days)
        sample_data = [
            (0, 8, 'Great', 8.0, 45, True, 1, 3, 'Amazing workout this morning!'),
            (1, 7, 'Good', 7.5, 0, False, 2, 4, 'Productive work day'),
            (2, 4, 'Meh', 6.0, 0, False, 0, 2, 'Sunday blues'),
            (3, 9, 'Amazing', 8.5, 60, False, 1, 2, 'Best day ever!'),
            (4, 6, 'Okay', 7.0, 0, False, 3, 7, 'Work stress'),
            (5, 8, 'Great', 7.5, 30, True, 1, 3, 'Coffee with friends'),
            (6, 7, 'Good', 6.5, 0, False, 4, 8, 'Long but good day')
        ]
        
        for days_ago, mood_val, mood_label, sleep_hrs, exercise_min, social, caffeine, stress, note in sample_data:
            entry_date = date.today() - timedelta(days=days_ago)
            
            cursor.execute("""
            INSERT IGNORE INTO mood_entries (user_id, mood_value, mood_label, entry_date, entry_time, quick_note)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, mood_val, mood_label, entry_date, '12:00:00', note))
            
            cursor.execute("""
            INSERT IGNORE INTO activities (user_id, entry_date, sleep_hours, exercise_minutes, social_interaction, caffeine_intake, work_stress_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, entry_date, sleep_hrs, exercise_min, social, caffeine, stress))
        
        return jsonify({
            'success': True,
            'demo_user': {
                'username': 'demo_user',
                'password': 'demo123',
                'email': 'demo@test.com'
            },
            'message': 'Demo user created with 7 days of sample data!'
        })
        
    except Exception as e:
        return jsonify({'error': f'Demo creation failed: {e}'}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    """Log out current user"""
    session.pop('user_id', None)
    return jsonify({'success': True, 'message': 'Logged out successfully!'})

if __name__ == '__main__':
    print("Starting Mood Journal App...")
    print("SDG 3: Good Health & Well-being")
    print("Target: Mental wellness for young adults")
    print("=" * 50)
    
    # Test database
    db = get_db()
    if db:
        db.close()
        print("SUCCESS: Database connected!")
    else:
        print("ERROR: Database connection failed!")
        print("Check MySQL is running and .env settings")
    
    # Check AI key
    if HUGGING_FACE_API_KEY and HUGGING_FACE_API_KEY != 'hf_your_token_here':
        print("SUCCESS: AI key loaded!")
    else:
        print("WARNING: No AI key - get one at huggingface.co/settings/tokens")
    
    print("=" * 50)
    print("Server starting at http://localhost:5000")
    print("Test health check: http://localhost:5000/api/health")
    print("Mood Journal ready!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
    