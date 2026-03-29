const output = document.getElementById("output");

function getBaseUrl() {
  return document.getElementById("baseUrl").value.trim().replace(/\/+$/, "");
}

function getUserId() {
  return document.getElementById("userId").value.trim();
}

function writeOutput(title, payload) {
  const stamp = new Date().toLocaleTimeString();
  const formatted = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  output.textContent = `[${stamp}] ${title}\n${formatted}`;
}

function splitList(raw) {
  if (!raw) {
    return [];
  }
  return raw.split(",").map((v) => v.trim()).filter(Boolean);
}

async function callApi({ method, path, body, query, auth = true }) {
  const userId = getUserId();
  const url = new URL(`${getBaseUrl()}${path}`);

  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value).trim() !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }

  const headers = {};
  if (auth) {
    if (!userId) {
      throw new Error("X-User-Id is required for this endpoint.");
    }
    headers["X-User-Id"] = userId;
  }

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url.toString(), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  let data;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = text;
  }

  if (!res.ok) {
    throw new Error(JSON.stringify({ status: res.status, data }, null, 2));
  }

  return { status: res.status, data };
}

function bindForm(id, handler) {
  const form = document.getElementById(id);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await handler(new FormData(form));
      writeOutput(`${id} OK`, result);
    } catch (error) {
      writeOutput(`${id} ERROR`, String(error.message || error));
    }
  });
}

bindForm("registerForm", async (fd) => {
  return callApi({
    method: "POST",
    path: "/auth/register",
    auth: false,
    body: {
      email: fd.get("email"),
      name: fd.get("name"),
      password: fd.get("password"),
    },
  });
});

bindForm("loginForm", async (fd) => {
  return callApi({
    method: "POST",
    path: "/auth/login",
    auth: false,
    body: {
      email: fd.get("email"),
      password: fd.get("password"),
    },
  });
});

bindForm("meForm", async () => callApi({ method: "GET", path: "/auth/me" }));

bindForm("profileUpsertForm", async (fd) => {
  return callApi({
    method: "POST",
    path: "/profiles/me",
    body: {
      name: fd.get("name") || null,
      interests: splitList(fd.get("interests")),
      course: fd.get("course") || null,
      accommodation: fd.get("accommodation") || null,
      ethnicity: fd.get("ethnicity") || null,
      gender: fd.get("gender") || null,
      spoken_language: fd.get("spoken_language") || null,
      societies: splitList(fd.get("societies")),
      goals: fd.get("goals") || null,
      bio: fd.get("bio") || null,
    },
  });
});

bindForm("profileGetForm", async () => callApi({ method: "GET", path: "/profiles/me" }));
bindForm("leaderboardForm", async () => callApi({ method: "GET", path: "/leaderboard/top-exp" }));

bindForm("discoveryMatchForm", async (fd) => {
  const candidateId = fd.get("candidate_id");
  return callApi({ method: "POST", path: `/discovery/match/${candidateId}` });
});

bindForm("discoveryMatchesForm", async () => callApi({ method: "GET", path: "/discovery/matches" }));

bindForm("connectForm", async (fd) => {
  const candidateId = fd.get("candidate_id");
  return callApi({ method: "POST", path: `/connections/${candidateId}` });
});

bindForm("connectionsListForm", async () => callApi({ method: "GET", path: "/connections" }));

bindForm("chatSendForm", async (fd) => {
  const connectionUserId = fd.get("connection_user_id");
  return callApi({
    method: "POST",
    path: `/connections/${connectionUserId}/chat`,
    body: {
      content: fd.get("content"),
      message_type: fd.get("message_type") || "text",
    },
  });
});

bindForm("chatGetForm", async (fd) => {
  const connectionUserId = fd.get("connection_user_id");
  return callApi({ method: "GET", path: `/connections/${connectionUserId}/chat` });
});

bindForm("messageXpForm", async (fd) => {
  return callApi({
    method: "POST",
    path: "/messages/send",
    query: {
      recipient_id: fd.get("recipient_id"),
      content: fd.get("content"),
    },
  });
});

bindForm("friendRequestForm", async (fd) => {
  const receiverId = fd.get("receiver_id");
  return callApi({ method: "POST", path: `/friends/request/${receiverId}` });
});

bindForm("friendAcceptForm", async (fd) => {
  const requestId = fd.get("request_id");
  return callApi({ method: "POST", path: `/friends/request/${requestId}/accept` });
});

document.getElementById("clearOutput").addEventListener("click", () => {
  output.textContent = "";
});

writeOutput(
  "Ready",
  {
    note: "Set Base URL and X-User-Id, then submit any card.",
    endpointsCovered: 15,
  }
);
