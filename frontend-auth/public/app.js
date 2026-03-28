const API_URL_KEY = "bathchat_api_base_url";
const SESSION_KEY = "bathchat_session";

const apiConfigForm = document.querySelector("#api-config-form");
const apiUrlInput = document.querySelector("#apiBaseUrl");
const signupForm = document.querySelector("#signup-form");
const loginForm = document.querySelector("#login-form");
const messageCard = document.querySelector("#message-card");
const sessionText = document.querySelector("#session-text");
const tabSignup = document.querySelector("#tab-signup");
const tabLogin = document.querySelector("#tab-login");

function readApiBaseUrl() {
  return localStorage.getItem(API_URL_KEY) || "http://127.0.0.1:8001";
}

function setApiBaseUrl(url) {
  const normalized = url.trim().replace(/\/$/, "");
  localStorage.setItem(API_URL_KEY, normalized);
  return normalized;
}

function getSession() {
  const raw = localStorage.getItem(SESSION_KEY);
  return raw ? JSON.parse(raw) : null;
}

function setSession(payload) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
  refreshSessionUI();
}

function refreshSessionUI() {
  const session = getSession();
  if (!session) {
    sessionText.textContent = "Not signed in";
    return;
  }

  sessionText.textContent = `Signed in as ${session.email} (userId: ${session.userId})`;
}

function setMessage(message, type = "success") {
  messageCard.classList.remove("is-error", "is-success");
  messageCard.classList.add(type === "error" ? "is-error" : "is-success");
  messageCard.textContent = message;
}

async function callApi(path, options) {
  const baseUrl = readApiBaseUrl();
  const response = await fetch(`${baseUrl}${path}`, options);

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const detail = data?.detail || `Request failed with status ${response.status}`;
    throw new Error(detail);
  }

  return data;
}

function setTab(mode) {
  const signUpActive = mode === "signup";
  tabSignup.classList.toggle("is-active", signUpActive);
  tabLogin.classList.toggle("is-active", !signUpActive);
  signupForm.classList.toggle("hidden", !signUpActive);
  loginForm.classList.toggle("hidden", signUpActive);
}

function parseUserIdFromToken(token) {
  const match = /^user-(\d+)$/.exec(token || "");
  if (!match) {
    return null;
  }
  return Number.parseInt(match[1], 10);
}

apiConfigForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const normalized = setApiBaseUrl(apiUrlInput.value);
  setMessage(`Saved backend URL: ${normalized}`);
});

signupForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(signupForm);
  const payload = {
    name: String(formData.get("name") || "").trim(),
    email: String(formData.get("email") || "").trim().toLowerCase(),
    password: String(formData.get("password") || ""),
  };

  try {
    const user = await callApi("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    setSession({ userId: user.id, email: user.email, token: null });
    setMessage(`Account created. Your user ID is ${user.id}. You can now log in.`);
    setTab("login");
  } catch (error) {
    setMessage(error.message, "error");
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(loginForm);
  const email = String(formData.get("email") || "").trim().toLowerCase();
  const password = String(formData.get("password") || "");

  try {
    const tokenData = await callApi("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const userId = parseUserIdFromToken(tokenData.access_token);
    if (!userId) {
      throw new Error("Could not parse user ID from login token.");
    }

    const user = await callApi("/auth/me", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": String(userId),
      },
    });

    setSession({ userId, email: user.email, token: tokenData.access_token });
    setMessage(`Logged in as ${user.name}. Use X-User-Id: ${userId} for protected API calls.`);
  } catch (error) {
    setMessage(error.message, "error");
  }
});

tabSignup.addEventListener("click", () => setTab("signup"));
tabLogin.addEventListener("click", () => setTab("login"));

apiUrlInput.value = readApiBaseUrl();
refreshSessionUI();
setMessage("Set your backend URL, then create an account or log in.");
