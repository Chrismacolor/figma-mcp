// UI iframe — handles HTTP polling to server and bridges messages to code.ts

const serverUrlInput = document.getElementById("serverUrl") as HTMLInputElement;
const authTokenInput = document.getElementById("authToken") as HTMLInputElement;
const connectBtn = document.getElementById("connectBtn") as HTMLButtonElement;
const statusDot = document.getElementById("statusDot") as HTMLSpanElement;
const statusText = document.getElementById("statusText") as HTMLSpanElement;
const logDiv = document.getElementById("log") as HTMLDivElement;

let connected = false;
let pollTimer: ReturnType<typeof setInterval> | null = null;

function log(msg: string) {
  const entry = document.createElement("div");
  entry.className = "log-entry";
  const time = new Date().toLocaleTimeString();
  entry.textContent = `[${time}] ${msg}`;
  logDiv.appendChild(entry);
  logDiv.scrollTop = logDiv.scrollHeight;
}

function setStatus(state: "off" | "on" | "error", text: string) {
  statusDot.className = `dot ${state}`;
  statusText.textContent = text;
}

function getHeaders(): Record<string, string> {
  return {
    Authorization: `Bearer ${authTokenInput.value.trim()}`,
    "Content-Type": "application/json",
  };
}

function baseUrl(): string {
  return serverUrlInput.value.trim().replace(/\/$/, "");
}

async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch(`${baseUrl()}/health`);
    return resp.ok;
  } catch {
    return false;
  }
}

async function pollJobs() {
  try {
    const resp = await fetch(`${baseUrl()}/api/jobs/next`, {
      headers: getHeaders(),
    });
    if (resp.status === 401) {
      log("Auth failed (401) — check token");
      setStatus("error", "Auth failed (401)");
      disconnect();
      return;
    }
    if (resp.status === 204) return; // no pending jobs
    if (!resp.ok) return;

    const job = await resp.json();
    log(`Job received: ${job.id} (${job.ops.length} ops)`);
    parent.postMessage(
      { pluginMessage: { type: "execute-ops", jobId: job.id, ops: job.ops } },
      "*"
    );
  } catch (err: any) {
    log(`Poll error: ${err.message}`);
  }
}

async function pollReadRequests() {
  try {
    const resp = await fetch(`${baseUrl()}/api/read-request`, {
      headers: getHeaders(),
    });
    if (resp.status === 204 || !resp.ok) return;

    const req = await resp.json();
    log(`Read request: ${req.id} (depth=${req.depth})`);
    parent.postMessage(
      {
        pluginMessage: {
          type: "read-node-tree",
          requestId: req.id,
          depth: req.depth,
        },
      },
      "*"
    );
  } catch (err: any) {
    log(`Read poll error: ${err.message}`);
  }
}

async function poll() {
  await Promise.all([pollJobs(), pollReadRequests()]);
}

function connect() {
  if (!authTokenInput.value.trim()) {
    log("Enter auth token first");
    return;
  }
  checkHealth().then((ok) => {
    if (!ok) {
      log("Cannot reach server — is it running?");
      setStatus("error", "Server unreachable");
      return;
    }
    connected = true;
    connectBtn.textContent = "Disconnect";
    connectBtn.className = "connected";
    setStatus("on", "Connected — polling");
    log("Connected to server");
    poll(); // immediate first poll
    pollTimer = setInterval(poll, 1500);
  });
}

function disconnect() {
  connected = false;
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  connectBtn.textContent = "Connect";
  connectBtn.className = "";
  setStatus("off", "Disconnected");
  log("Disconnected");
}

connectBtn.addEventListener("click", () => {
  if (connected) {
    disconnect();
  } else {
    connect();
  }
});

// Messages from code.ts (Figma sandbox)
window.onmessage = async (event: MessageEvent) => {
  const msg = event.data?.pluginMessage;
  if (!msg) return;

  if (msg.type === "job-complete") {
    log(`Job complete: ${msg.jobId}`);
    try {
      await fetch(`${baseUrl()}/api/jobs/${msg.jobId}/complete`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ result: msg.result }),
      });
    } catch (err: any) {
      log(`Failed to report completion: ${err.message}`);
    }
  } else if (msg.type === "job-error") {
    log(`Job error: ${msg.error}`);
    try {
      await fetch(`${baseUrl()}/api/jobs/${msg.jobId}/error`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ error: msg.error }),
      });
    } catch (err: any) {
      log(`Failed to report error: ${err.message}`);
    }
  } else if (msg.type === "read-response") {
    log(`Read response for ${msg.requestId}`);
    try {
      await fetch(
        `${baseUrl()}/api/read-request/${msg.requestId}/response`,
        {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({ data: msg.data }),
        }
      );
    } catch (err: any) {
      log(`Failed to send read response: ${err.message}`);
    }
  }
};
