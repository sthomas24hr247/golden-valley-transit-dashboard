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


def find_available_driver(cursor, pickup_time):
    """Find best available driver based on schedule and availability"""
    # Extract just the time portion for shift comparison
    try:
        from datetime import datetime
        if isinstance(pickup_time, str):
            time_obj = datetime.strptime(pickup_time, '%Y-%m-%d %H:%M')
        else:
            time_obj = pickup_time
        pickup_time_only = time_obj.strftime('%H:%M:%S')
    except:
        pickup_time_only = pickup_time
    
    cursor.execute("""
        SELECT TOP 1 
            d.driver_id,
            u.first_name + ' ' + u.last_name as driver_name,
            d.performance_rating
        FROM operations.drivers d
        INNER JOIN security.users u ON d.user_id = u.user_id
        WHERE d.current_status = 'available'
          AND u.status = 'active'
          AND CAST(? AS TIME) BETWEEN d.shift_start AND d.shift_end
        ORDER BY 
            d.performance_rating DESC,
            d.total_trips_completed DESC
    """, (pickup_time_only,))
    
    return cursor.fetchone()

def assign_driver_to_trip(cursor, trip_id, driver_id):
    """Assign driver to trip"""
    cursor.execute("""
        UPDATE operations.trips 
        SET driver_id = ?,
            status = 'assigned',
            updated_at = GETDATE()
        WHERE trip_id = ?
    """, (driver_id, trip_id))

def validate_business_hours(appointment_time):
    """Validate appointment is within business hours (6 AM - 10 PM)"""
    from datetime import datetime
    try:
        if isinstance(appointment_time, str):
            time_obj = datetime.strptime(appointment_time, '%Y-%m-%d %H:%M')
        else:
            time_obj = appointment_time
        
        hour = time_obj.hour
        return 6 <= hour < 22  # 6 AM to 10 PM
    except:
        return False

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
            VALUES (?, ?, ?, ?, ?, 'routine', 'scheduled', 'web', GETDATE())
        """, (
            trip_number, patient_id, data['pickup_address'], data['dropoff_address'],
            appointment_datetime
        ))
        
        trip_id = cursor.fetchone()[0]
        
        # Validate business hours (6 AM - 10 PM)
        if not validate_business_hours(appointment_datetime):
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Appointments must be between 6:00 AM and 10:00 PM'
            }), 400
        
        # Auto-assign driver if available
        driver_info = find_available_driver(cursor, appointment_datetime)
        driver_assigned = False
        driver_name = None
        
        if driver_info:
            driver_id = driver_info[0]
            driver_name = driver_info[1]
            assign_driver_to_trip(cursor, trip_id, driver_id)
            driver_assigned = True
        
        conn.commit()
        cursor.close()
        conn.close()
        
        response_data = {
            'success': True,
            'message': 'Booking created successfully',
            'trip_id': str(trip_id),
            'patient_id': str(patient_id),
            'driver_assigned': driver_assigned,
            'driver_name': driver_name if driver_assigned else 'Pending dispatcher assignment'
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
