# main_development.py - Development Environment Flask Application
import os
import sys
import pyodbc
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, redirect
from flask_cors import CORS

app = Flask(__name__)

# DEVELOPMENT Configuration
app.config['SECRET_KEY'] = 'gvt-development-secret-key-2024'
app.config['DEBUG'] = True
app.config['ENVIRONMENT'] = 'DEVELOPMENT'

# Development Database Connection
def get_db_connection():
    """Get Azure SQL DEVELOPMENT database connection"""
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=partnership-sql-server.database.windows.net;"
        "DATABASE=golden-valley-transit-dev;"  # DEV database
        "UID=info;"
        "PWD=SaQu12022!;"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )
    return pyodbc.connect(connection_string)

def execute_query(query, params=None):
    """Execute SQL query on DEVELOPMENT database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        columns = [column[0] for column in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        return results
    except Exception as e:
        print(f"Database error: {e}")
        return []

# Enable CORS
CORS(app, origins='*')


# Customer Login System
@app.route('/customer-login')
def customer_login():
    """Customer login page"""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Golden Valley Transit - Customer Login</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                font-family: 'Inter', sans-serif;
            }
            .glass-card {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(20px);
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            .form-input {
                border: 2px solid #e5e7eb;
                border-radius: 12px;
                padding: 0.75rem 1rem;
                width: 100%;
                transition: all 0.3s ease;
            }
            .form-input:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
            }
            .premium-button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                font-weight: 600;
                border-radius: 12px;
                padding: 0.75rem 1.5rem;
                border: none;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .premium-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
            }
        </style>
    </head>
    <body class="min-h-screen flex items-center justify-center p-4">
        <div class="glass-card p-8 max-w-md w-full">
            <div class="text-center mb-8">
                <div class="w-16 h-16 bg-white bg-opacity-20 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span class="text-3xl">🏥</span>
                </div>
                <h1 class="text-3xl font-bold text-gray-800 mb-2">Golden Valley Transit</h1>
                <p class="text-gray-600">Login to Your Patient Portal</p>
            </div>
            
            <form class="space-y-6" onsubmit="customerLogin(event)">
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">Email Address</label>
                    <input type="email" class="form-input" placeholder="your.email@example.com" id="loginEmail" required>
                </div>
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">Phone Number</label>
                    <input type="tel" class="form-input" placeholder="(661) 555-0100" id="loginPhone" required>
                </div>
                <button type="submit" class="premium-button w-full py-3">
                    Access My Portal
                </button>
            </form>
            
            <div class="text-center mt-6">
                <p class="text-gray-600">New customer? <a href="/new-customer" class="text-blue-600 font-semibold hover:text-blue-800">Register here</a></p>
                <p class="text-gray-600 mt-2">Demo version? <a href="/patient-portal-demo" class="text-purple-600 font-semibold hover:text-purple-800">View Elena Garcia's demo</a></p>
            </div>
        </div>
        
        <script>
            function customerLogin(event) {
                event.preventDefault();
                
                const email = document.getElementById('loginEmail').value;
                const phone = document.getElementById('loginPhone').value;
                
                if (!email || !phone) {
                    alert('Please enter your email and phone number');
                    return;
                }
                
                // Redirect to personalized portal
                window.location.href = `/patient-portal?email=${encodeURIComponent(email)}&phone=${encodeURIComponent(phone)}`;
            }
        </script>
    </body>
    </html>
    """)

@app.route('/')
def index():
    """Development environment landing page"""
    return {
        "message": "Golden Valley Transit DEVELOPMENT Environment",
        "status": "healthy",
        "version": "2.1.0-dev",
        "environment": "DEVELOPMENT",
        "database": "golden-valley-transit-dev",
        "demo_url": "http://192.168.5.39:5001/demo",
        "warning": "This is a development environment - safe for testing"
    }

@app.route('/demo')
def demo_landing():
    """Development demo landing page"""
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Golden Valley Transit - Development Demo</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); }
            .demo-card { 
                background: rgba(255, 255, 255, 0.95); 
                backdrop-filter: blur(20px);
                transition: all 0.3s ease;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .demo-card:hover { 
                transform: translateY(-8px); 
                box-shadow: 0 25px 50px rgba(0,0,0,0.2); 
            }
            .dev-badge {
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                font-weight: bold;
                font-size: 0.875rem;
            }
        </style>
    </head>
    <body class="min-h-screen p-8">
        <div class="max-w-7xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-12">
                <div class="dev-badge inline-block mb-4">🛠️ DEVELOPMENT ENVIRONMENT</div>
                <h1 class="text-5xl font-bold text-white mb-4">Golden Valley Transit</h1>
                <p class="text-2xl text-blue-100 mb-2">Development Demo Platform</p>
                <p class="text-lg text-blue-200">Safe Testing Environment • Dev Database • Integrated Web App</p>
                <div class="mt-4 space-x-4">
                    <span class="inline-block bg-green-500 text-white px-4 py-2 rounded-full text-sm font-semibold">
                        🟢 DEV DATABASE
                    </span>
                    <span class="inline-block bg-blue-500 text-white px-4 py-2 rounded-full text-sm font-semibold">
                        🔧 SAFE TESTING
                    </span>
                </div>
            </div>
            
            <!-- Main Demo Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
                <div class="demo-card p-8">
                    <div class="text-6xl mb-6 text-center">✨</div>
                    <h3 class="text-2xl font-bold mb-3 text-gray-800">New Customer</h3>
                    <p class="text-gray-600 mb-6">Complete registration & first booking</p>
                    <div class="text-sm text-gray-500 mb-4">
                        🛠️ Registration workflow<br>
                        🔧 First trip booking<br>
                        📧 Welcome email system
                    </div>
                    <a href="/new-customer" class="block w-full bg-green-600 text-white text-center px-6 py-3 rounded-xl hover:bg-green-700 font-semibold transition-colors">
                        Start Registration
                    </a>
                </div>
                
                <div class="demo-card p-8">
                    <div class="text-6xl mb-6 text-center">👤</div>
                    <h3 class="text-2xl font-bold mb-3 text-gray-800">Patient Portal</h3>
                    <p class="text-gray-600 mb-6">Elena Garcia's experience (dev data)</p>
                    <div class="text-sm text-gray-500 mb-4">
                        🛠️ Development testing<br>
                        🔧 Safe to modify<br>
                        📊 Dev database
                    </div>
                    <a href="/patient-portal" class="block w-full bg-blue-600 text-white text-center px-6 py-3 rounded-xl hover:bg-blue-700 font-semibold transition-colors">
                        Test Patient Portal
                    </a>
                </div>
                
                <div class="demo-card p-8">
                    <div class="text-6xl mb-6 text-center">🚛</div>
                    <h3 class="text-2xl font-bold mb-3 text-gray-800">Driver Dashboard</h3>
                    <p class="text-gray-600 mb-6">Carlos Martinez's interface (dev)</p>
                    <div class="text-sm text-gray-500 mb-4">
                        🛠️ Driver workflow testing<br>
                        🔧 Feature development<br>
                        📊 Dev environment
                    </div>
                    <a href="/driver-dashboard" class="block w-full bg-green-600 text-white text-center px-6 py-3 rounded-xl hover:bg-green-700 font-semibold transition-colors">
                        Test Driver Dashboard
                    </a>
                </div>
                
                <div class="demo-card p-8">
                    <div class="text-6xl mb-6 text-center">🛡️</div>
                    <h3 class="text-2xl font-bold mb-3 text-gray-800">Insurance Admin</h3>
                    <p class="text-gray-600 mb-6">Claims processing (dev testing)</p>
                    <div class="text-sm text-gray-500 mb-4">
                        🛠️ Claims workflow<br>
                        🔧 Billing development<br>
                        📊 Test data safe
                    </div>
                    <a href="/insurance-admin" class="block w-full bg-purple-600 text-white text-center px-6 py-3 rounded-xl hover:bg-purple-700 font-semibold transition-colors">
                        Test Insurance Portal
                    </a>
                </div>
                
                <div class="demo-card p-8">
                    <div class="text-6xl mb-6 text-center">📡</div>
                    <h3 class="text-2xl font-bold mb-3 text-gray-800">Dispatch Center</h3>
                    <p class="text-gray-600 mb-6">Operations center (dev)</p>
                    <div class="text-sm text-gray-500 mb-4">
                        🛠️ Fleet management testing<br>
                        🔧 Dispatch development<br>
                        📊 Safe operations
                    </div>
                    <a href="/dispatch-center" class="block w-full bg-red-600 text-white text-center px-6 py-3 rounded-xl hover:bg-red-700 font-semibold transition-colors">
                        Test Dispatch Center
                    </a>
                </div>
                
                <div class="demo-card p-8">
                    <div class="text-6xl mb-6 text-center">📊</div>
                    <h3 class="text-2xl font-bold mb-3 text-gray-800">Dev API Data</h3>
                    <p class="text-gray-600 mb-6">Development database queries</p>
                    <div class="text-sm text-gray-500 mb-4">
                        🛠️ API testing<br>
                        🔧 Database development<br>
                        📊 Dev data queries
                    </div>
                    <a href="/api/demo-data" class="block w-full bg-yellow-600 text-white text-center px-6 py-3 rounded-xl hover:bg-yellow-700 font-semibold transition-colors">
                        Test API Data
                    </a>
                </div>
                
                <div class="demo-card p-8">
                    <div class="text-6xl mb-6 text-center">💚</div>
                    <h3 class="text-2xl font-bold mb-3 text-gray-800">System Health</h3>
                    <p class="text-gray-600 mb-6">Development monitoring</p>
                    <div class="text-sm text-gray-500 mb-4">
                        🛠️ Health monitoring<br>
                        🔧 System diagnostics<br>
                        📊 Dev environment status
                    </div>
                    <a href="/health" class="block w-full bg-gray-600 text-white text-center px-6 py-3 rounded-xl hover:bg-gray-700 font-semibold transition-colors">
                        Check Dev Health
                    </a>
                </div>
            </div>
            
            <!-- Development Environment Info -->
            <div class="demo-card p-8 text-center">
                <h3 class="text-3xl font-bold mb-4 text-gray-800">🛠️ Development Environment</h3>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-6 text-center">
                    <div>
                        <div class="text-2xl font-bold text-blue-600">DEV</div>
                        <div class="text-sm text-gray-600">Environment</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-green-600">SAFE</div>
                        <div class="text-sm text-gray-600">Testing</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-purple-600">5</div>
                        <div class="text-sm text-gray-600">Systems</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-orange-600">READY</div>
                        <div class="text-sm text-gray-600">For Development</div>
                    </div>
                </div>
                <p class="text-gray-600 mt-6">Safe development environment for testing and iteration before production</p>
            </div>
        </div>
    </body>
    </html>
    ''')

# Same dashboard routes as before, but clearly marked as development
@app.route('/patient-portal')
def patient_portal():
    """Personalized patient portal"""
    # Get customer info from URL parameters
    customer_email = request.args.get('email', '')
    customer_phone = request.args.get('phone', '')
    
    # If no parameters, redirect to login
    if not customer_email or not customer_phone:
        return redirect('/customer-login')
    
    # Extract customer name from email for personalization
    if '@' in customer_email:
        name_part = customer_email.split('@')[0]
        if '.' in name_part:
            first_name, last_name = name_part.split('.', 1)
            customer_name = f"{first_name.title()} {last_name.title()}"
        else:
            customer_name = name_part.title()
    else:
        customer_name = "Valued Customer"
    
    try:
        with open('partnership_demo.html', 'r') as f:
            html_content = f.read()
        
        # Personalize the content
        html_content = html_content.replace('Elena Garcia', customer_name)
        html_content = html_content.replace('elena.garcia@email.com', customer_email)
        html_content = html_content.replace('(661) 555-0103', customer_phone)
        
        # Update trip count for new customers
        if 'new' in customer_email.lower() or 'test' in customer_email.lower():
            html_content = html_content.replace('156 Completed Trips', '0 Completed Trips')
            html_content = html_content.replace('Trip History', 'Welcome! Ready to Book Your First Trip')
        
        return html_content
    except FileNotFoundError:
        return jsonify({"error": "Patient portal HTML file not found", "environment": "development"}), 404

@app.route('/patient-portal-demo')
def patient_portal_demo():
    """Original demo portal (Elena Garcia)"""
    try:
        with open('partnership_demo.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return jsonify({"error": "Demo portal HTML file not found", "environment": "development"}), 404

@app.route('/driver-dashboard')
def driver_dashboard():
    """Development Driver dashboard"""
    try:
        with open('driver_dashboard.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return jsonify({"error": "Driver dashboard HTML file not found", "environment": "development"}), 404

@app.route('/insurance-admin')
def insurance_admin():
    """Development Insurance admin"""
    try:
        with open('insurance_admin_dashboard.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return jsonify({"error": "Insurance admin HTML file not found", "environment": "development"}), 404

@app.route('/dispatch-center')
def dispatch_center():
    """Development Dispatch center"""
    try:
        with open('dispatch_operations_center.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return jsonify({"error": "Dispatch center HTML file not found", "environment": "development"}), 404

@app.route('/new-customer')
def new_customer_registration():
    """New customer registration and booking system"""
    try:
        with open('new_customer_registration.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return jsonify({
            "error": "New customer registration HTML file not found",
            "environment": "development"
        }), 404


# -----------------------------
# PATIENT DASHBOARD ROUTE
# -----------------------------
@app.route('/patient-dashboard')
def patient_dashboard():
    """Patient dashboard with profile section"""
    try:
        with open('patient-dashboard.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return jsonify({
            "error": "Patient dashboard HTML file not found",
            "environment": "development"
        }), 404


# -----------------------------
# GET PATIENT PROFILE API
# -----------------------------
@app.route('/api/patient/profile', methods=['GET'])
@app.route('/api/patient/profile/<patient_id>', methods=['GET'])
def get_patient_profile(patient_id=None):
    """Get patient profile data from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if patient_id is None:
            cursor.execute("SELECT TOP 1 patient_id FROM medical.patients ORDER BY created_at DESC")
            row = cursor.fetchone()
            if row:
                patient_id = row[0]
            else:
                return jsonify({"error": "No patients found"}), 404
        
        cursor.execute("""
            SELECT p.patient_id, p.mrn, p.first_name, p.last_name, p.date_of_birth,
                   p.gender, p.phone_primary, p.email, p.emergency_contact_name,
                   p.emergency_contact_phone, p.emergency_contact_relationship
            FROM medical.patients p WHERE p.patient_id = ?
        """, (patient_id,))
        
        patient_row = cursor.fetchone()
        if not patient_row:
            return jsonify({"error": "Patient not found"}), 404
        
        patient_data = {
            "patient_id": str(patient_row[0]),
            "mrn": patient_row[1],
            "first_name": patient_row[2],
            "last_name": patient_row[3],
            "date_of_birth": str(patient_row[4]) if patient_row[4] else None,
            "gender": patient_row[5],
            "phone": patient_row[6],
            "email": patient_row[7],
            "emergency_contact": {
                "name": patient_row[8],
                "phone": patient_row[9],
                "relationship": patient_row[10]
            }
        }
        
        # Get address
        cursor.execute("""
            SELECT street_address, apartment_unit, city, state, zip_code
            FROM medical.patient_addresses WHERE patient_id = ? AND is_primary = 1
        """, (patient_id,))
        addr = cursor.fetchone()
        if addr:
            patient_data["address"] = {"street": addr[0], "apartment": addr[1], "city": addr[2], "state": addr[3], "zip_code": addr[4]}
        
        # Get insurance
        cursor.execute("""
            SELECT insurance_provider, member_id, group_number, coverage_status
            FROM medical.patient_insurance WHERE patient_id = ? AND is_primary = 1
        """, (patient_id,))
        ins = cursor.fetchone()
        if ins:
            patient_data["insurance"] = {"provider": ins[0], "member_id": ins[1], "group_number": ins[2], "coverage_status": ins[3]}
        
        # Get medical info
        cursor.execute("""
            SELECT mobility_equipment, assistance_level, oxygen_required, medical_notes, requires_assistance
            FROM medical.patient_medical_info WHERE patient_id = ?
        """, (patient_id,))
        med = cursor.fetchone()
        if med:
            patient_data["medical"] = {"mobility_equipment": med[0], "assistance_level": med[1], "oxygen_required": med[2], "medical_notes": med[3], "requires_assistance": bool(med[4])}
        
        conn.close()
        return jsonify({"status": "success", "data": patient_data, "environment": "DEVELOPMENT"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# -----------------------------
# UPDATE PATIENT PROFILE API
# -----------------------------
@app.route('/api/patient/profile', methods=['PUT'])
@app.route('/api/patient/profile/<patient_id>', methods=['PUT'])
def update_patient_profile(patient_id=None):
    """Update patient profile data"""
    try:
        data = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if patient_id is None:
            cursor.execute("SELECT TOP 1 patient_id FROM medical.patients ORDER BY created_at DESC")
            row = cursor.fetchone()
            if row:
                patient_id = row[0]
            else:
                return jsonify({"error": "No patients found"}), 404
        
        # Update personal info
        if any(k in data for k in ['first_name', 'last_name', 'phone', 'email']):
            cursor.execute("""
                UPDATE medical.patients SET 
                    first_name = COALESCE(?, first_name),
                    last_name = COALESCE(?, last_name),
                    phone_primary = COALESCE(?, phone_primary),
                    email = COALESCE(?, email),
                    updated_at = GETUTCDATE()
                WHERE patient_id = ?
            """, (data.get('first_name'), data.get('last_name'), data.get('phone'), data.get('email'), patient_id))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Profile updated"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# -----------------------------
# GET PATIENT TRIPS API
# -----------------------------
@app.route('/api/patient/trips', methods=['GET'])
@app.route('/api/patient/trips/<patient_id>', methods=['GET'])
def get_patient_trips(patient_id=None):
    """Get patient trip history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if patient_id is None:
            cursor.execute("SELECT TOP 1 patient_id FROM medical.patients ORDER BY created_at DESC")
            row = cursor.fetchone()
            if row:
                patient_id = row[0]
            else:
                return jsonify({"error": "No patients found"}), 404
        
        cursor.execute("""
            SELECT trip_id, trip_number, trip_date, pickup_time, pickup_address, 
                   dropoff_address, trip_status, trip_type, special_instructions
            FROM operations.trips WHERE patient_id = ?
            ORDER BY trip_date DESC
        """, (patient_id,))
        
        trips = []
        for row in cursor.fetchall():
            trips.append({
                "trip_id": str(row[0]), "trip_number": row[1],
                "trip_date": str(row[2]) if row[2] else None,
                "pickup_time": str(row[3]) if row[3] else None,
                "pickup_address": row[4], "dropoff_address": row[5],
                "status": row[6], "trip_type": row[7], "special_instructions": row[8]
            })
        
        conn.close()
        
        from datetime import date
        today = str(date.today())
        upcoming = [t for t in trips if t['trip_date'] and t['trip_date'] >= today and t['status'] in ('scheduled', 'confirmed')]
        history = [t for t in trips if t not in upcoming]
        
        return jsonify({"status": "success", "data": {"upcoming": upcoming, "history": history}})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# -----------------------------
# BOOK PATIENT TRIP API
# -----------------------------
@app.route('/api/patient/trips/book', methods=['POST'])
def book_patient_trip():
    """Book a new trip"""
    try:
        data = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        patient_id = data.get('patient_id')
        if not patient_id:
            cursor.execute("SELECT TOP 1 patient_id FROM medical.patients ORDER BY created_at DESC")
            row = cursor.fetchone()
            if row:
                patient_id = row[0]
            else:
                return jsonify({"error": "No patients found"}), 404
        
        from datetime import datetime
        import random
        trip_number = f"GVT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        
        cursor.execute("""
            INSERT INTO operations.trips 
            (patient_id, trip_number, trip_date, pickup_time, pickup_address, dropoff_address, trip_status, trip_type, special_instructions)
            VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)
        """, (patient_id, trip_number, data.get('trip_date'), data.get('pickup_time'),
              data.get('pickup_address'), data.get('dropoff_address'),
              data.get('trip_type', 'one_way'), data.get('special_instructions')))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "trip_number": trip_number})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route('/health')
def health_check():
    """Development system health check"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "environment": "DEVELOPMENT",
            "database": "golden-valley-transit-dev",
            "timestamp": datetime.now().isoformat(),
            "version": "2.1.0-dev",
            "safe_testing": True
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "environment": "DEVELOPMENT", 
            "database": "disconnected",
            "error": str(e)
        }), 503

@app.route('/api/demo-data')
def demo_data():
    """Development demo data"""
    try:
        stats = {}
        users = execute_query("SELECT COUNT(*) as count FROM security.users")
        stats['users'] = users[0]['count'] if users else 0
        
        trips = execute_query("SELECT COUNT(*) as count FROM operations.trips")
        stats['trips'] = trips[0]['count'] if trips else 0
        
        return jsonify({
            "status": "success",
            "environment": "DEVELOPMENT",
            "database": "golden-valley-transit-dev",
            "statistics": stats,
            "message": "Development data - safe for testing"
        })
    except Exception as e:
        return jsonify({"status": "error", "environment": "DEVELOPMENT", "error": str(e)}), 500

if __name__ == '__main__':
    print("🛠️  GOLDEN VALLEY TRANSIT - DEVELOPMENT ENVIRONMENT")
    print("=" * 60)
    print("🔗 Database: golden-valley-transit-dev (SAFE FOR TESTING)")
    print("🌐 Demo URL: http://192.168.5.39:5001/demo")
    print("🛠️  Environment: Development (break things safely)")
    print("🎯 Purpose: Testing & iteration before production")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=True)
