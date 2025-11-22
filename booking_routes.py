from flask import Blueprint, request, jsonify
import pyodbc
from datetime import datetime
import random
import string

booking_bp = Blueprint('booking', __name__)

def get_db_connection():
    """Get database connection"""
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=partnership-sql-server.database.windows.net;"
        "DATABASE=golden-valley-transit-dev;"
        "UID=info;"
        "PWD=SaQu12022!;"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )
    return pyodbc.connect(connection_string)

def generate_patient_id(cursor):
    """Generate unique patient ID (GVT-XXX format)"""
    cursor.execute("SELECT MAX(PatientID) FROM Patients WHERE PatientID LIKE 'GVT-%'")
    result = cursor.fetchone()
    
    if result and result[0]:
        # Extract number and increment
        last_id = result[0]
        number = int(last_id.split('-')[1]) + 1
    else:
        number = 2  # Start at 2 (Elena is GVT-001)
    
    return f"GVT-{number:03d}"

def generate_username(name):
    """Generate username from name"""
    # Take first name and add random numbers
    first_name = name.split()[0].lower()
    random_num = ''.join(random.choices(string.digits, k=4))
    return f"{first_name}{random_num}"

def generate_password():
    """Generate temporary password"""
    # 8 characters: letters + numbers
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def check_existing_patient(cursor, phone, email=None):
    """Check if patient already exists by phone or email"""
    if email:
        cursor.execute("""
            SELECT PatientID, UserID FROM Patients 
            WHERE PhoneNumber = ? OR Email = ?
        """, (phone, email))
    else:
        cursor.execute("""
            SELECT PatientID, UserID FROM Patients 
            WHERE PhoneNumber = ?
        """, (phone,))
    
    return cursor.fetchone()

@booking_bp.route('/api/booking/create', methods=['POST'])
def create_booking():
    """Create a new trip booking with automatic patient registration"""
    try:
        data = request.json
        
        # Validate required fields
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
        
        # Check if patient already exists
        existing = check_existing_patient(cursor, data['phone'], data.get('email'))
        
        if existing:
            # Existing patient - just create trip
            patient_id = existing[0]
            user_id = existing[1]
            is_new_patient = False
        else:
            # New patient - create full registration
            
            # Generate credentials
            patient_id = generate_patient_id(cursor)
            username = generate_username(data['patient_name'])
            temp_password = generate_password()
            
            # Create User account
            cursor.execute("""
                INSERT INTO Users (
                    Username, 
                    PasswordHash, 
                    Email, 
                    PhoneNumber, 
                    UserType, 
                    IsActive, 
                    CreatedDate
                ) VALUES (?, ?, ?, ?, 'Patient', 1, GETDATE())
            """, (
                username,
                temp_password,  # In production, hash this!
                data.get('email', ''),
                data['phone']
            ))
            
            # Get the new UserID
            cursor.execute("SELECT @@IDENTITY")
            user_id = cursor.fetchone()[0]
            
            # Create Patient record
            cursor.execute("""
                INSERT INTO Patients (
                    PatientID,
                    UserID,
                    FirstName,
                    LastName,
                    DateOfBirth,
                    PhoneNumber,
                    Email,
                    Address,
                    EmergencyContact,
                    MedicalConditions,
                    MobilityRequirements,
                    PreferredLanguage,
                    InsuranceProvider,
                    InsurancePolicyNumber,
                    IsActive,
                    CreatedDate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE())
            """, (
                patient_id,
                user_id,
                data['patient_name'].split()[0] if data['patient_name'] else '',
                ' '.join(data['patient_name'].split()[1:]) if len(data['patient_name'].split()) > 1 else '',
                data.get('date_of_birth', None),
                data['phone'],
                data.get('email', ''),
                data['pickup_address'],  # Use pickup as default address
                data.get('emergency_contact', ''),
                data.get('medical_conditions', ''),
                data.get('mobility_requirements', ''),
                data.get('language', 'English'),
                data.get('insurance_provider', ''),
                data.get('insurance_policy', ''),
            ))
            
            is_new_patient = True
        
        # Create the trip
        cursor.execute("""
            INSERT INTO Trips (
                PatientID,
                PickupAddress,
                PickupCity,
                PickupZip,
                DropoffAddress,
                DropoffCity,
                DropoffZip,
                AppointmentDate,
                AppointmentTime,
                TripType,
                Status,
                PriorityLevel,
                SpecialRequirements,
                EstimatedDistance,
                EstimatedDuration,
                CreatedDate,
                CreatedBy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, 0, 0, GETDATE(), ?)
        """, (
            patient_id,
            data['pickup_address'],
            data.get('pickup_city', 'Bakersfield'),
            data.get('pickup_zip', '93301'),
            data['dropoff_address'],
            data.get('dropoff_city', 'Bakersfield'),
            data.get('dropoff_zip', '93301'),
            data['appointment_date'],
            data['appointment_time'],
            data.get('trip_type', 'Medical Appointment'),
            data.get('priority', 'Standard'),
            data.get('notes', ''),
            user_id
        ))
        
        # Get the new trip ID
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
        
        # If new patient, include login credentials
        if is_new_patient:
            response_data['new_patient'] = True
            response_data['username'] = username
            response_data['temporary_password'] = temp_password
            response_data['portal_url'] = 'https://gvt-dashboard.azurewebsites.net/patient-portal'
        
        return jsonify(response_data), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@booking_bp.route('/api/booking/test', methods=['GET'])
def test_booking():
    """Test endpoint to verify booking API is working"""
    return jsonify({
        'success': True,
        'message': 'Booking API is operational'
    })

@booking_bp.route('/api/patient/check', methods=['POST'])
def check_patient():
    """Check if patient exists by phone number"""
    try:
        data = request.json
        phone = data.get('phone')
        
        if not phone:
            return jsonify({
                'success': False,
                'error': 'Phone number required'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        existing = check_existing_patient(cursor, phone)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'exists': existing is not None,
            'patient_id': existing[0] if existing else None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
