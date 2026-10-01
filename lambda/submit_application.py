import json
import boto3
import base64
import os
import re
from datetime import datetime
import uuid

# Environment variables with sensible defaults
TABLE_NAME = os.environ.get('TABLE_NAME', 'JobApplications')
RESUME_BUCKET = os.environ.get('RESUME_BUCKET', 'serverless-job-resumes')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'recruiter@example.com')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', ADMIN_EMAIL)
REGION = os.environ.get('AWS_REGION', os.environ.get('REGION', 'eu-north-1'))

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
ses = boto3.client('ses', region_name=REGION)

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
}

def build_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body)
    }

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email)) if email else False

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    # Handle CORS pre-flight
    http_method = event.get('httpMethod', '')
    if http_method == 'OPTIONS':
        return build_response(200, {'message': 'CORS preflight successful'})

    try:
        # Parse payload
        if 'body' in event and event['body']:
            try:
                body = json.loads(event['body'])
            except Exception as e:
                return build_response(400, {'error': 'Invalid JSON in request body'})
        elif isinstance(event, dict) and 'name' in event:
            body = event
        else:
            return build_response(400, {'error': 'Empty or missing request payload'})

        # Extract and validate required fields
        name = (body.get('name') or '').strip()
        email = (body.get('email') or '').strip()
        phone = (body.get('phone') or '').strip()
        role = (body.get('role') or '').strip()
        experience = (body.get('experience') or '').strip()
        portfolio_url = (body.get('portfolio_url') or '').strip()
        cover_letter = (body.get('cover_letter') or '').strip()
        file_base64 = body.get('file_base64')
        file_name = body.get('file_name', 'resume.pdf')

        if not name or not email or not role:
            return build_response(400, {
                'error': 'Missing required fields. Name, email, and role are mandatory.'
            })

        if not is_valid_email(email):
            return build_response(400, {'error': 'Invalid email address format.'})

        application_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + 'Z'
        resume_s3_key = None
        resume_presigned_url = None

        # Process Resume PDF upload if provided
        if file_base64:
            try:
                # Remove data URI prefix if present (e.g., data:application/pdf;base64,...)
                if ',' in file_base64:
                    raw_base64 = file_base64.split(',', 1)[1]
                else:
                    raw_base64 = file_base64

                file_bytes = base64.b64decode(raw_base64)

                # Check max size (approx 5MB limit)
                if len(file_bytes) > 5 * 1024 * 1024:
                    return build_response(400, {'error': 'Resume file size exceeds 5MB limit.'})

                # Sanitize file extension
                clean_ext = 'pdf'
                if '.' in file_name:
                    ext = file_name.rsplit('.', 1)[1].lower()
                    if ext in ['pdf', 'doc', 'docx']:
                        clean_ext = ext

                resume_s3_key = f"resumes/{role.replace(' ', '_')}/{application_id}.{clean_ext}"

                content_type = 'application/pdf' if clean_ext == 'pdf' else 'application/octet-stream'

                s3.put_object(
                    Bucket=RESUME_BUCKET,
                    Key=resume_s3_key,
                    Body=file_bytes,
                    ContentType=content_type,
                    Metadata={
                        'candidate-name': name,
                        'candidate-email': email,
                        'applied-role': role,
                        'application-id': application_id
                    }
                )

                # Generate secure presigned URL valid for 7 days (604800 seconds) for recruiter review
                resume_presigned_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': RESUME_BUCKET, 'Key': resume_s3_key},
                    ExpiresIn=604800
                )
            except Exception as s3_err:
                print(f"Error uploading file to S3: {str(s3_err)}")
                return build_response(500, {'error': 'Failed to process and store resume file.'})

        # Save record in DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        item = {
            'application_id': application_id,
            'name': name,
            'email': email,
            'phone': phone,
            'role': role,
            'experience': experience,
            'portfolio_url': portfolio_url,
            'cover_letter': cover_letter,
            'resume_key': resume_s3_key,
            'resume_filename': file_name if resume_s3_key else None,
            'resume_url': resume_presigned_url,
            'status': 'SUBMITTED',  # SUBMITTED | IN_REVIEW | SHORTLISTED | REJECTED
            'applied_at': timestamp,
            'updated_at': timestamp
        }

        table.put_item(Item=item)
        print(f"Stored application {application_id} in DynamoDB")

        # Notify the admin via SES; email failure does not fail the application submission.
        try:
            send_recruiter_alert(ADMIN_EMAIL, item, resume_presigned_url)
        except Exception as email_err:
            print(f"SES admin notification warning: {str(email_err)}")
            # Do not fail application submission if SES email fails (e.g. sandbox verification)

        return build_response(201, {
            'success': True,
            'message': 'Application submitted successfully!',
            'application_id': application_id,
            'applied_at': timestamp
        })

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return build_response(500, {
            'error': 'Internal server error processing application',
            'details': str(e)
        })


def send_recruiter_alert(admin_email, item, resume_url):
    """Sends notification to the hiring manager with candidate info and resume download link"""
    subject = f"🎯 New Application: {item['name']} for {item['role']}"
    resume_btn = f"""
      <p style="margin-top: 20px;">
        <a href="{resume_url}" style="background-color: #2563eb; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">
          Download Resume PDF
        </a>
      </p>
    """ if resume_url else "<p><em>No resume file was attached.</em></p>"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px; }}
        .card {{ max-width: 620px; margin: 0 auto; background: #1e293b; border-radius: 12px; border: 1px solid #334155; padding: 28px; }}
        h2 {{ margin-top: 0; color: #38bdf8; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        td {{ padding: 10px 0; border-bottom: 1px solid #334155; font-size: 14px; vertical-align: top; }}
        td.label {{ font-weight: 600; color: #94a3b8; width: 130px; }}
        td.val {{ color: #f1f5f9; }}
        .cover {{ background: #0f172a; padding: 14px; border-radius: 8px; margin-top: 8px; white-space: pre-wrap; font-size: 13px; color: #cbd5e1; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h2>New Candidate Application</h2>
        <table>
          <tr><td class="label">Candidate:</td><td class="val"><strong>{item['name']}</strong></td></tr>
          <tr><td class="label">Role:</td><td class="val">{item['role']}</td></tr>
          <tr><td class="label">Email:</td><td class="val"><a href="mailto:{item['email']}" style="color: #38bdf8;">{item['email']}</a></td></tr>
          <tr><td class="label">Phone:</td><td class="val">{item.get('phone') or 'N/A'}</td></tr>
          <tr><td class="label">Experience:</td><td class="val">{item.get('experience') or 'N/A'}</td></tr>
          <tr><td class="label">Portfolio / Web:</td><td class="val"><a href="{item.get('portfolio_url')}" style="color: #38bdf8;">{item.get('portfolio_url') or 'N/A'}</a></td></tr>
          <tr><td class="label">Application ID:</td><td class="val"><code>{item['application_id']}</code></td></tr>
        </table>

        {resume_btn}

        <p style="margin-top: 24px; font-weight: 600; color: #94a3b8;">Pitch / Cover Letter:</p>
        <div class="cover">{item.get('cover_letter') or 'None provided.'}</div>
      </div>
    </body>
    </html>
    """

    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={'ToAddresses': [admin_email]},
        Message={
            'Subject': {'Data': subject, 'Charset': 'UTF-8'},
            'Body': {'Html': {'Data': html_body, 'Charset': 'UTF-8'}}
        }
    )
