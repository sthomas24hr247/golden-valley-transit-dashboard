#!/usr/bin/env python3
from flask import Flask, send_file, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

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
def patient_portal():
    return send_file('partnership_demo.html')

@app.route('/driver-dashboard')
def driver_dashboard():
    return send_file('driver_dashboard.html')

@app.route('/dispatcher-center')
def dispatcher():
    return send_file('dispatch_operations_center.html')

@app.route('/insurance-admin')
def insurance():
    return send_file('insurance_admin_dashboard.html')

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "Golden Valley Transit Dashboard"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
