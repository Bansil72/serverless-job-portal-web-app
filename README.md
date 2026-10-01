# 🚀 Serverless Job Application & Resume Portal on AWS

A production-grade, event-driven serverless job application portal built on AWS. Applicants can browse open roles, fill out profile credentials, and upload their resume PDF. The system securely processes the payload with AWS Lambda, stores the file in a private Amazon S3 bucket, indexes candidate records in Amazon DynamoDB, and sends an admin notification via Amazon SES.

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
4. To connect the live backend, set `API_GATEWAY_URL` in `frontend/app.js` to your API Gateway stage invoke URL. The frontend adds `/applications` when it submits the form. An existing `JOB_PORTAL_API_ENDPOINT` value in browser local storage overrides this setting; remove that key to use the configured value.

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
  - Create it in `eu-north-1`. Use a dedicated bucket for the frontend because the deploy workflow syncs with `--delete`.
  - For the CloudFront setup below, keep **Block all public access** enabled. CloudFront OAC grants access without making the bucket public.
  - In **Properties → Static website hosting**, choose **Enable**, select **Host a static website**, and set `index.html` as the index document. The Terraform configuration also sets `index.html` as the error document. This creates an S3 website endpoint, but the recommended CloudFront OAC setup below uses the bucket's regular S3 origin instead; do not make this bucket public just to use CloudFront.

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

#### Connect the frontend

In `frontend/app.js`, set `API_GATEWAY_URL` to the stage invoke URL, for example:

```js
const API_GATEWAY_URL = 'https://abc123.execute-api.eu-north-1.amazonaws.com/prod';
```

Use the base stage URL only; do not add `/applications`, because the form submission code appends that path. The URL currently in `app.js` is an example/configured endpoint and should match your deployed API. The browser uses a saved `JOB_PORTAL_API_ENDPOINT` value first if one exists, so remove that local-storage key when switching to the source setting.

### 6️⃣ Host the frontend with S3 and CloudFront

The frontend workflow uploads the contents of `frontend/` to an S3 bucket. Create the bucket first, then create the CloudFront distribution manually:

1. In **CloudFront → Distributions → Create distribution**, choose the frontend S3 bucket as the origin. Select the bucket's regional S3 origin, not the S3 static website endpoint.
2. Create or select an **Origin Access Control (OAC)**, choose **Sign requests**, and allow the CloudFront wizard to update the S3 bucket policy. This keeps direct public access blocked while allowing CloudFront to read the site.
3. Set **Default root object** to `index.html`.
4. For the default behavior, redirect HTTP to HTTPS, allow `GET` and `HEAD`, and use the managed `CachingOptimized` cache policy.
5. Create the distribution and wait for its status to become **Deployed**. Open the distribution domain name to verify the site. The first deployment can also be started from **Actions → Deploy Frontend to S3 & CloudFront → Run workflow** after adding the GitHub secrets below.
6. Copy the distribution ID into the `CLOUDFRONT_DISTRIBUTION_ID` GitHub secret so subsequent frontend deployments invalidate cached files.

The S3 **static website endpoint** is a separate HTTP origin that does not support OAC. If you deliberately use that endpoint as a CloudFront custom origin, the bucket website must be publicly readable; this is less secure and is not the recommended configuration above. For a custom domain, add the domain to the distribution and attach an ACM certificate issued in `us-east-1` (CloudFront's certificate requirement); the AWS resources and workflows for this project otherwise use `eu-north-1`.

### 7️⃣ GitHub Actions secrets

In your GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**. Add these secrets for the deployment workflows:

| Secret name | Required | Value |
| --- | --- | --- |
| `AWS_ACCESS_KEY_ID` | Yes | Access key ID for an IAM user/role allowed to deploy this app. |
| `AWS_SECRET_ACCESS_KEY` | Yes | Matching secret access key. Do not commit or paste credentials into source files. |
| `AWS_REGION` | No | Set to `eu-north-1`; the workflows default to this if the secret is absent. |
| `S3_FRONTEND_BUCKET` | Yes | Frontend bucket name only, without `s3://`. |
| `CLOUDFRONT_DISTRIBUTION_ID` | No | CloudFront distribution ID. If omitted, the frontend upload runs but cache invalidation is skipped. |
| `LAMBDA_SUBMIT_FUNCTION_NAME` | No | Existing Lambda function name; defaults to `SubmitJobApplicationFunction`. |

The AWS identity needs permission to sync objects in the frontend bucket, update the Lambda function, and create CloudFront invalidations when the distribution ID is configured. Use least-privilege IAM permissions. Once these secrets are set, pushes to `main` that change `frontend/` or `lambda/` trigger their respective workflows.

### 8️⃣ Optional: Terraform Deployment
```bash
cd terraform
terraform init
terraform apply -var="admin_email=your-verified-email@example.com"
```

---

## 📜 License

MIT License. Free to use, adapt, and showcase in your DevOps portfolio!
