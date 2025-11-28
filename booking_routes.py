def send_welcome_email(email, patient_name, username, temp_password):
    """Send welcome email to new patient"""
    try:
        api_key = os.environ.get('SENDGRID_API_KEY')
        from_email = os.environ.get('SENDGRID_FROM_EMAIL', 'info@goldenvalleytransit.com')
        
        if not api_key:
            print("SendGrid API key not configured")
            return False
        
        message = Mail(
            from_email=from_email,
            to_emails=email,
            subject='Welcome to Golden Valley Transit!',
            html_content=f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1 style="color: #667eea;">Welcome to Golden Valley Transit!</h1>
                    <p>Dear {patient_name},</p>
                    <p>Your patient account has been created successfully.</p>
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3>Your Login Credentials:</h3>
                        <p><strong>Username:</strong> {username}</p>
                        <p><strong>Temporary Password:</strong> {temp_password}</p>
                    </div>
                    <p>Please log in to your patient portal to:</p>
                    <ul>
                        <li>Schedule transportation</li>
                        <li>View upcoming appointments</li>
                        <li>Update your information</li>
                    </ul>
                    <p><a href="https://gvt-dashboard.azurewebsites.net/patient-portal" 
                          style="background: #667eea; color: white; padding: 12px 24px; 
                                 text-decoration: none; border-radius: 8px; display: inline-block;">
                        Access Patient Portal
                    </a></p>
                    <p style="margin-top: 30px; color: #666;">
                        Questions? Call us at (661) 555-0100
                    </p>
                    <p>Golden Valley Transit<br>
                    <em>Caring Medical Transportation for the Central Valley</em></p>
                </div>
            '''
        )
        
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        print(f"Email sent successfully: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False