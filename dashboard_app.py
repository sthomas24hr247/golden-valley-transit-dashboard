#!/usr/bin/env python3
from flask import Flask, send_file, jsonify, send_from_directory
from flask_cors import CORS
import os

# Import booking routes
from booking_routes import booking_bp
from insurance_verification import insurance_bp
from billing_system import billing_bp
from analytics_system import analytics_bp
from patient_api import patient_bp

app = Flask(__name__)
CORS(app)

# Register booking blueprint
app.register_blueprint(booking_bp)
app.register_blueprint(insurance_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(patient_bp)

# Route mapping
@app.route('/')
def index():
    return send_file('src/new_dashboard_landing.html')

@app.route('/dashboard')
def dashboard():
    return send_file('src/new_dashboard_landing.html')

@app.route('/new-customer-registration')
def new_customer():
    return send_file('new_customer_registration.html')

@app.route('/patient-portal')
def patient_login():
    return send_file('patient_login.html')

@app.route('/patient-dashboard')
def patient_portal():
    return send_file('patient-dashboard.html')

@app.route('/driver-dashboard')
def driver_dashboard():
    return send_file('driver_dashboard.html')

@app.route('/dispatcher-center')
def dispatcher():
    return send_file('dispatch_operations_center.html')

@app.route('/insurance-admin')
def insurance():
    return send_file('insurance_admin_dashboard.html')

@app.route('/analytics-dashboard')
def analytics_dashboard():
    return send_file('analytics_dashboard.html')

@app.route('/billing-dashboard')
def billing_dashboard():
    return send_file('billing_dashboard.html')

@app.route('/billing')
def billing():
    return send_file('billing_dashboard.html')

@app.route('/user-management')
def user_management():
    return send_from_directory('.', 'user_management.html')

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "Golden Valley Transit Dashboard"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
@app.route('/driver-dashboard-offline')
def driver_dashboard_offline():
    return send_from_directory('.', 'driver-dashboard-offline.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('.', 'sw.js', mimetype='application/javascript')
