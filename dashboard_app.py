#!/usr/bin/env python3
from flask import Flask, send_file, jsonify
from flask_cors import CORS
import os

# Import booking routes
from booking_routes import booking_bp
from insurance_verification import insurance_bp
from billing_system import billing_bp
from analytics_system import analytics_bp

app = Flask(__name__)
CORS(app)

# Register booking blueprint
app.register_blueprint(booking_bp)
app.register_blueprint(insurance_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(analytics_bp)

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
    return send_file('patient_dashboard.html')

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

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "Golden Valley Transit Dashboard"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
