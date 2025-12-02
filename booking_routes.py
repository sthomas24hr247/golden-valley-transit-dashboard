from flask import Blueprint, request, jsonify
import pyodbc
from datetime import datetime
import random
import string
import os

# Try to import SendGrid - if not available, emails won't send but app will work
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    print("SendGrid not installed - email functionality disabled")

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
    if not name or not name.strip():
        first_name = "patient"
    else:
        parts = name.split()
        first_name = parts[0].lower() if parts else "patient"
    random_num = ''.join(random.choices(string.digits, k=4))
    return f"{first_name}{random_num}"

def generate_password():
    """Generate temporary password"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def generate_trip_number():
    """Generate unique trip number"""
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
    try:
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
    try:
        if isinstance(appointment_time, str):
            time_obj = datetime.strptime(appointment_time, '%Y-%m-%d %H:%M')
        else:
            time_obj = appointment_time
        
        hour = time_obj.hour
        return 6 <= hour < 22
    except:
        return False

def send_welcome_email(email, patient_name, username, temp_password):
    """Send welcome email to new patient using SendGrid"""
    if not SENDGRID_AVAILABLE:
        print("SendGrid not available - skipping email")
        return False
    
    try:
        api_key = os.environ.get('SENDGRID_API_KEY')
        from_email = os.environ.get('SENDGRID_FROM_EMAIL', 'info@goldenvalleytransit.com')
        
        if not api_key:
            print("SendGrid API key not configured")
            return False
        
        if not email:
            print("No email address provided")
            return False
        
        # Use patient name or default
        display_name = patient_name if patient_name and patient_name.strip() else "Valued Patient"
        
        message = Mail(
            from_email=from_email,
            to_emails=email,
            subject='Welcome to Golden Valley Transit!',
            html_content=f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #667eea; margin: 0;">Golden Valley Transit</h1>
                        <p style="color: #718096;">Caring Medical Transportation for the Central Valley</p>
                    </div>
                    
                    <h2 style="color: #2d3748;">Welcome, {display_name}!</h2>
                    <p style="color: #4a5568;">Your patient account has been created successfully.</p>
                    
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 12px; margin: 25px 0; color: white;">
                        <h3 style="margin-top: 0; color: white;">Your Login Credentials</h3>
                        <p style="margin: 10px 0;"><strong>Username:</strong> {username}</p>
                        <p style="margin: 10px 0;"><strong>Temporary Password:</strong> {temp_password}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://gvt-dashboard.azurewebsites.net/patient-portal" 
                           style="background: #667eea; color: white; padding: 14px 28px; 
                                  text-decoration: none; border-radius: 8px; display: inline-block;
                                  font-weight: bold;">
                            Access Your Patient Portal
                        </a>
                    </div>
                    
                    <p style="color: #718096; text-align: center;">
                        Questions? Call us at (661) 555-0100
                    </p>
                </div>
            '''
        )
        
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        print(f"Welcome email sent to {email}: Status {response.status_code}")
        return True
        
    except Exception as e:
        print(f"Failed to send welcome email: {str(e)}")
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
            username = None
            temp_password = None
        else:
            mrn = generate_mrn()
            username = generate_username(data['patient_name'])
            temp_password = generate_password()
            
            name_parts = data['patient_name'].split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
            cursor.execute("""
                INSERT INTO security.users (
                    username, password_hash, email, phone, 
                    first_name, last_name, user_type, status, created_at
                ) OUTPUT INSERTED.user_id
                VALUES (?, ?, ?, ?, ?, ?, 'patient', 'active', GETDATE())
            """, (
                username, temp_password, data.get('email', ''), data['phone'],
                first_name, last_name
            ))
            
            user_id = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO medical.patients (
                    user_id, mrn, first_name, last_name, date_of_birth, phone, email,
                    status, created_at
                ) OUTPUT INSERTED.patient_id
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', GETDATE())
            """, (
                user_id, mrn, first_name, last_name,
                data.get('date_of_birth', '1900-01-01'),
                data['phone'], data.get('email', '')
            ))
            
            patient_id = cursor.fetchone()[0]
            is_new_patient = True

        if data.get('insurance_company') and data.get('policy_number'):
            from datetime import timedelta
            effective_date = datetime.now().date()
            expiration_date = effective_date + timedelta(days=365)
            
            insurance_company_lower = data['insurance_company'].lower()
            if 'medi-cal' in insurance_company_lower or 'medicaid' in insurance_company_lower:
                prior_auth = False
                copay = 0.00
            elif 'medicare' in insurance_company_lower:
                prior_auth = False
                copay = 0.00
            else:
                prior_auth = True
                copay = 15.00
            
            cursor.execute("""
                INSERT INTO medical.patient_insurance (
                    patient_id, insurance_company, policy_number,
                    effective_date, expiration_date,
                    copay_amount, prior_authorization_required, 
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', GETDATE())
            """, (
                patient_id, data['insurance_company'], data['policy_number'],
                effective_date, expiration_date, copay, prior_auth
            ))

        appointment_datetime = f"{data['appointment_date']} {data['appointment_time']}"
        
        if not validate_business_hours(appointment_datetime):
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Appointments must be between 6:00 AM and 10:00 PM'
            }), 400
        
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
            'trip_number': trip_number,
            'patient_id': str(patient_id),
            'driver_assigned': driver_assigned,
            'driver_name': driver_name if driver_assigned else 'Pending dispatcher assignment'
        }
        
        if is_new_patient:
            response_data['new_patient'] = True
            response_data['username'] = username
            response_data['temporary_password'] = temp_password
            response_data['portal_url'] = 'https://gvt-dashboard.azurewebsites.net/patient-portal'
            
            if data.get('email'):
                email_sent = send_welcome_email(
                    data['email'], 
                    data['patient_name'], 
                    username, 
                    temp_password
                )
                response_data['email_sent'] = email_sent
            else:
                response_data['email_sent'] = False
        
        return jsonify(response_data), 201
        
    except Exception as e:
        print(f"Booking error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@booking_bp.route('/api/booking/test', methods=['GET'])
def test_booking():
    """Test endpoint"""
    return jsonify({'success': True, 'message': 'Booking API is operational'})


@booking_bp.route('/api/send-welcome-email-alt', methods=['POST'])
def send_welcome_email_alt():
    """Alternative endpoint for sending welcome email from registration form"""
    try:
        data = request.json
        
        first_name = data.get('firstName', '').strip()
        last_name = data.get('lastName', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        
        if not email:
            return jsonify({'success': False, 'message': 'Email is required'}), 400
        
        # Generate credentials with safe defaults
        full_name = f"{first_name} {last_name}".strip()
        username = generate_username(full_name)
        temp_password = generate_password()
        mrn = generate_mrn()
        
        # Try to create user in database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if user already exists by email
            cursor.execute("SELECT user_id FROM security.users WHERE email = ?", (email,))
            existing = cursor.fetchone()
            
            if not existing:
                # Create user
                cursor.execute("""
                    INSERT INTO security.users (
                        username, password_hash, email, phone,
                        first_name, last_name, user_type, status, created_at
                    ) OUTPUT INSERTED.user_id
                    VALUES (?, ?, ?, ?, ?, ?, 'patient', 'active', GETDATE())
                """, (username, temp_password, email, phone, first_name, last_name))
                
                user_id = cursor.fetchone()[0]
                
                # Create patient record
                cursor.execute("""
                    INSERT INTO medical.patients (
                        user_id, mrn, first_name, last_name, date_of_birth, phone, email,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, '1900-01-01', ?, ?, 'active', GETDATE())
                """, (user_id, mrn, first_name, last_name, phone, email))
                
                conn.commit()
                print(f"Created new patient: {first_name} {last_name} ({email})")
            else:
                print(f"User already exists: {email}")
            
            cursor.close()
            conn.close()
        except Exception as db_error:
            print(f"Database error (non-fatal): {str(db_error)}")
        
        # Send welcome email
        patient_name = full_name if full_name else "Valued Patient"
        email_sent = send_welcome_email(email, patient_name, username, temp_password)
        
        if email_sent:
            return jsonify({
                'success': True,
                'message': 'Welcome email sent successfully',
                'username': username
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Account created but email could not be sent',
                'username': username,
                'email_sent': False
            })
            
    except Exception as e:
        print(f"Send welcome email error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
# Patient Portal API Endpoints
@booking_bp.route('/api/patient/login', methods=['POST'])
def patient_login():
    """Patient login endpoint"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check credentials
        cursor.execute("""
            SELECT u.user_id, u.first_name, u.last_name, u.password_hash, p.patient_id
            FROM security.users u
            LEFT JOIN medical.patients p ON u.user_id = p.user_id
            WHERE u.username = ? AND u.user_type = 'patient' AND u.status = 'active'
        """, (username,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
        
        # Simple password check (in production, use proper hashing)
        if user[3] != password:
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
        
        return jsonify({
            'success': True,
            'token': f"patient_{user[4]}_{random.randint(1000,9999)}",
            'patient_id': str(user[4]),
            'patient_name': f"{user[1]} {user[2]}"
        })
        
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({'success': False, 'error': 'Login failed'}), 500


@booking_bp.route('/api/patient/<patient_id>/trips', methods=['GET'])
def get_patient_trips(patient_id):
    """Get patient's upcoming and past trips"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get upcoming trips
        cursor.execute("""
            SELECT t.trip_id, t.trip_number, t.pickup_address, t.destination_address,
                   t.scheduled_pickup_time, t.status,
                   COALESCE(d.driver_name, 'Pending') as driver_name
            FROM operations.trips t
            LEFT JOIN operations.drivers d ON t.driver_id = d.driver_id
            WHERE t.patient_id = ? 
              AND t.scheduled_pickup_time >= GETDATE()
              AND t.status NOT IN ('completed', 'cancelled')
            ORDER BY t.scheduled_pickup_time ASC
        """, (patient_id,))
        
        upcoming = []
        for row in cursor.fetchall():
            upcoming.append({
                'trip_id': str(row[0]),
                'trip_number': row[1],
                'pickup_address': row[2],
                'destination_address': row[3],
                'scheduled_pickup_time': row[4].isoformat() if row[4] else None,
                'status': row[5],
                'driver_name': row[6]
            })
        
        # Get trip history
        cursor.execute("""
            SELECT TOP 10 t.trip_id, t.trip_number, t.pickup_address, t.destination_address,
                   t.scheduled_pickup_time, t.status
            FROM operations.trips t
            WHERE t.patient_id = ? 
              AND (t.scheduled_pickup_time < GETDATE() OR t.status IN ('completed', 'cancelled'))
            ORDER BY t.scheduled_pickup_time DESC
        """, (patient_id,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'trip_id': str(row[0]),
                'trip_number': row[1],
                'pickup_address': row[2],
                'destination_address': row[3],
                'scheduled_pickup_time': row[4].isoformat() if row[4] else None,
                'status': row[5]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'upcoming': upcoming,
            'history': history
        })
        
    except Exception as e:
        print(f"Get trips error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
