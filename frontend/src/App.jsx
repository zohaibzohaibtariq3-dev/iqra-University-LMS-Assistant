import { useCallback, useEffect, useRef, useState } from "react";
import { Menu, GraduationCap, FileText, ListChecks, ScrollText, AlertCircle, X } from "lucide-react";
import Sidebar from "./components/Sidebar.jsx";
import Message from "./components/Message.jsx";
import Composer from "./components/Composer.jsx";
import { api, streamChat } from "./api.js";

const SUGGESTIONS = [
  { title: "Explain recursion", text: "Explain recursion in simple words with a Python example." },
  { title: "Assignment answer", text: "Assignment question: Explain the OSI model with its seven layers. Write a detailed answer." },
  { title: "Roman Urdu", text: "Process aur thread mein kya farq hai? Roman Urdu mein samjhao." },
  { title: "Latest information", text: "What are the latest developments in artificial intelligence this month?" },
];

const PDF_ACTIONS = [
  { label: "Summarize", icon: FileText, text: "Summarize the uploaded PDF with key points." },
  { label: "10 MCQs", icon: ListChecks, text: "Generate 10 MCQs from the uploaded PDF with an answer key." },
  { label: "Exam questions", icon: ScrollText, text: "Write 5 likely exam questions with short answers from the uploaded PDF." },
];

export default function App() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
  );
  const [chats, setChats] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [docs, setDocs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [webSearch, setWebSearch] = useState(true);
  const [style, setStyle] = useState("detailed");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const abortRef = useRef(null);
  const scrollRef = useRef(null);
  const stickRef = useRef(true);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  const refreshChats = useCallback(() => api.listChats().then(setChats).catch(() => {}), []);
  useEffect(() => { refreshChats(); }, [refreshChats]);

  // keep the view pinned to the newest text unless the user scrolls up
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [messages, status]);

  const onScroll = () => {
    const el = scrollRef.current;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  };

  const newChat = () => {
    abortRef.current?.abort();
    setActiveId(null); setMessages([]); setDocs([]); setError(""); setNotice(""); setSidebarOpen(false);
  };

  const openChat = async (id) => {
    if (busy) return;
    try {
      const data = await api.getChat(id);
      setActiveId(id); setMessages(data.messages); setDocs(data.documents);
      setError(""); setNotice(""); setSidebarOpen(false); stickRef.current = true;
    } catch (e) { setError(e.message); }
  };

  const deleteChat = async (id) => {
    if (!window.confirm("Delete this chat and its uploaded PDFs?")) return;
    try {
      await api.deleteChat(id);
      if (id === activeId) newChat();
      refreshChats();
    } catch (e) { setError(e.message); }
  };

  const runStream = async ({ message = "", regenerate = false }) => {
    if (busy) return;
    setError(""); setNotice(""); setBusy(true); setStatus("Thinking");
    stickRef.current = true;
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setMessages((prev) => {
      const base = regenerate ? prev.slice(0, -1) : [...prev, { role: "user", content: message }];
      return [...base, { role: "assistant", content: "", sources: [], streaming: true }];
    });
    const patchLast = (fn) =>
      setMessages((prev) => { const c = [...prev]; c[c.length - 1] = fn(c[c.length - 1]); return c; });

    try {
      await streamChat(
        { chat_id: activeId, message, web_search: webSearch, style, regenerate },
        ctrl.signal,
        (ev) => {
          if (ev.type === "meta") setActiveId(ev.chat_id);
          else if (ev.type === "status") setStatus(ev.data);
          else if (ev.type === "notice") setNotice(ev.data);
          else if (ev.type === "sources") patchLast((m) => ({ ...m, sources: ev.data }));
          else if (ev.type === "token") patchLast((m) => ({ ...m, content: m.content + ev.data }));
          else if (ev.type === "error") setError(ev.data);
        }
      );
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message || "Something went wrong.");
    } finally {
      setMessages((prev) => {
        const c = prev.map((m, i) => (i === prev.length - 1 ? { ...m, streaming: false } : m));
        const last = c[c.length - 1];
        return last && last.role === "assistant" && !last.content.trim() ? c.slice(0, -1) : c;
      });
      setBusy(false); setStatus(""); abortRef.current = null;
      refreshChats();
    }
  };

  const send = (text) => runStream({ message: text });
  const regenerate = () => runStream({ regenerate: true });
  const stop = () => abortRef.current?.abort();

  const uploadPdf = async (file) => {
    setError(""); setUploading(true);
    try {
      let id = activeId;
      if (!id) {
        id = (await api.createChat()).id;
        setActiveId(id);
      }
      await api.uploadPdf(id, file);
      setDocs((await api.getChat(id)).documents);
      refreshChats();
    } catch (e) { setError(e.message); }
    finally { setUploading(false); }
  };

  const removeDoc = async (docId) => {
    try { await api.deleteDocument(docId); setDocs((d) => d.filter((x) => x.id !== docId)); }
    catch (e) { setError(e.message); }
  };

  const empty = messages.length === 0;
  const lastAssistantIndex = messages.map((m) => m.role).lastIndexOf("assistant");

  return (
    <div className="flex h-full">
      <Sidebar
        chats={chats} activeId={activeId} onNew={newChat} onOpen={openChat} onDelete={deleteChat}
        theme={theme} onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
        open={sidebarOpen} onClose={() => setSidebarOpen(false)}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-line bg-panel px-3 py-2.5 md:hidden">
          <button onClick={() => setSidebarOpen(true)} aria-label="Open sidebar" className="rounded-lg p-2 hover:bg-bg">
            <Menu size={20} />
          </button>
          <span className="text-sm font-semibold">Iqra LMS Assistant</span>
        </header>

        <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-6">
            {empty ? (
              <div className="flex min-h-[55vh] flex-col items-center justify-center text-center">
                <div className="mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-brand text-brand-ink">
                  <GraduationCap size={30} />
                </div>
                <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">What are you studying today?</h1>
                <p className="mt-3 max-w-md text-muted">
                  Ask any academic question, solve an assignment, get code explained, or upload lecture notes as a PDF.
                </p>
                <div className="mt-8 grid w-full max-w-xl gap-2.5 sm:grid-cols-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s.title}
                      onClick={() => send(s.text)}
                      className="rounded-xl border border-line bg-panel p-3.5 text-left hover:border-brand"
                    >
                      <div className="text-sm font-semibold">{s.title}</div>
                      <div className="mt-1 line-clamp-2 text-sm text-muted">{s.text}</div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-7">
                {messages.map((m, i) => (
                  <Message
                    key={i} message={m} status={status}
                    canRegenerate={!busy && i === lastAssistantIndex}
                    onRegenerate={regenerate}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="mx-auto w-full max-w-3xl px-3 sm:px-4">
          {notice && (
            <div className="mb-2 flex items-start gap-2 rounded-xl border border-line bg-panel px-3 py-2 text-sm text-muted">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span className="flex-1">{notice}</span>
              <button onClick={() => setNotice("")} aria-label="Dismiss"><X size={15} /></button>
            </div>
          )}
          {error && (
            <div role="alert" className="mb-2 flex items-start gap-2 rounded-xl border border-red-400 bg-panel px-3 py-2 text-sm text-red-500">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span className="flex-1">{error}</span>
              <button onClick={() => setError("")} aria-label="Dismiss"><X size={15} /></button>
            </div>
          )}
          {docs.length > 0 && !busy && (
            <div className="mb-2 flex flex-wrap gap-2">
              {PDF_ACTIONS.map(({ label, icon: Icon, text }) => (
                <button
                  key={label}
                  onClick={() => send(text)}
                  className="flex items-center gap-1.5 rounded-full border border-line bg-panel px-3 py-1.5 text-xs font-medium hover:border-brand"
                >
                  <Icon size={14} className="text-brand" /> {label}
                </button>
              ))}
            </div>
          )}
        </div>

        <Composer
          busy={busy} uploading={uploading} docs={docs}
          webSearch={webSearch} onToggleSearch={() => setWebSearch((v) => !v)}
          style={style} onStyle={setStyle}
          onSend={send} onStop={stop} onUpload={uploadPdf} onRemoveDoc={removeDoc}
        />
      </main>
    </div>
  );
}
