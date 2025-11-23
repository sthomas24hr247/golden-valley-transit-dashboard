from flask import Blueprint, request, jsonify
import pyodbc
from datetime import datetime, timedelta
import os

insurance_bp = Blueprint('insurance', __name__)

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

def verify_medi_cal(policy_number):
    """
    Verify Medi-Cal eligibility
    In production, this would call the actual Medi-Cal API
    For now, returns mock verification
    """
    # Mock verification logic
    # TODO: Replace with actual Medi-Cal API call
    return {
        'verified': True,
        'active': True,
        'coverage_type': 'Medi-Cal',
        'effective_date': '2024-01-01',
        'expiration_date': '2025-12-31',
        'prior_auth_required': False,
        'copay': 0.00,
        'message': 'Coverage verified and active'
    }

def verify_commercial_insurance(insurance_company, policy_number, group_number=None):
    """
    Verify commercial insurance via Availity
    In production, this would call the Availity API
    For now, returns mock verification
    """
    # Mock verification logic
    # TODO: Replace with actual Availity API call
    return {
        'verified': True,
        'active': True,
        'coverage_type': insurance_company,
        'effective_date': '2024-01-01',
        'expiration_date': '2025-12-31',
        'prior_auth_required': True,
        'copay': 15.00,
        'deductible': 250.00,
        'message': 'Coverage verified - prior authorization may be required'
    }

@insurance_bp.route('/api/insurance/verify', methods=['POST'])
def verify_insurance():
    """Verify patient insurance eligibility"""
    try:
        data = request.json
        
        required_fields = ['patient_id', 'insurance_company', 'policy_number']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Determine verification method based on insurance company
        insurance_company = data['insurance_company'].lower()
        
        if 'medi-cal' in insurance_company or 'medicaid' in insurance_company:
            verification = verify_medi_cal(data['policy_number'])
        else:
            verification = verify_commercial_insurance(
                data['insurance_company'],
                data['policy_number'],
                data.get('group_number')
            )
        
        # Save verification results to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if insurance record exists
        cursor.execute("""
            SELECT insurance_id FROM medical.patient_insurance
            WHERE patient_id = ? AND status = 'active'
        """, (data['patient_id'],))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing record
            cursor.execute("""
                UPDATE medical.patient_insurance
                SET insurance_company = ?,
                    policy_number = ?,
                    group_number = ?,
                    effective_date = ?,
                    expiration_date = ?,
                    prior_authorization_required = ?,
                    copay_amount = ?,
                    deductible_amount = ?,
                    status = ?
                WHERE insurance_id = ?
            """, (
                data['insurance_company'],
                data['policy_number'],
                data.get('group_number', ''),
                verification['effective_date'],
                verification['expiration_date'],
                verification['prior_auth_required'],
                verification.get('copay', 0),
                verification.get('deductible', 0),
                'active' if verification['active'] else 'inactive',
                existing[0]
            ))
        else:
            # Create new record
            cursor.execute("""
                INSERT INTO medical.patient_insurance (
                    patient_id, insurance_company, policy_number, group_number,
                    effective_date, expiration_date, prior_authorization_required,
                    copay_amount, deductible_amount, is_primary, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, GETDATE())
            """, (
                data['patient_id'],
                data['insurance_company'],
                data['policy_number'],
                data.get('group_number', ''),
                verification['effective_date'],
                verification['expiration_date'],
                verification['prior_auth_required'],
                verification.get('copay', 0),
                verification.get('deductible', 0),
                'active' if verification['active'] else 'inactive'
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'verified': verification['verified'],
            'active': verification['active'],
            'message': verification['message'],
            'prior_auth_required': verification['prior_auth_required'],
            'copay': verification.get('copay', 0),
            'coverage_dates': {
                'effective': verification['effective_date'],
                'expiration': verification['expiration_date']
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@insurance_bp.route('/api/insurance/check/<patient_id>', methods=['GET'])
def check_insurance_status(patient_id):
    """Check current insurance verification status for a patient"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                insurance_company,
                policy_number,
                effective_date,
                expiration_date,
                status,
                prior_authorization_required,
                copay_amount
            FROM medical.patient_insurance
            WHERE patient_id = ? AND is_primary = 1
            ORDER BY created_at DESC
        """, (patient_id,))
        
        insurance = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not insurance:
            return jsonify({
                'success': False,
                'message': 'No insurance on file'
            }), 404
        
        # Check if verification is expired (30 days old)
        expiration = insurance[3]
        needs_reverification = expiration < datetime.now().date() if expiration else True
        
        return jsonify({
            'success': True,
            'insurance_company': insurance[0],
            'policy_number': insurance[1],
            'effective_date': str(insurance[2]),
            'expiration_date': str(insurance[3]),
            'status': insurance[4],
            'prior_auth_required': insurance[5],
            'copay': float(insurance[6]) if insurance[6] else 0,
            'needs_reverification': needs_reverification
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
