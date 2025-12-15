from flask import Blueprint, jsonify, request
import pyodbc
import os

patient_bp = Blueprint('patient', __name__)

def get_db_connection():
    conn_str = os.environ.get('DATABASE_CONNECTION_STRING')
    if not conn_str:
        conn_str = (
            "Driver={ODBC Driver 18 for SQL Server};"
            "Server=partnership-sql-server-v2.database.windows.net;"
            "Database=golden-valley-transit-prod;"
            "Uid=sqladmin;"
            "Pwd=" + os.environ.get('DB_PASSWORD', '') + ";"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
        )
    return pyodbc.connect(conn_str)

@patient_bp.route('/api/patient/profile', methods=['GET'])
@patient_bp.route('/api/patient/profile/<patient_id>', methods=['GET'])
def get_patient_profile(patient_id=None):
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
                   p.gender, p.phone, p.email, p.emergency_contact_name,
                   p.emergency_contact_phone, p.emergency_contact_relationship
            FROM medical.patients p WHERE p.patient_id = ?
        """, (patient_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Patient not found"}), 404
        
        data = {
            "patient_id": str(row[0]), "mrn": row[1], "first_name": row[2],
            "last_name": row[3], "date_of_birth": str(row[4]) if row[4] else None,
            "gender": row[5], "phone": row[6], "email": row[7],
            "emergency_contact": {"name": row[8], "phone": row[9], "relationship": row[10]}
        }
        
        # Get address
        cursor.execute("""
            SELECT street_address, apartment_unit, city, state, zip_code
            FROM medical.patient_addresses WHERE patient_id = ? AND is_primary = 1
        """, (patient_id,))
        addr = cursor.fetchone()
        if addr:
            data["address"] = {"street": addr[0], "apartment": addr[1], "city": addr[2], "state": addr[3], "zip_code": addr[4]}
        
        # Get insurance
        cursor.execute("""
            SELECT insurance_provider, member_id, group_number, coverage_status
            FROM medical.patient_insurance WHERE patient_id = ? AND is_primary = 1
        """, (patient_id,))
        ins = cursor.fetchone()
        if ins:
            data["insurance"] = {"provider": ins[0], "member_id": ins[1], "group_number": ins[2], "coverage_status": ins[3]}
        
        # Get medical info
        cursor.execute("""
            SELECT mobility_equipment, assistance_level, oxygen_required, medical_notes, requires_assistance
            FROM medical.patient_medical_info WHERE patient_id = ?
        """, (patient_id,))
        med = cursor.fetchone()
        if med:
            data["medical"] = {"mobility_equipment": med[0], "assistance_level": med[1], "oxygen_required": med[2], "medical_notes": med[3], "requires_assistance": bool(med[4]) if med[4] else False}
        
        conn.close()
        return jsonify({"status": "success", "data": data})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@patient_bp.route('/api/patient/profile', methods=['PUT'])
@patient_bp.route('/api/patient/profile/<patient_id>', methods=['PUT'])
def update_patient_profile(patient_id=None):
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
        
        if any(k in data for k in ['first_name', 'last_name', 'phone', 'email']):
            cursor.execute("""
                UPDATE medical.patients SET 
                    first_name = COALESCE(?, first_name),
                    last_name = COALESCE(?, last_name),
                    phone = COALESCE(?, phone),
                    email = COALESCE(?, email),
                    updated_at = GETUTCDATE()
                WHERE patient_id = ?
            """, (data.get('first_name'), data.get('last_name'), data.get('phone'), data.get('email'), patient_id))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Profile updated"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@patient_bp.route('/api/patient/trips', methods=['GET'])
@patient_bp.route('/api/patient/trips/<patient_id>', methods=['GET'])
def get_patient_trips(patient_id=None):
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

@patient_bp.route('/api/patient/trips/book', methods=['POST'])
def book_patient_trip():
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
