// Candidate Application Portal Script 
const STORAGE_KEY_API = 'JOB_PORTAL_API_ENDPOINT';
const STORAGE_KEY_MOCK_APPS = 'JOB_PORTAL_LOCAL_APPLICATIONS';
const STORAGE_KEY_THEME = 'theme';

const API_GATEWAY_URL = 'https://cc0b3vt8qg.execute-api.eu-north-1.amazonaws.com/prod'; // Paste the API Gateway stage invoke URL here.
let apiUrl = localStorage.getItem(STORAGE_KEY_API) || API_GATEWAY_URL;

const apiEndpointDisplay = document.getElementById('apiEndpointDisplay');
const changeApiBtn = document.getElementById('changeApiBtn');
const alertBox = document.getElementById('alertBox');
const form = document.getElementById('applicationForm');
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('resumeFileInput');
const filePreview = document.getElementById('filePreview');
const previewFileName = document.getElementById('previewFileName');
const previewFileSize = document.getElementById('previewFileSize');
const removeFileBtn = document.getElementById('removeFileBtn');
const submitBtn = document.getElementById('submitBtn');
const btnSpinner = document.getElementById('btnSpinner');
const btnText = document.getElementById('btnText');
const successModal = document.getElementById('successModal');
const modalMessage = document.getElementById('modalMessage');
const modalCloseBtn = document.getElementById('modalCloseBtn');

// Theme toggle elements
const themeToggleBtn = document.getElementById('themeToggleBtn');
const sunIcon = document.getElementById('sunIcon');
const moonIcon = document.getElementById('moonIcon');

let selectedFile = null;
let selectedFileBase64 = null;

// ==========================================================================
// Theme Management (Dark & Light Mode)
// ==========================================================================
function getCurrentTheme() {
  return document.documentElement.getAttribute('data-theme') || 'dark';
}

function updateThemeIcons(theme) {
  if (theme === 'dark') {
    sunIcon.style.display = 'block';
    moonIcon.style.display = 'none';
  } else {
    sunIcon.style.display = 'none';
    moonIcon.style.display = 'block';
  }
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(STORAGE_KEY_THEME, theme);
  updateThemeIcons(theme);
}

if (themeToggleBtn) {
  themeToggleBtn.addEventListener('click', () => {
    const current = getCurrentTheme();
    const target = current === 'dark' ? 'light' : 'dark';
    setTheme(target);
  });
}

// Initial theme icon setup
updateThemeIcons(getCurrentTheme());

// Listen for OS theme preference changes if user hasn't explicitly set a preference
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
  if (!localStorage.getItem(STORAGE_KEY_THEME)) {
    setTheme(e.matches ? 'dark' : 'light');
  }
});

// ==========================================================================
// API Endpoint Configuration (Configurable via localStorage or runtime)
// ==========================================================================
function updateEndpointDisplay() {
  if (!apiEndpointDisplay) return;
  if (apiUrl && apiUrl.trim() !== '') {
    apiEndpointDisplay.textContent = apiUrl;
    apiEndpointDisplay.style.color = '#0070f3';
  } else {
    apiEndpointDisplay.textContent = 'Local Demo / Mock Mode (Active)';
    apiEndpointDisplay.style.color = 'var(--body)';
  }
}

if (changeApiBtn) {
  changeApiBtn.addEventListener('click', () => {
    const current = apiUrl || 'https://xxxxxx.execute-api.eu-north-1.amazonaws.com/prod';
    const input = prompt('Enter your AWS API Gateway Endpoint URL (or leave blank for Local Demo Mode):', current);
    if (input !== null) {
      apiUrl = input.trim();
      if (apiUrl) {
        localStorage.setItem(STORAGE_KEY_API, apiUrl);
      } else {
        localStorage.removeItem(STORAGE_KEY_API);
      }
      updateEndpointDisplay();
      showAlert('API Endpoint updated successfully', 'success');
    }
  });
}

function showAlert(message, type = 'error') {
  alertBox.textContent = message;
  alertBox.className = `alert-banner ${type}`;
  alertBox.style.display = 'block';
  setTimeout(() => {
    alertBox.style.display = 'none';
  }, 5000);
}

// ==========================================================================
// File Dropzone Handling
// ==========================================================================
dropzone.addEventListener('click', () => fileInput.click());

['dragenter', 'dragover'].forEach(eventName => {
  dropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.add('dragover');
  });
});

['dragleave', 'drop'].forEach(eventName => {
  dropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('dragover');
  });
});

dropzone.addEventListener('drop', (e) => {
  const files = e.dataTransfer.files;
  if (files && files.length > 0) {
    handleFileSelection(files[0]);
  }
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files && e.target.files.length > 0) {
    handleFileSelection(e.target.files[0]);
  }
});

function handleFileSelection(file) {
  const isValidType = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
  if (!isValidType) {
    showAlert('Please upload a valid PDF document.', 'error');
    return;
  }

  const maxBytes = 5 * 1024 * 1024;
  if (file.size > maxBytes) {
    showAlert('Resume file exceeds maximum allowed size of 5MB.', 'error');
    return;
  }

  selectedFile = file;
  previewFileName.textContent = file.name;
  previewFileSize.textContent = (file.size / 1024).toFixed(1) + ' KB';

  const reader = new FileReader();
  reader.onload = () => {
    selectedFileBase64 = reader.result;
    dropzone.style.display = 'none';
    filePreview.style.display = 'flex';
  };
  reader.readAsDataURL(file);
}

removeFileBtn.addEventListener('click', () => {
  selectedFile = null;
  selectedFileBase64 = null;
  fileInput.value = '';
  filePreview.style.display = 'none';
  dropzone.style.display = 'block';
});

// ==========================================================================
// Form Submission Handler
// ==========================================================================
form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const role = document.getElementById('role').value;
  const experience = document.getElementById('experience').value;
  const name = document.getElementById('name').value.trim();
  const email = document.getElementById('email').value.trim();
  const phone = document.getElementById('phone').value.trim();
  const portfolio_url = document.getElementById('portfolio_url').value.trim();
  const cover_letter = document.getElementById('cover_letter').value.trim();

  if (!role || !experience || !name || !email) {
    showAlert('Please complete all mandatory fields.', 'error');
    return;
  }

  const payload = {
    role,
    experience,
    name,
    email,
    phone,
    portfolio_url,
    cover_letter,
    file_base64: selectedFileBase64,
    file_name: selectedFile ? selectedFile.name : null
  };

  setLoading(true);

  try {
    if (apiUrl && apiUrl.trim() !== '') {
      // Live AWS API Gateway Call
      const endpoint = apiUrl.replace(/\/+$/, '') + '/applications';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to submit application to AWS Lambda.');
      }

      showSuccess(data.application_id || 'AWS-' + Math.random().toString(36).substring(2, 9).toUpperCase());
    } else {
      // Mock Demo Mode for Instant Testing
      await new Promise(r => setTimeout(r, 600));
      const mockId = 'app-' + Math.random().toString(36).substring(2, 10);
      const newMockItem = {
        application_id: mockId,
        name,
        email,
        phone: phone || '+1 (555) 019-2834',
        role,
        experience,
        portfolio_url: portfolio_url || 'https://github.com/developer',
        cover_letter: cover_letter || 'Experienced in cloud-native microservices, AWS CDK, and zero-downtime deployments.',
        resume_filename: selectedFile ? selectedFile.name : 'resume_sample.pdf',
        resume_url: selectedFileBase64 || '#',
        status: 'SUBMITTED',
        applied_at: new Date().toISOString()
      };

      const existing = JSON.parse(localStorage.getItem(STORAGE_KEY_MOCK_APPS) || '[]');
      existing.unshift(newMockItem);
      localStorage.setItem(STORAGE_KEY_MOCK_APPS, JSON.stringify(existing));

      showSuccess(mockId);
    }
  } catch (err) {
    console.error('Submission error:', err);
    showAlert(err.message || 'Error occurred while contacting backend API.', 'error');
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  btnSpinner.style.display = isLoading ? 'inline-block' : 'none';
  btnText.textContent = isLoading ? 'Processing...' : 'Submit Application';
}

function showSuccess(appId) {
  modalMessage.textContent = `Your application was submitted successfully. Reference ID: ${appId}`;
  successModal.style.display = 'flex';
  form.reset();
  removeFileBtn.click();
}

modalCloseBtn.addEventListener('click', () => {
  successModal.style.display = 'none';
});

updateEndpointDisplay();
