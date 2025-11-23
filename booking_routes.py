from flask import Blueprint, request, jsonify
import pyodbc
from datetime import datetime
import random
import string
import os

booking_bp = Blueprint('booking', __name__)

def get_db_connection():
    """Get database connection using environment variables"""
    server = os.environ.get('DB_SERVER', 'partnership-sql-server-v2.database.windows.net')
    database = os.environ.get('DB_DATABASE', 'golden-valley-transit-prod')
    username = os.environ.get('DB_USERNAME', 'sqladmin')
    password = os.environ.get('DB_PASSWORD', 'GoldenValley2025')
    
    connection_string = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    
    return pyodbc.connect(connection_string)

def generate_mrn():
    """Generate MRN (Medical Record Number)"""
    return f"GVT{random.randint(100000, 999999)}"

def generate_username(name):
    """Generate username from name"""
    first_name = name.split()[0].lower()
    random_num = ''.join(random.choices(string.digits, k=4))
    return f"{first_name}{random_num}"

def generate_password():
    """Generate temporary password"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))


def generate_trip_number():
    """Generate unique trip number"""
    from datetime import datetime
    date_str = datetime.now().strftime('%Y%m%d')
    random_num = random.randint(1000, 9999)
    return f"GVT-{date_str}-{random_num}"

def check_existing_patient(cursor, phone):
    """Check if patient already exists"""
    cursor.execute("""
        SELECT patient_id, user_id FROM medical.patients 
        WHERE phone = ?
    """, (phone,))
    return cursor.fetchone()

@booking_bp.route('/api/booking/create', methods=['POST'])
def create_booking():
    """Create new trip booking with automatic patient registration"""
    try:
        data = request.json
        
        required_fields = ['patient_name', 'phone', 'pickup_address', 
                          'dropoff_address', 'appointment_date', 'appointment_time']
        
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        existing = check_existing_patient(cursor, data['phone'])
        
        if existing:
            patient_id = existing[0]
            user_id = existing[1]
            is_new_patient = False
        else:
            # Generate IDs
            user_id = None  # Will be auto-generated as uniqueidentifier
            patient_id = None  # Will be auto-generated as uniqueidentifier
            mrn = generate_mrn()
            username = generate_username(data['patient_name'])
            temp_password = generate_password()
            
            # Create User account
            cursor.execute("""
                INSERT INTO security.users (
                    username, password_hash, email, phone, 
                    first_name, last_name, user_type, status, created_at
                ) OUTPUT INSERTED.user_id
                VALUES (?, ?, ?, ?, ?, ?, 'patient', 'active', GETDATE())
            """, (
                username, temp_password, data.get('email', ''), data['phone'],
                data['patient_name'].split()[0],
                ' '.join(data['patient_name'].split()[1:]) if len(data['patient_name'].split()) > 1 else '',
            ))
            
            user_id = cursor.fetchone()[0]
            
            # Create Patient record
            cursor.execute("""
                INSERT INTO medical.patients (
                    user_id, mrn, first_name, last_name, date_of_birth, phone, email,
                    status, created_at
                ) OUTPUT INSERTED.patient_id
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', GETDATE())
            """, (
                user_id, mrn,
                data['patient_name'].split()[0],
                ' '.join(data['patient_name'].split()[1:]) if len(data['patient_name'].split()) > 1 else '',
                data.get('date_of_birth', '1900-01-01'),
                data['phone'], data.get('email', '')
            ))
            
            patient_id = cursor.fetchone()[0]
            is_new_patient = True
        
        # Combine appointment date and time
        appointment_datetime = f"{data['appointment_date']} {data['appointment_time']}"
        
        # Create the trip
        trip_number = generate_trip_number()
        
        trip_number = generate_trip_number()
        
        cursor.execute("""
            INSERT INTO operations.trips (
                trip_number, patient_id, pickup_address, destination_address,
                scheduled_pickup_time, trip_type, status, 
                booking_source, created_at
            ) OUTPUT INSERTED.trip_id
            VALUES (?, ?, ?, ?, ?, 'Medical Appointment', 'scheduled', 'web', GETDATE())
        """, (
            trip_number, patient_id, data['pickup_address'], data['dropoff_address'],
            appointment_datetime
        ))
        
        trip_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        response_data = {
            'success': True,
            'message': 'Booking created successfully',
            'trip_id': str(trip_id),
            'patient_id': str(patient_id)
        }
        
        if is_new_patient:
            response_data['new_patient'] = True
            response_data['username'] = username
            response_data['temporary_password'] = temp_password
            response_data['portal_url'] = 'https://gvt-dashboard.azurewebsites.net/patient-portal'
        
        return jsonify(response_data), 201
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@booking_bp.route('/api/booking/test', methods=['GET'])
def test_booking():
    """Test endpoint"""
    return jsonify({'success': True, 'message': 'Booking API is operational'})
