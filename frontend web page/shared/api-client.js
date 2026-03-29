// Shared API Client Library
const API_CONFIG = {
  baseUrl: localStorage.getItem('apiBaseUrl') || 'http://127.0.0.1:8770',
  userId: localStorage.getItem('userId') || '1'
};

function getBaseUrl() {
  return API_CONFIG.baseUrl;
}

function setBaseUrl(url) {
  API_CONFIG.baseUrl = url;
  localStorage.setItem('apiBaseUrl', url);
  document.getElementById('baseUrlDisplay')?.textContent = url;
}

function getUserId() {
  return API_CONFIG.userId;
}

function setUserId(id) {
  API_CONFIG.userId = id;
  localStorage.setItem('userId', id);
  document.getElementById('userIdDisplay')?.textContent = id;
}

async function callApi({ method = 'GET', path = '', query = {}, body = null } = {}) {
  const baseUrl = getBaseUrl();
  const userId = getUserId();
  
  let url = `${baseUrl}${path}`;
  const queryStr = new URLSearchParams(query).toString();
  if (queryStr) url += `?${queryStr}`;
  
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': userId,
    },
  };
  
  if (body) options.body = JSON.stringify(body);
  
  try {
    console.log('Making request:', { url, options });
    const response = await fetch(url, options);
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
  const console = document.getElementById('apiOutput');
  if (console) console.innerHTML = '';
}
