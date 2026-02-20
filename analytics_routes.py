# analytics_routes.py
# Add this file to your gvt-github repo
# Then import and register in dashboard_app.py
#
# This module provides API endpoints that query the
# analytics-warehouse-prod database on partnership-sql-server-v2
# to serve data to the analytics dashboard.

import pyodbc
from flask import Blueprint, jsonify
from datetime import datetime, timedelta

analytics_bp = Blueprint('analytics_warehouse', __name__)

def get_analytics_connection():
    """Connect to the analytics warehouse on partnership-sql-server-v2"""
    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=partnership-sql-server-v2.database.windows.net;"
        "DATABASE=analytics-warehouse-prod-2025-8-24-9-20;"
        "UID=sqladmin;"
        "PWD=SaQu12022!;"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def run_query(query, params=None):
    """Execute a query and return list of dicts"""
    try:
        conn = get_analytics_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        results = [dict(zip(columns, row)) for row in rows]
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Analytics DB error: {e}")
        return None


@analytics_bp.route('/api/analytics/summary')
def analytics_summary():
    """Main analytics summary endpoint - powers the dashboard KPI cards and charts"""
    try:
        conn = get_analytics_connection()
        cursor = conn.cursor()

        # KPI Cards - MTD metrics
        cursor.execute("""
            SELECT 
                ISNULL(SUM(total_trips_completed), 0) AS total_trips_mtd,
                ISNULL(SUM(total_revenue), 0) AS revenue_mtd,
                ISNULL(SUM(unique_patients), 0) AS active_patients,
                ISNULL(AVG(on_time_rate), 0) AS avg_on_time_rate,
                ISNULL(SUM(total_trips_completed), 0) AS completed_trips,
                ISNULL(SUM(total_trips_cancelled), 0) AS cancelled_trips,
                ISNULL(AVG(average_trip_duration_minutes), 0) AS avg_duration
            FROM operational.daily_trip_metrics
            WHERE metric_date >= DATEADD(DAY, -30, CAST(GETUTCDATE() AS DATE))
        """)
        row = cursor.fetchone()
        kpi = {
            "total_trips_mtd": int(row[0]) if row else 0,
            "revenue_mtd": float(row[1]) if row else 0,
            "active_patients": int(row[2]) if row else 0,
            "on_time_rate": round(float(row[3]), 1) if row else 0,
            "completed_trips": int(row[4]) if row else 0,
            "cancelled_trips": int(row[5]) if row else 0,
            "avg_duration": round(float(row[6]), 1) if row else 0
        }

        # Fleet metrics
        cursor.execute("""
            SELECT TOP 1
                ISNULL(vehicles_in_service, 0) AS active_vehicles,
                ISNULL(total_vehicles, 0) AS total_vehicles
            FROM performance.fleet_performance_summary
            ORDER BY summary_date DESC
        """)
        fleet_row = cursor.fetchone()
        kpi["active_vehicles"] = int(fleet_row[0]) if fleet_row else 0
        kpi["total_vehicles"] = int(fleet_row[1]) if fleet_row else 0

        # Workforce metrics
        cursor.execute("""
            SELECT TOP 1
                ISNULL(active_drivers, 0) AS total_drivers,
                ISNULL(active_drivers, 0) AS active_drivers
            FROM performance.workforce_metrics
            ORDER BY metric_date DESC
        """)
        wf_row = cursor.fetchone()
        kpi["total_drivers"] = int(wf_row[0]) if wf_row else 0
        if kpi["total_drivers"] > 0:
            kpi["avg_trips_per_driver"] = round(kpi["completed_trips"] / kpi["total_drivers"], 1)
        else:
            kpi["avg_trips_per_driver"] = 0

        # Revenue Trend (last 30 days, grouped by date)
        cursor.execute("""
            SELECT 
                metric_date,
                ISNULL(SUM(total_revenue), 0) AS daily_revenue
            FROM operational.daily_trip_metrics
            WHERE metric_date >= DATEADD(DAY, -30, CAST(GETUTCDATE() AS DATE))
            GROUP BY metric_date
            ORDER BY metric_date
        """)
        revenue_trend = []
        for r in cursor.fetchall():
            revenue_trend.append({
                "date": r[0].strftime('%Y-%m-%d') if r[0] else '',
                "revenue": round(float(r[1]), 2)
            })

        # Recent Activity (last 14 days, grouped by date)
        cursor.execute("""
            SELECT TOP 14
                metric_date,
                ISNULL(SUM(total_trips_completed), 0) AS trips,
                ISNULL(SUM(total_revenue), 0) AS revenue,
                ISNULL(AVG(on_time_rate), 0) AS on_time_pct
            FROM operational.daily_trip_metrics
            GROUP BY metric_date
            ORDER BY metric_date DESC
        """)
        recent_activity = []
        for r in cursor.fetchall():
            trips = int(r[1])
            recent_activity.append({
                "date": r[0].strftime('%Y-%m-%d') if r[0] else '',
                "trips": trips,
                "revenue": round(float(r[2]), 2),
                "on_time_pct": round(float(r[3]), 1),
                "status": "On Track" if float(r[3]) >= 90 else "Needs Review"
            })

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "kpi": kpi,
            "revenue_trend": revenue_trend,
            "recent_activity": recent_activity
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@analytics_bp.route('/api/analytics/revenue-trend')
def revenue_trend():
    """Revenue trend for configurable time ranges"""
    from flask import request
    days = int(request.args.get('days', 30))
    results = run_query("""
        SELECT metric_date, ISNULL(SUM(total_revenue), 0) AS revenue
        FROM operational.daily_trip_metrics
        WHERE metric_date >= DATEADD(DAY, ?, CAST(GETUTCDATE() AS DATE))
        GROUP BY metric_date ORDER BY metric_date
    """, (-days,))
    if results is None:
        return jsonify({"success": False, "error": "Database error"}), 500
    for r in results:
        if r.get('metric_date'):
            r['metric_date'] = r['metric_date'].strftime('%Y-%m-%d')
        r['revenue'] = round(float(r.get('revenue', 0)), 2)
    return jsonify({"success": True, "data": results})


@analytics_bp.route('/api/analytics/health')
def analytics_health():
    """Health check for analytics database connection"""
    try:
        conn = get_analytics_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS ok")
        cursor.close()
        conn.close()
        return jsonify({"success": True, "database": "analytics-warehouse-prod", "status": "connected"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
