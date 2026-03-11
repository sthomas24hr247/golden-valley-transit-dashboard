#!/usr/bin/env python3
"""
NEMTsystem Customer Onboarding Script
--------------------------------------
Provisions a new tenant by:
  1. Creating an organizations.tenants record in credigraph-prod
  2. Generating and storing an API key in organizations.api_keys
  3. Creating a scoped Azure Blob Storage container for tenant documents
  4. Sending a welcome email via Azure Communication Services

Usage:
  python3 onboard_tenant.py \
    --name "Kern Valley Transit" \
    --email "admin@kernvalleytransit.com" \
    --contact "John Smith" \
    --phone "661-555-0100" \
    --plan "standard"

Plans: standard | professional | enterprise | custom
"""

import argparse
import hashlib
import os
import sys
import uuid
import secrets
import string
from datetime import datetime, timezone

from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

# ── DEPENDENCIES ──────────────────────────────────────────────────────────────
try:
    import pyodbc
except ImportError:
    print("ERROR: pyodbc not installed. Run: pip install pyodbc")
    sys.exit(1)

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    print("ERROR: azure-storage-blob not installed. Run: pip install azure-storage-blob")
    sys.exit(1)

try:
    from azure.communication.email import EmailClient
    ACS_AVAILABLE = True
except ImportError:
    ACS_AVAILABLE = False
    print("WARNING: azure-communication-email not installed. Email will be skipped.")


# ── CONFIG ────────────────────────────────────────────────────────────────────
CREDIGRAPH_SERVER   = os.environ.get('CREDIGRAPH_SERVER',   'partnership-sql-server-v2.database.windows.net')
CREDIGRAPH_DATABASE = os.environ.get('CREDIGRAPH_DATABASE', 'credigraph-prod')
CREDIGRAPH_USERNAME = os.environ.get('CREDIGRAPH_USERNAME', 'sqladmin')
CREDIGRAPH_PASSWORD = os.environ.get('CREDIGRAPH_PASSWORD', 'SaQu12025!!!')

STORAGE_ACCOUNT_NAME = os.environ.get('STORAGE_ACCOUNT_NAME', 'nemtsystemdocs')
STORAGE_ACCOUNT_KEY  = os.environ.get('STORAGE_ACCOUNT_KEY',
    '')

ACS_CONNECTION_STRING = os.environ.get('ACS_CONNECTION_STRING',
    '')

ACS_SENDER = os.environ.get('ACS_SENDER', 'onboarding@nemtsystem.com')

PLAN_LIMITS = {
    'standard':     {'providers': 10,  'monthly_rate': 299},
    'professional': {'providers': 50,  'monthly_rate': 799},
    'enterprise':   {'providers': 999, 'monthly_rate': 1999},
    'custom':       {'providers': 999, 'monthly_rate': 0},
}


# ── DATABASE ──────────────────────────────────────────────────────────────────
def get_credigraph():
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={CREDIGRAPH_SERVER};DATABASE={CREDIGRAPH_DATABASE};"
        f"UID={CREDIGRAPH_USERNAME};PWD={CREDIGRAPH_PASSWORD};"
        f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


# ── API KEY GENERATOR ─────────────────────────────────────────────────────────
def generate_api_key(prefix='nemt'):
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(40))
    raw_key  = f"{prefix}_{random_part}"
    key_prefix = raw_key[:12]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_prefix, key_hash


# ── STEP 1: CREATE TENANT ─────────────────────────────────────────────────────
def create_tenant(conn, name, email, contact_name, phone, plan):
    print(f"\n[1/4] Creating tenant record for: {name}")

    tenant_id = str(uuid.uuid4())
    now       = datetime.now(timezone.utc)
    limits    = PLAN_LIMITS.get(plan, PLAN_LIMITS['standard'])

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO organizations.tenants (
            tenant_id, organization_name, tenant_type, subscription_tier,
            subscription_status, max_providers, billing_email,
            primary_contact, primary_phone,
            is_active, created_at, updated_at
        ) VALUES (?, ?, 'nemt_operator', ?, 'active', ?, ?, ?, ?, 1, ?, ?)
    """, (
        tenant_id, name, plan, limits['providers'],
        email, contact_name, phone, now, now
    ))
    conn.commit()
    print(f"    tenant_id : {tenant_id}")
    print(f"    plan      : {plan} (up to {limits['providers']} providers, ${limits['monthly_rate']}/mo)")
    return tenant_id


# ── STEP 2: GENERATE API KEY ──────────────────────────────────────────────────
def create_api_key(conn, tenant_id, name):
    print(f"\n[2/4] Generating API key")

    key_id             = str(uuid.uuid4())
    raw_key, prefix, key_hash = generate_api_key()
    now                = datetime.now(timezone.utc)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO organizations.api_keys (
            key_id, tenant_id, key_name, key_hash, key_prefix,
            permissions, rate_limit_per_hour,
            is_active, created_at
        ) VALUES (?, ?, ?, ?, ?, 'read,write', 1000, 1, ?)
    """, (key_id, tenant_id, f"{name} — Primary Key", key_hash, prefix, now))
    conn.commit()
    print(f"    key_id    : {key_id}")
    print(f"    key_prefix: {prefix}")
    print(f"    api_key   : {raw_key}  <-- share this with the customer")
    return raw_key


# ── STEP 3: CREATE BLOB CONTAINER ─────────────────────────────────────────────
def create_storage_container(tenant_id):
    print(f"\n[3/4] Creating Azure Blob Storage container")

    container_name = tenant_id.lower().replace('-', '')[:63]
    account_url    = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"

    try:
        client = BlobServiceClient(account_url=account_url, credential=STORAGE_ACCOUNT_KEY)
        client.create_container(container_name)
        print(f"    container : {container_name}")
        print(f"    url       : {account_url}/{container_name}")
    except Exception as e:
        if 'ContainerAlreadyExists' in str(e):
            print(f"    container : {container_name} (already exists -- reusing)")
        else:
            print(f"    WARNING: Storage container creation failed: {e}")
            print(f"    Continuing -- container can be created manually later")

    return container_name


# ── STEP 4: SEND WELCOME EMAIL ────────────────────────────────────────────────
def send_welcome_email(email, contact_name, org_name, api_key, plan):
    print(f"\n[4/4] Sending welcome email to {email}")

    if not ACS_AVAILABLE:
        print("    SKIPPED: azure-communication-email not installed")
        return

    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS['standard'])
    rate   = f"${limits['monthly_rate']}/month" if limits['monthly_rate'] > 0 else "Custom pricing"

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#0f172a;padding:32px;text-align:center;">
        <h1 style="color:#14b8a6;margin:0;font-size:24px;">NEMTsystem</h1>
        <p style="color:#94a3b8;margin:8px 0 0;">Broker-Ready. Stay Broker-Ready.</p>
      </div>
      <div style="padding:32px;background:#fff;">
        <p style="font-size:16px;color:#1e293b;">Hi {contact_name},</p>
        <p style="color:#475569;">Welcome to NEMTsystem. Your account for
        <strong>{org_name}</strong> has been provisioned and is ready to use.</p>

        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
                    padding:20px;margin:24px 0;">
          <p style="margin:0 0 12px;font-weight:700;color:#0f172a;">Your Account Details</p>
          <table style="width:100%;border-collapse:collapse;">
            <tr>
              <td style="padding:6px 0;color:#64748b;width:140px;">Organization</td>
              <td style="padding:6px 0;color:#1e293b;font-weight:600;">{org_name}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;color:#64748b;">Plan</td>
              <td style="padding:6px 0;color:#1e293b;font-weight:600;">
                {plan.capitalize()} — {rate}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;color:#64748b;">API Key</td>
              <td style="padding:6px 0;font-family:monospace;font-size:12px;color:#0f172a;
                  background:#f1f5f9;padding:4px 8px;border-radius:4px;">{api_key}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;color:#64748b;">Max Providers</td>
              <td style="padding:6px 0;color:#1e293b;">{limits['providers']}</td>
            </tr>
          </table>
        </div>

        <p style="color:#475569;">Keep your API key secure. Do not share it publicly.
        You can request additional keys from your account manager at any time.</p>

        <div style="text-align:center;margin:32px 0;">
          <a href="https://credentialing.nemtsystem.com/credentialing"
             style="background:#14b8a6;color:#fff;padding:14px 32px;border-radius:8px;
                    text-decoration:none;font-weight:700;font-size:15px;">
            Access Your Dashboard
          </a>
        </div>

        <p style="color:#475569;">The NEMTsystem Team<br>
        <a href="https://nemtsystem.com" style="color:#14b8a6;">nemtsystem.com</a></p>
      </div>
      <div style="background:#f8fafc;padding:16px;text-align:center;">
        <p style="color:#94a3b8;font-size:12px;margin:0;">
          NEMTsystem by My IT Copilot | Bakersfield, CA | HIPAA Compliant
        </p>
      </div>
    </div>
    """

    text_body = (
        f"Hi {contact_name},\n\n"
        f"Welcome to NEMTsystem. Your account for {org_name} has been provisioned.\n\n"
        f"Organization : {org_name}\n"
        f"Plan         : {plan.capitalize()} — {rate}\n"
        f"API Key      : {api_key}\n"
        f"Max Providers: {limits['providers']}\n\n"
        f"Access your dashboard at: https://credentialing.nemtsystem.com\n\n"
        f"Keep your API key secure and do not share it publicly.\n\n"
        f"The NEMTsystem Team\n"
        f"nemtsystem.com"
    )

    try:
        client  = EmailClient.from_connection_string(ACS_CONNECTION_STRING)
        message = {
            "senderAddress": ACS_SENDER,
            "recipients": {"to": [{"address": email, "displayName": contact_name}]},
            "content": {
                "subject": f"Welcome to NEMTsystem — {org_name} Account Ready",
                "plainText": text_body,
                "html": html_body,
            },
        }
        poller   = client.begin_send(message)
        result   = poller.result()
        print(f"    message_id: {result.get('id', 'sent')}")
        print(f"    result    : Email delivered to {email}")
    except Exception as e:
        print(f"    WARNING   : Email failed: {e}")
        print(f"    Continuing -- email can be sent manually")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Onboard a new NEMTsystem tenant')
    parser.add_argument('--name',    required=True,  help='Organization name')
    parser.add_argument('--email',   required=True,  help='Primary admin email')
    parser.add_argument('--contact', required=True,  help='Primary contact name')
    parser.add_argument('--phone',   default='',     help='Primary phone number')
    parser.add_argument('--plan',    default='standard',
                        choices=['standard','professional','enterprise','custom'],
                        help='Subscription plan (default: standard)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Validate inputs without writing to database')
    args = parser.parse_args()

    print("=" * 60)
    print("  NEMTsystem Tenant Onboarding")
    print("=" * 60)
    print(f"  Organization : {args.name}")
    print(f"  Email        : {args.email}")
    print(f"  Contact      : {args.contact}")
    print(f"  Plan         : {args.plan}")

    if args.dry_run:
        print("\n  DRY RUN -- no changes will be made")
        tenant_id          = str(uuid.uuid4())
        raw_key, prefix, _ = generate_api_key()
        container          = tenant_id.lower().replace('-','')[:63]
        print(f"\n  Would create tenant_id  : {tenant_id}")
        print(f"  Would create api_key    : {raw_key}")
        print(f"  Would create key_prefix : {prefix}")
        print(f"  Would create container  : {container}")
        return

    print("\nConnecting to credigraph-prod...")
    try:
        conn = get_credigraph()
        print("Connected.")
    except Exception as e:
        print(f"ERROR: Could not connect to credigraph-prod: {e}")
        sys.exit(1)

    try:
        tenant_id      = create_tenant(conn, args.name, args.email,
                                       args.contact, args.phone, args.plan)
        api_key        = create_api_key(conn, tenant_id, args.name)
        container_name = create_storage_container(tenant_id)
        send_welcome_email(args.email, args.contact, args.name, api_key, args.plan)
    except Exception as e:
        print(f"\nERROR during onboarding: {e}")
        conn.close()
        sys.exit(1)

    conn.close()

    print("\n" + "=" * 60)
    print("  ONBOARDING COMPLETE")
    print("=" * 60)
    print(f"  tenant_id  : {tenant_id}")
    print(f"  api_key    : {api_key}")
    print(f"  container  : {container_name}")
    print(f"  dashboard  : https://credentialing.nemtsystem.com")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Share the API key securely with the customer")
    print("  2. Schedule onboarding call via Microsoft Bookings")
    print("  3. Add their drivers and vehicles to the credentialing module")
    print()


if __name__ == '__main__':
    main()
