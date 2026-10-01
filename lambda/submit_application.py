import json
import boto3
import base64
import os
import re
from html import escape as html_escape
from datetime import datetime
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from botocore.client import Config

# Environment variables with sensible defaults
TABLE_NAME = os.environ.get('TABLE_NAME', 'JobApplications')
RESUME_BUCKET = os.environ.get('RESUME_BUCKET') or os.environ.get('BUCKET_NAME') or 'job-portal-receive-resume'
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'recruiter@example.com')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL') or ADMIN_EMAIL
REGION = os.environ.get('AWS_REGION', os.environ.get('REGION', 'eu-north-1'))

# Initialize AWS clients
# Using explicit regional endpoint & SigV4 for S3 ensures presigned URLs work globally in eu-north-1 without signature mismatch
dynamodb = boto3.resource('dynamodb', region_name=REGION)
s3 = boto3.client(
    's3',
    region_name=REGION,
    endpoint_url=f'https://s3.{REGION}.amazonaws.com',
    config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'})
)
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
        download_filename = re.sub(
            r'[^A-Za-z0-9._-]', '_', os.path.basename(str(file_name or 'resume.pdf'))
        ) or 'resume.pdf'

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
        resume_file_bytes = None

        # Process Resume PDF upload if provided
        if file_base64:
            try:
                # Remove data URI prefix if present (e.g., data:application/pdf;base64,...)
                if ',' in file_base64:
                    raw_base64 = file_base64.split(',', 1)[1]
                else:
                    raw_base64 = file_base64

                resume_file_bytes = base64.b64decode(raw_base64)

                # Check max size (approx 5MB limit)
                if len(resume_file_bytes) > 5 * 1024 * 1024:
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
                    Body=resume_file_bytes,
                    ContentType=content_type,
                    ContentDisposition=f'inline; filename="{download_filename}"',
                    Metadata={
                        'candidate-name': name,
                        'candidate-email': email,
                        'applied-role': role,
                        'application-id': application_id
                    }
                )

                # Generate secure presigned URL valid for 24 hours (86400 seconds) for recruiter review
                resume_presigned_url = s3.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': RESUME_BUCKET,
                        'Key': resume_s3_key
                    },
                    ExpiresIn=86400
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

        admin_notification_sent = False
        try:
            email_response = send_recruiter_alert(
                ADMIN_EMAIL, item, resume_presigned_url, resume_file_bytes, download_filename
            )
            admin_notification_sent = True
            print(f"SES admin email sent. Message ID: {email_response.get('MessageId')}")
        except Exception as email_err:
            print(f"SES admin notification warning: {str(email_err)}")
            # Do not fail application submission if SES email fails (e.g. sandbox verification)

        return build_response(201, {
            'success': True,
            'message': 'Application submitted successfully!',
            'application_id': application_id,
            'applied_at': timestamp,
            'admin_notification_sent': admin_notification_sent
        })

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return build_response(500, {
            'error': 'Internal server error processing application',
            'details': str(e)
        })


def send_recruiter_alert(admin_email, item, resume_url, resume_file_bytes, resume_filename):
    """Sends notification to the hiring manager with candidate info and resume attachment/download link"""
    subject = f"🎯 New Application: {item['name']} for {item['role']}"
    safe_resume_url = html_escape(resume_url, quote=True) if resume_url else None
    resume_btn = f"""
      <div style="margin: 22px 0; padding: 14px 18px; background-color: #0f172a; border: 1px solid #334155; border-radius: 8px;">
        <p style="margin: 0 0 10px 0; color: #94a3b8; font-size: 13px;">📎 Candidate Resume Document:</p>
        <a href="{safe_resume_url}" target="_blank" style="background-color: #2563eb; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block; font-size: 14px;">
          View / Download Resume PDF ({html_escape(resume_filename)})
        </a>
      </div>
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

    plain_text = (
        f"New application received from {item['name']} for {item['role']}.\n"
        f"Application ID: {item['application_id']}\n"
        f"Email: {item['email']}\n"
        f"Phone: {item.get('phone') or 'N/A'}\n"
        f"Resume Document: {resume_url or 'None provided'}\n"
    )

    # 1. If physical resume file bytes are present, attempt raw MIME email with PDF attached
    if resume_file_bytes:
        try:
            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = SENDER_EMAIL
            msg['To'] = admin_email

            body_container = MIMEMultipart('alternative')
            body_container.attach(MIMEText(plain_text, 'plain', 'utf-8'))
            body_container.attach(MIMEText(html_body, 'html', 'utf-8'))
            msg.attach(body_container)

            attachment = MIMEApplication(resume_file_bytes, _subtype='pdf')
            attachment.add_header('Content-Disposition', 'attachment', filename=resume_filename)
            msg.attach(attachment)

            return ses.send_raw_email(
                Source=SENDER_EMAIL,
                Destinations=[admin_email],
                RawMessage={'Data': msg.as_bytes()}
            )
        except Exception as raw_err:
            print(f"send_raw_email with attachment failed ({str(raw_err)}). Falling back to standard send_email.")

    # 2. Standard SES send_email fallback (contains the direct presigned download link)
    return ses.send_email(
        Source=SENDER_EMAIL,
        Destination={'ToAddresses': [admin_email]},
        Message={
            'Subject': {'Data': subject, 'Charset': 'UTF-8'},
            'Body': {
                'Text': {'Data': plain_text, 'Charset': 'UTF-8'},
                'Html': {'Data': html_body, 'Charset': 'UTF-8'}
            }
        }
    )
