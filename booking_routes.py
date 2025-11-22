from flask import Blueprint, request, jsonify
import pyodbc
from datetime import datetime

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

@booking_bp.route('/api/booking/create', methods=['POST'])
def create_booking():
    """Create a new trip booking from website"""
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
        
        # Insert into Trips table
        cursor.execute("""
            INSERT INTO Trips (
                PatientName,
                PhoneNumber,
                PickupAddress,
                DropoffAddress,
                AppointmentDate,
                AppointmentTime,
                Status,
                CreatedDate,
                Notes
            ) VALUES (?, ?, ?, ?, ?, ?, 'Pending', GETDATE(), ?)
        """, (
            data['patient_name'],
            data['phone'],
            data['pickup_address'],
            data['dropoff_address'],
            data['appointment_date'],
            data['appointment_time'],
            data.get('notes', '')
        ))
        
        conn.commit()
        
        # Get the new trip ID
        cursor.execute("SELECT @@IDENTITY")
        trip_id = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Booking created successfully',
            'trip_id': trip_id
        }), 201
        
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
