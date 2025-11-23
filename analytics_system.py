from flask import Blueprint, request, jsonify
import pyodbc
from datetime import datetime, timedelta
import os

analytics_bp = Blueprint('analytics', __name__)

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

@analytics_bp.route('/api/analytics/dashboard', methods=['GET'])
def get_dashboard_metrics():
    """Get overview dashboard metrics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total trips
        cursor.execute("""
            SELECT COUNT(*) FROM operations.trips
        """)
        total_trips = cursor.fetchone()[0]
        
        # Trips today
        cursor.execute("""
            SELECT COUNT(*) FROM operations.trips
            WHERE CAST(scheduled_pickup_time AS DATE) = CAST(GETDATE() AS DATE)
        """)
        trips_today = cursor.fetchone()[0]
        
        # Total patients
        cursor.execute("""
            SELECT COUNT(*) FROM medical.patients
            WHERE status = 'active'
        """)
        total_patients = cursor.fetchone()[0]
        
        # Total drivers
        cursor.execute("""
            SELECT COUNT(*) FROM operations.drivers d
            INNER JOIN security.users u ON d.user_id = u.user_id
            WHERE u.status = 'active'
        """)
        total_drivers = cursor.fetchone()[0]
        
        # Available drivers now
        cursor.execute("""
            SELECT COUNT(*) FROM operations.drivers d
            INNER JOIN security.users u ON d.user_id = u.user_id
            WHERE d.current_status = 'available'
              AND u.status = 'active'
              AND CAST(GETDATE() AS TIME) BETWEEN d.shift_start AND d.shift_end
        """)
        available_drivers = cursor.fetchone()[0]
        
        # Revenue metrics
        cursor.execute("""
            SELECT 
                SUM(total_amount) as total_billed,
                SUM(paid_amount) as total_paid,
                SUM(total_amount - paid_amount) as outstanding
            FROM billing.claims
        """)
        revenue = cursor.fetchone()
        
        # Claims by status
        cursor.execute("""
            SELECT 
                claim_status,
                COUNT(*) as count
            FROM billing.claims
            GROUP BY claim_status
        """)
        claims_by_status = {}
        for row in cursor.fetchall():
            claims_by_status[row[0]] = row[1]
        
        # Trips by status
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM operations.trips
            GROUP BY status
        """)
        trips_by_status = {}
        for row in cursor.fetchall():
            trips_by_status[row[0]] = row[1]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'overview': {
                'total_trips': total_trips,
                'trips_today': trips_today,
                'total_patients': total_patients,
                'total_drivers': total_drivers,
                'available_drivers': available_drivers
            },
            'revenue': {
                'total_billed': float(revenue[0]) if revenue[0] else 0.0,
                'total_paid': float(revenue[1]) if revenue[1] else 0.0,
                'outstanding': float(revenue[2]) if revenue[2] else 0.0
            },
            'claims_by_status': claims_by_status,
            'trips_by_status': trips_by_status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/api/analytics/revenue', methods=['GET'])
def get_revenue_analytics():
    """Get detailed revenue analytics"""
    try:
        # Get date range from query params (default to last 30 days)
        days = int(request.args.get('days', 30))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Revenue by payer type
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN pi.insurance_company LIKE '%medi-cal%' OR pi.insurance_company LIKE '%medicaid%' THEN 'Medi-Cal'
                    WHEN pi.insurance_company LIKE '%medicare%' THEN 'Medicare'
                    ELSE 'Commercial'
                END as payer_type,
                COUNT(c.claim_id) as claim_count,
                SUM(c.total_amount) as total_billed,
                SUM(c.paid_amount) as total_paid
            FROM billing.claims c
            INNER JOIN medical.patient_insurance pi ON c.insurance_id = pi.insurance_id
            WHERE c.service_date >= DATEADD(day, -?, GETDATE())
            GROUP BY 
                CASE 
                    WHEN pi.insurance_company LIKE '%medi-cal%' OR pi.insurance_company LIKE '%medicaid%' THEN 'Medi-Cal'
                    WHEN pi.insurance_company LIKE '%medicare%' THEN 'Medicare'
                    ELSE 'Commercial'
                END
        """, (days,))
        
        by_payer = []
        for row in cursor.fetchall():
            by_payer.append({
                'payer_type': row[0],
                'claim_count': row[1],
                'total_billed': float(row[2]) if row[2] else 0.0,
                'total_paid': float(row[3]) if row[3] else 0.0
            })
        
        # Daily revenue trend
        cursor.execute("""
            SELECT 
                CAST(service_date AS DATE) as date,
                COUNT(*) as claims,
                SUM(total_amount) as billed,
                SUM(paid_amount) as paid
            FROM billing.claims
            WHERE service_date >= DATEADD(day, -?, GETDATE())
            GROUP BY CAST(service_date AS DATE)
            ORDER BY date DESC
        """, (days,))
        
        daily_trend = []
        for row in cursor.fetchall():
            daily_trend.append({
                'date': str(row[0]),
                'claims': row[1],
                'billed': float(row[2]) if row[2] else 0.0,
                'paid': float(row[3]) if row[3] else 0.0
            })
        
        # Collection rate
        cursor.execute("""
            SELECT 
                SUM(total_amount) as total_billed,
                SUM(paid_amount) as total_collected
            FROM billing.claims
            WHERE service_date >= DATEADD(day, -?, GETDATE())
        """, (days,))
        
        collection = cursor.fetchone()
        collection_rate = 0.0
        if collection and collection[0] and collection[0] > 0:
            collection_rate = (float(collection[1] or 0) / float(collection[0])) * 100
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'period_days': days,
            'by_payer_type': by_payer,
            'daily_trend': daily_trend,
            'collection_rate': round(collection_rate, 2)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/api/analytics/operations', methods=['GET'])
def get_operational_metrics():
    """Get operational performance metrics"""
    try:
        days = int(request.args.get('days', 30))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Trip volume by day
        cursor.execute("""
            SELECT 
                CAST(scheduled_pickup_time AS DATE) as date,
                COUNT(*) as trip_count,
                COUNT(CASE WHEN driver_id IS NOT NULL THEN 1 END) as assigned_count
            FROM operations.trips
            WHERE scheduled_pickup_time >= DATEADD(day, -?, GETDATE())
            GROUP BY CAST(scheduled_pickup_time AS DATE)
            ORDER BY date DESC
        """, (days,))
        
        trip_volume = []
        for row in cursor.fetchall():
            trip_volume.append({
                'date': str(row[0]),
                'total_trips': row[1],
                'assigned_trips': row[2],
                'unassigned_trips': row[1] - row[2]
            })
        
        # Trips by status
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM operations.trips
            WHERE scheduled_pickup_time >= DATEADD(day, -?, GETDATE())
            GROUP BY status
        """, (days,))
        
        by_status = {}
        for row in cursor.fetchall():
            by_status[row[0]] = row[1]
        
        # Driver utilization
        cursor.execute("""
            SELECT 
                d.driver_id,
                u.first_name + ' ' + u.last_name as driver_name,
                COUNT(t.trip_id) as trips_completed,
                d.current_status
            FROM operations.drivers d
            INNER JOIN security.users u ON d.user_id = u.user_id
            LEFT JOIN operations.trips t ON d.driver_id = t.driver_id 
                AND t.scheduled_pickup_time >= DATEADD(day, -?, GETDATE())
            WHERE u.status = 'active'
            GROUP BY d.driver_id, u.first_name, u.last_name, d.current_status
            ORDER BY trips_completed DESC
        """, (days,))
        
        driver_stats = []
        for row in cursor.fetchall():
            driver_stats.append({
                'driver_id': str(row[0]),
                'driver_name': row[1],
                'trips_completed': row[2],
                'status': row[3]
            })
        
        # Peak hours analysis
        cursor.execute("""
            SELECT 
                DATEPART(hour, scheduled_pickup_time) as hour,
                COUNT(*) as trip_count
            FROM operations.trips
            WHERE scheduled_pickup_time >= DATEADD(day, -?, GETDATE())
            GROUP BY DATEPART(hour, scheduled_pickup_time)
            ORDER BY hour
        """, (days,))
        
        peak_hours = []
        for row in cursor.fetchall():
            peak_hours.append({
                'hour': row[0],
                'trip_count': row[1]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'period_days': days,
            'trip_volume': trip_volume,
            'trips_by_status': by_status,
            'driver_utilization': driver_stats,
            'peak_hours': peak_hours
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/api/analytics/patients', methods=['GET'])
def get_patient_analytics():
    """Get patient demographics and activity"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total active patients
        cursor.execute("""
            SELECT COUNT(*) FROM medical.patients WHERE status = 'active'
        """)
        total_patients = cursor.fetchone()[0]
        
        # Patients by insurance type
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN pi.insurance_company LIKE '%medi-cal%' OR pi.insurance_company LIKE '%medicaid%' THEN 'Medi-Cal'
                    WHEN pi.insurance_company LIKE '%medicare%' THEN 'Medicare'
                    ELSE 'Commercial'
                END as insurance_type,
                COUNT(DISTINCT p.patient_id) as patient_count
            FROM medical.patients p
            LEFT JOIN medical.patient_insurance pi ON p.patient_id = pi.patient_id 
                AND pi.is_primary = 1 AND pi.status = 'active'
            WHERE p.status = 'active'
            GROUP BY 
                CASE 
                    WHEN pi.insurance_company LIKE '%medi-cal%' OR pi.insurance_company LIKE '%medicaid%' THEN 'Medi-Cal'
                    WHEN pi.insurance_company LIKE '%medicare%' THEN 'Medicare'
                    ELSE 'Commercial'
                END
        """)
        
        by_insurance = {}
        for row in cursor.fetchall():
            if row[0]:  # Only include if insurance_type is not None
                by_insurance[row[0]] = row[1]
        
        # Top patients by trip count
        cursor.execute("""
            SELECT TOP 10
                p.patient_id,
                p.first_name + ' ' + p.last_name as patient_name,
                COUNT(t.trip_id) as trip_count,
                MAX(t.scheduled_pickup_time) as last_trip_date
            FROM medical.patients p
            LEFT JOIN operations.trips t ON p.patient_id = t.patient_id
            WHERE p.status = 'active'
            GROUP BY p.patient_id, p.first_name, p.last_name
            ORDER BY trip_count DESC
        """)
        
        top_patients = []
        for row in cursor.fetchall():
            top_patients.append({
                'patient_id': str(row[0]),
                'patient_name': row[1],
                'trip_count': row[2],
                'last_trip_date': str(row[3]) if row[3] else None
            })
        
        # New patients by month
        cursor.execute("""
            SELECT 
                YEAR(created_at) as year,
                MONTH(created_at) as month,
                COUNT(*) as new_patients
            FROM medical.patients
            WHERE created_at >= DATEADD(month, -6, GETDATE())
            GROUP BY YEAR(created_at), MONTH(created_at)
            ORDER BY year DESC, month DESC
        """)
        
        new_patients = []
        for row in cursor.fetchall():
            new_patients.append({
                'year': row[0],
                'month': row[1],
                'count': row[2]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'total_patients': total_patients,
            'by_insurance_type': by_insurance,
            'top_patients': top_patients,
            'new_patients_trend': new_patients
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@analytics_bp.route('/api/analytics/export/csv', methods=['GET'])
def export_csv():
    """Export analytics data as CSV"""
    try:
        report_type = request.args.get('type', 'trips')
        days = int(request.args.get('days', 30))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if report_type == 'trips':
            cursor.execute("""
                SELECT 
                    t.trip_number,
                    t.scheduled_pickup_time,
                    p.first_name + ' ' + p.last_name as patient_name,
                    t.pickup_address,
                    t.destination_address,
                    t.status,
                    ISNULL(d.first_name + ' ' + d.last_name, 'Unassigned') as driver_name
                FROM operations.trips t
                INNER JOIN medical.patients p ON t.patient_id = p.patient_id
                LEFT JOIN operations.drivers dr ON t.driver_id = dr.driver_id
                LEFT JOIN security.users d ON dr.user_id = d.user_id
                WHERE t.scheduled_pickup_time >= DATEADD(day, -?, GETDATE())
                ORDER BY t.scheduled_pickup_time DESC
            """, (days,))
            
            # Build CSV
            csv_data = "Trip Number,Scheduled Time,Patient Name,Pickup Address,Dropoff Address,Status,Driver\n"
            for row in cursor.fetchall():
                csv_data += f'"{row[0]}","{row[1]}","{row[2]}","{row[3]}","{row[4]}","{row[5]}","{row[6]}"\n'
            
        elif report_type == 'revenue':
            cursor.execute("""
                SELECT 
                    c.claim_number,
                    c.service_date,
                    p.first_name + ' ' + p.last_name as patient_name,
                    pi.insurance_company,
                    c.total_amount,
                    c.paid_amount,
                    c.claim_status
                FROM billing.claims c
                INNER JOIN medical.patients p ON c.patient_id = p.patient_id
                INNER JOIN medical.patient_insurance pi ON c.insurance_id = pi.insurance_id
                WHERE c.service_date >= DATEADD(day, -?, GETDATE())
                ORDER BY c.service_date DESC
            """, (days,))
            
            csv_data = "Claim Number,Service Date,Patient Name,Insurance,Amount Billed,Amount Paid,Status\n"
            for row in cursor.fetchall():
                csv_data += f'"{row[0]}","{row[1]}","{row[2]}","{row[3]}",{row[4]},{row[5]},"{row[6]}"\n'
        
        cursor.close()
        conn.close()
        
        return csv_data, 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename={report_type}_report.csv'
        }
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
