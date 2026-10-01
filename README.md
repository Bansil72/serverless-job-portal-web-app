# 🚀 Serverless Job Application & Resume Portal on AWS

A production-grade, event-driven serverless job application portal built on AWS. Applicants can browse open roles, fill out profile credentials, and upload their resume PDF. The system securely processes the payload with AWS Lambda, stores the file in a private Amazon S3 bucket, indexes candidate records in Amazon DynamoDB, and sends an admin notification via Amazon SES.

The frontend is styled strictly using the **Vercel Geist Design System** with complete **Dark and Light mode** support.

---

## 🌟 Key Highlights

- **Vercel Geist Aesthetic with Dark Mode**: Stark, high-contrast monochrome design with a one-click Sun/Moon theme toggle, automatic OS dark mode detection, and Vercel's signature multi-stop mesh gradient hero.
- **Candidate Submission Pipeline**: Role selector, form validation, and drag-and-drop resume PDF upload (with size/type validation and base64 conversion).
- **Serverless Architecture**:
  - **Amazon API Gateway**: REST API with CORS support (`POST /applications`).
  - **AWS Lambda (Python 3.11)**: Event-driven handler (`submit_application.py`) that processes uploads, updates DynamoDB, and sends SES emails.
  - **Amazon S3**: Private bucket for resume storage with granular metadata, plus static web hosting.
  - **Amazon DynamoDB**: Low-latency NoSQL database for candidate records.
  - **Amazon SES**: Sends new application notifications to the hiring team; applicants do not receive email.
  - **Amazon CloudFront**: Global CDN distribution with HTTPS caching.
- **CI/CD Automation**: Dual GitHub Actions workflows for automated frontend deployment to S3 + CloudFront invalidation, and automated packaging & deployment of AWS Lambda function.
- **Infrastructure as Code (IaC)**: Optional Terraform configuration included to provision resources with a single command.

---

## 🧱 Architecture Diagram

```
                     ┌───────────────────────────┐
                     │         Applicant         │
                     └─────────────┬─────────────┘
                                   │
                                   ▼
                      CloudFront CDN (HTTPS)
                                   │
                                   ▼
                          S3 Static Hosting
                       (index.html, styles.css)
                                   │
                                   ▼ [POST /applications]
                          Amazon API Gateway
                                   │
                                   ▼
                       AWS Lambda (Python 3.11)
                       (submit_application.py)
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
  Amazon DynamoDB              Amazon S3                Amazon SES
 (Candidate Records)       (Private Resume PDF)     (Transactional Emails)
```

---

## 📁 Repository Structure

```
serverless-job-portal/
├── frontend/
│   ├── index.html        # Candidate job application portal (Dark/Light mode)
│   ├── styles.css        # Vercel Geist design system with theme tokens
│   └── app.js            # Candidate submission logic, theme toggle & mock mode
├── lambda/
│   └── submit_application.py   # Processes application, uploads PDF, writes DB, sends SES
├── terraform/
│   ├── main.tf           # S3, DynamoDB, and IAM role provisioning
│   ├── variables.tf      # Configuration variables
│   └── outputs.tf        # Resource IDs and ARNs
├── .github/
│   └── workflows/
│       ├── deploy-frontend.yml # Frontend CI/CD pipeline
│       └── deploy-lambda.yml   # Lambda backend CI/CD pipeline
├── DESIGN.md             # Vercel Geist design system specification
├── .gitignore
└── README.md
```

---

## ⚡ Quick Start (Local Demo Mode)

You can preview and test the complete application right in your browser without deploying to AWS first:

1. Open `frontend/index.html` in your browser.
2. Toggle between **Dark Mode** and **Light Mode** using the icon button in the top navigation.
3. The portal runs in **Local Demo Mode** by default, generating sample tracking IDs and validating PDF uploads.
4. When your AWS backend is deployed, click **Configure Endpoint** in the top bar and paste your API Gateway invoke URL!

---

## 🚀 AWS Cloud Deployment Steps

### 1️⃣ DynamoDB Table
- **Table Name**: `JobApplications`
- **Partition Key**: `application_id` (String)
- **Billing Mode**: On-Demand (Pay per request)

### 2️⃣ S3 Buckets
1. **Resumes Bucket** (e.g., `my-company-resumes-private`):
   - Block all public access: **Enabled**
   - Enable CORS (allow GET, PUT, POST).
2. **Frontend Bucket** (e.g., `my-company-job-portal`):
   - Configured for Static Website Hosting or CloudFront Origin Access Control (OAC).

### 3️⃣ Amazon SES Setup
- Go to SES in `eu-north-1`.
- Verify your sender email address and admin alert email address.

### 4️⃣ Lambda Function (Python 3.11)
- **`SubmitJobApplicationFunction`**:
  - Code: `lambda/submit_application.py`
  - Environment Variables:
    - `TABLE_NAME`: `JobApplications`
    - `RESUME_BUCKET`: `my-company-resumes-private`
    - `ADMIN_EMAIL`: `your-verified-email@example.com`
    - `SENDER_EMAIL`: `your-verified-email@example.com`
  - IAM Role Permissions: S3 (`PutObject`, `GetObject`), DynamoDB (`PutItem`), SES (`SendEmail`), CloudWatch Logs.

### 5️⃣ Amazon API Gateway (REST API)
- Create REST API: `JobPortalAPI`
- Create Resource: `/applications`
  - Method: `POST` → Integrates with `SubmitJobApplicationFunction` (Lambda Proxy enabled)
- Enable **CORS** on `/applications` (Allow headers: `*`, Methods: `POST, OPTIONS`).
- Deploy API to stage `prod` and copy the Invoke URL.

### 6️⃣ Optional: Terraform Deployment
```bash
cd terraform
terraform init
terraform apply -var="admin_email=your-verified-email@example.com"
```

---

## 📜 License

MIT License. Free to use, adapt, and showcase in your DevOps portfolio!
