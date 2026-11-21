const BASE = "/api";

async function request(path, options) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    throw new Error("Cannot reach the backend. Make sure it is running on port 8000.");
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.status === 204 ? null : res.json();
}

async function readError(res) {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail[0]?.msg || "Invalid request.";
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status}).`;
}

export const api = {
  listChats: () => request("/chats"),
  createChat: () => request("/chats", { method: "POST" }),
  getChat: (id) => request(`/chats/${id}`),
  deleteChat: (id) => request(`/chats/${id}`, { method: "DELETE" }),
  uploadPdf: (chatId, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/chats/${chatId}/documents`, { method: "POST", body: form });
  },
  deleteDocument: (id) => request(`/documents/${id}`, { method: "DELETE" }),
};

/** POST to the streaming endpoint and call onEvent for every JSON line. */
export async function streamChat(payload, signal, onEvent) {
  let res;
  try {
    res = await fetch(`${BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new Error("Cannot reach the backend. Make sure it is running on port 8000.");
  }
  if (!res.ok) throw new Error(await readError(res));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const l of lines) if (l.trim()) onEvent(JSON.parse(l));
  }
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
}
