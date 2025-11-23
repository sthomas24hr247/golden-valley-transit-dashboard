from flask import Blueprint, request, jsonify
import pyodbc
from datetime import datetime, date
import os
import random

billing_bp = Blueprint('billing', __name__)

def get_db_connection():
    """Get database connection"""
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

def generate_claim_number():
    """Generate unique claim number"""
    date_str = datetime.now().strftime('%Y%m%d')
    random_num = random.randint(1000, 9999)
    return f"CLM-{date_str}-{random_num}"

def calculate_mileage(pickup_address, dropoff_address):
    """Calculate mileage between addresses (mock - integrate with Google Maps API later)"""
    # TODO: Replace with actual Google Maps Distance Matrix API call
    # For now, return estimated mileage based on address distance
    return round(random.uniform(3.0, 15.0), 2)

def get_rate_schedule(cursor, payer_type, service_type):
    """Get current rate schedule for payer type and service"""
    cursor.execute("""
        SELECT base_rate, per_mile_rate, wait_time_rate, 
               after_hours_surcharge, weekend_surcharge
        FROM billing.rate_schedules
        WHERE payer_type = ? 
          AND service_type = ?
          AND is_active = 1
          AND effective_date <= GETDATE()
          AND (expiration_date IS NULL OR expiration_date >= GETDATE())
        ORDER BY effective_date DESC
    """, (payer_type.lower(), service_type.lower()))
    
    result = cursor.fetchone()
    if result:
        return {
            'base_rate': float(result[0]),
            'per_mile_rate': float(result[1]),
            'wait_time_rate': float(result[2]),
            'after_hours_surcharge': float(result[3]) if result[3] else 0.0,
            'weekend_surcharge': float(result[4]) if result[4] else 0.0
        }
    return None

@billing_bp.route('/api/billing/generate-claim', methods=['POST'])
def generate_claim():
    """Auto-generate claim from completed trip"""
    try:
        data = request.json
        trip_id = data.get('trip_id')
        
        if not trip_id:
            return jsonify({
                'success': False,
                'error': 'trip_id is required'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get trip details with patient and insurance info
        cursor.execute("""
            SELECT 
                t.trip_id, t.patient_id, t.pickup_address, t.destination_address,
                t.scheduled_pickup_time,
                p.first_name, p.last_name,
                pi.insurance_id, pi.insurance_company, pi.policy_number,
                pi.copay_amount
            FROM operations.trips t
            INNER JOIN medical.patients p ON t.patient_id = p.patient_id
            LEFT JOIN medical.patient_insurance pi ON p.patient_id = pi.patient_id 
                AND pi.is_primary = 1 AND pi.status = 'active'
            WHERE t.trip_id = ?
        """, (trip_id,))
        
        trip = cursor.fetchone()
        
        if not trip:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Trip not found'
            }), 404
        
        if not trip[7]:  # insurance_id
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'No active insurance found for patient'
            }), 400
        
        # Check if claim already exists for this trip
        cursor.execute("""
            SELECT claim_id FROM billing.claims WHERE trip_id = ?
        """, (trip_id,))
        
        existing_claim = cursor.fetchone()
        if existing_claim:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Claim already exists for this trip',
                'claim_id': str(existing_claim[0])
            }), 400
        
        # Determine payer type from insurance company
        insurance_company = trip[8].lower()
        if 'medi-cal' in insurance_company or 'medicaid' in insurance_company:
            payer_type = 'medi-cal'
        elif 'medicare' in insurance_company:
            payer_type = 'medicare'
        else:
            payer_type = 'commercial'
        
        # For now, assume wheelchair service (can be enhanced to detect from trip details)
        service_type = 'wheelchair'
        
        # Get rate schedule
        rates = get_rate_schedule(cursor, payer_type, service_type)
        
        if not rates:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': f'No rate schedule found for {payer_type} - {service_type}'
            }), 400
        
        # Calculate mileage
        mileage = calculate_mileage(trip[2], trip[3])
        
        # Calculate costs
        base_charge = rates['base_rate']
        mileage_charge = mileage * rates['per_mile_rate']
        total_amount = base_charge + mileage_charge
        
        # Apply surcharges if applicable
        service_date = trip[4].date() if trip[4] else date.today()
        if service_date.weekday() >= 5:  # Weekend
            total_amount += rates['weekend_surcharge']
        
        # Generate claim number
        claim_number = generate_claim_number()
        
        # Create claim
        cursor.execute("""
            INSERT INTO billing.claims (
                claim_number, trip_id, patient_id, insurance_id,
                service_date, claim_status, total_amount, 
                patient_responsibility, created_at
            ) OUTPUT INSERTED.claim_id
            VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, GETDATE())
        """, (
            claim_number, trip_id, trip[1], trip[7],
            service_date, float(total_amount), float(trip[10]) if trip[10] else 0.00
        ))
        
        claim_id = cursor.fetchone()[0]
        
        # Add line items
        # Base transportation charge
        cursor.execute("""
            INSERT INTO billing.claim_line_items (
                claim_id, line_number, service_code, service_description,
                quantity, unit_price, line_total
            ) VALUES (?, 1, 'A0130', 'Non-emergency wheelchair van transport', 1, ?, ?)
        """, (claim_id, float(base_charge), float(base_charge)))
        
        # Mileage charge
        cursor.execute("""
            INSERT INTO billing.claim_line_items (
                claim_id, line_number, service_code, service_description,
                quantity, unit_price, line_total
            ) VALUES (?, 2, 'S0215', 'Mileage', ?, ?, ?)
        """, (claim_id, float(mileage), float(rates['per_mile_rate']), float(mileage_charge)))
        
        # Create status history
        cursor.execute("""
            INSERT INTO billing.claim_status_history (
                claim_id, from_status, to_status, notes
            ) VALUES (?, NULL, 'draft', 'Claim auto-generated from completed trip')
        """, (claim_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'claim_id': str(claim_id),
            'claim_number': claim_number,
            'total_amount': float(total_amount),
            'breakdown': {
                'base_charge': float(base_charge),
                'mileage': float(mileage),
                'mileage_charge': float(mileage_charge),
                'patient_copay': float(trip[10]) if trip[10] else 0.0
            },
            'payer_type': payer_type,
            'insurance_company': trip[8]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@billing_bp.route('/api/billing/claim/<claim_id>', methods=['GET'])
def get_claim(claim_id):
    """Get claim details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.claim_number, c.service_date, c.claim_status,
                c.total_amount, c.approved_amount, c.paid_amount,
                c.patient_responsibility, c.submission_date, c.payment_date,
                c.denial_reason, c.payer_claim_number,
                p.first_name, p.last_name,
                pi.insurance_company, pi.policy_number,
                t.trip_number
            FROM billing.claims c
            INNER JOIN medical.patients p ON c.patient_id = p.patient_id
            INNER JOIN medical.patient_insurance pi ON c.insurance_id = pi.insurance_id
            INNER JOIN operations.trips t ON c.trip_id = t.trip_id
            WHERE c.claim_id = ?
        """, (claim_id,))
        
        claim = cursor.fetchone()
        
        if not claim:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Claim not found'
            }), 404
        
        # Get line items
        cursor.execute("""
            SELECT service_code, service_description, quantity, 
                   unit_price, line_total
            FROM billing.claim_line_items
            WHERE claim_id = ?
            ORDER BY line_number
        """, (claim_id,))
        
        line_items = []
        for row in cursor.fetchall():
            line_items.append({
                'service_code': row[0],
                'description': row[1],
                'quantity': float(row[2]),
                'unit_price': float(row[3]),
                'total': float(row[4])
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'claim': {
                'claim_number': claim[0],
                'service_date': str(claim[1]),
                'status': claim[2],
                'total_amount': float(claim[3]),
                'approved_amount': float(claim[4]) if claim[4] else None,
                'paid_amount': float(claim[5]),
                'patient_responsibility': float(claim[6]),
                'submission_date': str(claim[7]) if claim[7] else None,
                'payment_date': str(claim[8]) if claim[8] else None,
                'denial_reason': claim[9],
                'payer_claim_number': claim[10],
                'patient_name': f"{claim[11]} {claim[12]}",
                'insurance_company': claim[13],
                'policy_number': claim[14],
                'trip_number': claim[15],
                'line_items': line_items
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@billing_bp.route('/api/billing/pending-claims', methods=['GET'])
def get_pending_claims():
    """Get all pending claims ready for submission"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.claim_id, c.claim_number, c.service_date,
                c.total_amount, c.claim_status,
                p.first_name, p.last_name,
                pi.insurance_company,
                t.trip_number
            FROM billing.claims c
            INNER JOIN medical.patients p ON c.patient_id = p.patient_id
            INNER JOIN medical.patient_insurance pi ON c.insurance_id = pi.insurance_id
            INNER JOIN operations.trips t ON c.trip_id = t.trip_id
            WHERE c.claim_status IN ('draft', 'pending')
            ORDER BY c.service_date DESC
        """)
        
        claims = []
        for row in cursor.fetchall():
            claims.append({
                'claim_id': str(row[0]),
                'claim_number': row[1],
                'service_date': str(row[2]),
                'amount': float(row[3]),
                'status': row[4],
                'patient_name': f"{row[5]} {row[6]}",
                'insurance': row[7],
                'trip_number': row[8]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(claims),
            'claims': claims
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@billing_bp.route('/api/billing/submit-claim', methods=['POST'])
def submit_claim():
    """Mark claim as submitted (ready for EDI 837 export)"""
    try:
        data = request.json
        claim_id = data.get('claim_id')
        
        if not claim_id:
            return jsonify({
                'success': False,
                'error': 'claim_id is required'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update claim status
        cursor.execute("""
            UPDATE billing.claims
            SET claim_status = 'submitted',
                submission_date = GETDATE()
            WHERE claim_id = ?
        """, (claim_id,))
        
        # Add status history
        cursor.execute("""
            INSERT INTO billing.claim_status_history (
                claim_id, from_status, to_status, notes
            ) VALUES (?, 'draft', 'submitted', 'Claim submitted to clearinghouse')
        """, (claim_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Claim submitted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@billing_bp.route('/api/billing/post-payment', methods=['POST'])
def post_payment():
    """Post payment to a claim"""
    try:
        data = request.json
        
        required_fields = ['claim_id', 'payment_amount', 'payment_date', 'payer_name']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        claim_id = data['claim_id']
        payment_amount = float(data['payment_amount'])
        
        # Generate payment number
        payment_number = f"PMT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        
        # Create payment record
        cursor.execute("""
            INSERT INTO billing.payments (
                claim_id, payment_number, payment_date, payment_amount,
                payment_method, check_number, payer_name, reference_number, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            claim_id, payment_number, data['payment_date'], payment_amount,
            data.get('payment_method', 'eft'),
            data.get('check_number'),
            data['payer_name'],
            data.get('reference_number'),
            data.get('notes')
        ))
        
        # Update claim paid amount
        cursor.execute("""
            UPDATE billing.claims
            SET paid_amount = paid_amount + ?,
                payment_date = ?,
                claim_status = CASE 
                    WHEN (paid_amount + ?) >= total_amount THEN 'paid'
                    ELSE 'partially_paid'
                END
            WHERE claim_id = ?
        """, (payment_amount, data['payment_date'], payment_amount, claim_id))
        
        # Add status history
        cursor.execute("""
            INSERT INTO billing.claim_status_history (
                claim_id, to_status, notes
            ) VALUES (?, 'paid', ?)
        """, (claim_id, f'Payment posted: ${payment_amount}'))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'payment_number': payment_number,
            'message': 'Payment posted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@billing_bp.route('/api/billing/stats', methods=['GET'])
def get_billing_stats():
    """Get billing statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get counts by status
        cursor.execute("""
            SELECT 
                claim_status,
                COUNT(*) as count,
                SUM(total_amount) as total_amount,
                SUM(paid_amount) as paid_amount
            FROM billing.claims
            GROUP BY claim_status
        """)
        
        stats = {}
        for row in cursor.fetchall():
            stats[row[0]] = {
                'count': row[1],
                'total_amount': float(row[2]) if row[2] else 0.0,
                'paid_amount': float(row[3]) if row[3] else 0.0
            }
        
        # Get aging report
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN DATEDIFF(day, service_date, GETDATE()) <= 30 THEN '0-30'
                    WHEN DATEDIFF(day, service_date, GETDATE()) <= 60 THEN '31-60'
                    WHEN DATEDIFF(day, service_date, GETDATE()) <= 90 THEN '61-90'
                    ELSE '90+'
                END as age_bucket,
                COUNT(*) as count,
                SUM(total_amount - paid_amount) as outstanding
            FROM billing.claims
            WHERE claim_status NOT IN ('paid', 'denied')
            GROUP BY 
                CASE 
                    WHEN DATEDIFF(day, service_date, GETDATE()) <= 30 THEN '0-30'
                    WHEN DATEDIFF(day, service_date, GETDATE()) <= 60 THEN '31-60'
                    WHEN DATEDIFF(day, service_date, GETDATE()) <= 90 THEN '61-90'
                    ELSE '90+'
                END
        """)
        
        aging = {}
        for row in cursor.fetchall():
            aging[row[0]] = {
                'count': row[1],
                'outstanding': float(row[2]) if row[2] else 0.0
            }
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats_by_status': stats,
            'aging_report': aging
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
