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
    password = os.environ.get('DB_PASSWORD', 'SaQu12022!')
    
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
    
    print(f"Attempting connection to: {server}/{database}")  # Debug log
    return pyodbc.connect(connection_string)

def generate_patient_id(cursor):
    """Generate unique patient ID (GVT-XXX format)"""
    cursor.execute("SELECT MAX(PatientID) FROM medical.patients WHERE PatientID LIKE 'GVT-%'")
    result = cursor.fetchone()
    
    if result and result[0]:
        last_id = result[0]
        number = int(last_id.split('-')[1]) + 1
    else:
        number = 2
    
    return f"GVT-{number:03d}"

def generate_username(name):
    """Generate username from name"""
    first_name = name.split()[0].lower()
    random_num = ''.join(random.choices(string.digits, k=4))
    return f"{first_name}{random_num}"

def generate_password():
    """Generate temporary password"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def check_existing_patient(cursor, phone, email=None):
    """Check if patient already exists"""
    if email:
        cursor.execute("""
            SELECT PatientID, UserID FROM medical.patients 
            WHERE PhoneNumber = ? OR Email = ?
        """, (phone, email))
    else:
        cursor.execute("""
            SELECT PatientID, UserID FROM medical.patients 
            WHERE PhoneNumber = ?
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
        
        print(f"Creating booking for: {data['patient_name']}")  # Debug log
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        existing = check_existing_patient(cursor, data['phone'], data.get('email'))
        
        if existing:
            patient_id = existing[0]
            user_id = existing[1]
            is_new_patient = False
            print(f"Existing patient found: {patient_id}")  # Debug log
        else:
            patient_id = generate_patient_id(cursor)
            username = generate_username(data['patient_name'])
            temp_password = generate_password()
            
            print(f"Creating new patient: {patient_id}")  # Debug log
            
            cursor.execute("""
                INSERT INTO security.users (
                    Username, PasswordHash, Email, PhoneNumber, 
                    UserType, IsActive, CreatedDate
                ) VALUES (?, ?, ?, ?, 'Patient', 1, GETDATE())
            """, (username, temp_password, data.get('email', ''), data['phone']))
            
            cursor.execute("SELECT @@IDENTITY")
            user_id = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO medical.patients (
                    PatientID, UserID, FirstName, LastName, 
                    PhoneNumber, Email, Address, IsActive, CreatedDate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, GETDATE())
            """, (
                patient_id, user_id,
                data['patient_name'].split()[0],
                ' '.join(data['patient_name'].split()[1:]) if len(data['patient_name'].split()) > 1 else '',
                data['phone'], data.get('email', ''), data['pickup_address']
            ))
            
            is_new_patient = True
        
        cursor.execute("""
            INSERT INTO operations.trips (
                PatientID, PickupAddress, DropoffAddress,
                AppointmentDate, AppointmentTime, Status, CreatedDate
            ) VALUES (?, ?, ?, ?, ?, 'Pending', GETDATE())
        """, (
            patient_id, data['pickup_address'], data['dropoff_address'],
            data['appointment_date'], data['appointment_time']
        ))
        
        cursor.execute("SELECT @@IDENTITY")
        trip_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        response_data = {
            'success': True,
            'message': 'Booking created successfully',
            'trip_id': trip_id,
            'patient_id': patient_id
        }
        
        if is_new_patient:
            response_data['new_patient'] = True
            response_data['username'] = username
            response_data['temporary_password'] = temp_password
            response_data['portal_url'] = 'https://gvt-dashboard.azurewebsites.net/patient-portal'
        
        return jsonify(response_data), 201
        
    except Exception as e:
        print(f"Error: {str(e)}")  # Debug log
        return jsonify({'success': False, 'error': str(e)}), 500

@booking_bp.route('/api/booking/test', methods=['GET'])
def test_booking():
    """Test endpoint"""
    return jsonify({'success': True, 'message': 'Booking API is operational'})
