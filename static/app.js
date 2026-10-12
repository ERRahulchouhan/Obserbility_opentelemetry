const form = document.querySelector("#chat-form");
const input = document.querySelector("#prompt-input");
const sendButton = document.querySelector("#send-button");
const messages = document.querySelector("#messages");
const traceList = document.querySelector("#trace-list");
const traceCount = document.querySelector("#trace-count");
const traceStatus = document.querySelector("#trace-status");
const toast = document.querySelector("#toast");
let requestCount = 0;
let toastTimer;

function addMessage(role, text) {
  const message = document.createElement("article");
  message.className = `message message-${role}`;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "YOU" : "MOCK LLM";

  const content = document.createElement("p");
  content.className = "message-content";
  content.textContent = text;

  message.append(label, content);
  messages.append(message);
  message.scrollIntoView({ behavior: "smooth", block: "nearest" });
  return message;
}

function showToast(text) {
  toast.textContent = text;
  toast.classList.add("toast-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("toast-visible"), 3200);
}

function addTrace(prompt, traceId) {
  document.querySelector("#empty-traces")?.remove();

  const item = document.createElement("article");
  item.className = "trace-item";
  const promptLabel = document.createElement("p");
  promptLabel.className = "trace-prompt";
  promptLabel.textContent = prompt;

  const meta = document.createElement("div");
  meta.className = "trace-meta";
  const id = document.createElement("code");
  id.textContent = traceId.slice(0, 16);

  const link = document.createElement("a");
  link.className = "trace-open";
  link.href = `http://${window.location.hostname}:16686/trace/${encodeURIComponent(traceId)}`;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = "Open trace ↗";

  meta.append(id, link);
  item.append(promptLabel, meta);
  traceList.prepend(item);

  requestCount += 1;
  traceCount.textContent = String(requestCount);
  traceStatus.textContent = "TRACE CREATED";
  traceStatus.classList.add("trace-ready");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const prompt = input.value.trim();
  if (!prompt) return;

  addMessage("user", prompt);
  const reply = addMessage("assistant", "Generating a simulated response...");
  reply.classList.add("message-pending");
  sendButton.disabled = true;
  input.disabled = true;
  traceStatus.textContent = "RECORDING";
  traceStatus.classList.remove("trace-ready");

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Request failed.");

    reply.querySelector(".message-content").textContent = result.answer;
    addTrace(prompt, result.trace_id);
    input.value = "";
  } catch (error) {
    reply.querySelector(".message-content").textContent = "The request could not be completed.";
    traceStatus.textContent = "REQUEST FAILED";
    showToast(error.message);
  } finally {
    reply.classList.remove("message-pending");
    sendButton.disabled = false;
    input.disabled = false;
    input.focus();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
