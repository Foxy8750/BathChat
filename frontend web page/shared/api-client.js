// Shared API Client Library
const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8770';

const API_CONFIG = {
  baseUrl: localStorage.getItem('apiBaseUrl') || DEFAULT_API_BASE_URL,
  userId: localStorage.getItem('userId') || '1'
};

function isValidHttpUrl(value) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function normalizeBaseUrl(value) {
  if (!value || !isValidHttpUrl(value)) return DEFAULT_API_BASE_URL;
  return value.replace(/\/$/, '');
}

function getBaseUrl() {
  return API_CONFIG.baseUrl;
}

function setBaseUrl(url) {
  const normalized = normalizeBaseUrl(url);
  API_CONFIG.baseUrl = normalized;
  localStorage.setItem('apiBaseUrl', normalized);
  const baseUrlDisplay = document.getElementById('baseUrlDisplay');
  if (baseUrlDisplay) baseUrlDisplay.textContent = normalized;
}

function getUserId() {
  return API_CONFIG.userId;
}

function setUserId(id) {
  API_CONFIG.userId = id;
  localStorage.setItem('userId', id);
  const userIdDisplay = document.getElementById('userIdDisplay');
  if (userIdDisplay) userIdDisplay.textContent = id;
}

async function callApi({ method = 'GET', path = '', query = {}, body = null } = {}) {
  let baseUrl = normalizeBaseUrl(getBaseUrl());
  const userId = getUserId();
  
  let url = `${baseUrl}${path}`;
  const queryStr = new URLSearchParams(query).toString();
  if (queryStr) url += `?${queryStr}`;
  
  const options = {
    method,
    mode: 'cors',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
    },
  };
  
  if (body) options.body = JSON.stringify(body);
  
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    console.log('Making request:', { url, options });
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    console.log('Got response with status:', response.status);
    
    let data;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }
    
    const output = {
      success: response.ok,
      status: response.status,
      method,
      path,
      url: url,
      query: queryStr ? Object.fromEntries(new URLSearchParams(queryStr)) : {},
      headers: {
        'X-User-Id': userId,
        'Content-Type': 'application/json',
      },
      response: data,
    };
    
    console.log('Output:', output);
    addOutput(output);
    
    return response.ok ? data : null;
  } catch (error) {
    if (baseUrl !== DEFAULT_API_BASE_URL) {
      // Auto-recover when a stale saved base URL breaks all frontend buttons.
      try {
        console.warn('Primary API URL failed, retrying default URL', { baseUrl, defaultUrl: DEFAULT_API_BASE_URL });
        setBaseUrl(DEFAULT_API_BASE_URL);
        baseUrl = DEFAULT_API_BASE_URL;

        let retryUrl = `${baseUrl}${path}`;
        if (queryStr) retryUrl += `?${queryStr}`;

        const retryController = new AbortController();
        const retryTimeoutId = setTimeout(() => retryController.abort(), 10000);
        const retryResponse = await fetch(retryUrl, {
          ...options,
          signal: retryController.signal,
        });
        clearTimeout(retryTimeoutId);

        let retryData;
        const retryType = retryResponse.headers.get('content-type');
        if (retryType && retryType.includes('application/json')) {
          retryData = await retryResponse.json();
        } else {
          retryData = await retryResponse.text();
        }

        addOutput({
          success: retryResponse.ok,
          status: retryResponse.status,
          method,
          path,
          url: retryUrl,
          note: 'Recovered by switching API base URL to default.',
          response: retryData,
        });

        return retryResponse.ok ? retryData : null;
      } catch (retryError) {
        console.error('Retry fetch error:', retryError);
      }
    }

    console.error('Fetch error:', error);
    addOutput({
      success: false,
      error: error.message,
      stack: error.stack,
      method,
      path,
      url: url,
    });
    return null;
  }
}

function addOutput(obj) {
  const outputDiv = document.getElementById('apiOutput');
  if (!outputDiv) {
    window.console.error('apiOutput div not found!');
    return;
  }
  
  const entry = document.createElement('div');
  entry.className = `output-entry ${obj.success ? 'success' : 'error'}`;
  const time = new Date().toLocaleTimeString();
  
  entry.innerHTML = `
    <div class="output-time">[${time}]</div>
    <pre>${JSON.stringify(obj, null, 2)}</pre>
  `;
  
  outputDiv.appendChild(entry);
  outputDiv.scrollTop = outputDiv.scrollHeight;
}

function clearOutput() {
  const outputDiv = document.getElementById('apiOutput');
  if (outputDiv) outputDiv.innerHTML = '';
}

// Normalize stored values at load time so all pages start with a valid API target.
setBaseUrl(API_CONFIG.baseUrl);
