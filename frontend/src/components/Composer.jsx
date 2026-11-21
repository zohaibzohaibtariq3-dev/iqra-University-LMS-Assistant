import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square, Paperclip, Globe, FileText, X, Loader2 } from "lucide-react";

export default function Composer({
  busy, uploading, docs, webSearch, onToggleSearch, style, onStyle,
  onSend, onStop, onUpload, onRemoveDoc,
}) {
  const [text, setText] = useState("");
  const fileRef = useRef(null);
  const areaRef = useRef(null);

  useEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [text]);

  const submit = () => {
    const t = text.trim();
    if (!t || busy) return;
    onSend(t);
    setText("");
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const pickFile = (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) onUpload(file);
  };

  const pill = (active) =>
    `flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
      active ? "border-brand bg-brand-soft text-brand" : "border-line text-muted hover:text-ink"
    }`;

  return (
    <div className="mx-auto w-full max-w-3xl px-3 pb-3 sm:px-4 sm:pb-4">
      {docs.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {docs.map((d) => (
            <span key={d.id} className="flex items-center gap-1.5 rounded-lg border border-line bg-panel py-1 pl-2 pr-1 text-xs">
              <FileText size={13} className="text-brand" />
              <span className="max-w-[180px] truncate">{d.filename}</span>
              <span className="text-muted">{d.pages} p</span>
              <button onClick={() => onRemoveDoc(d.id)} aria-label={`Remove ${d.filename}`} className="rounded p-0.5 text-muted hover:text-red-500">
                <X size={13} />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="rounded-2xl border border-line bg-panel shadow-sm focus-within:border-brand">
        <textarea
          ref={areaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          maxLength={6000}
          placeholder="Ask a question, paste an assignment, or upload lecture notes..."
          className="block w-full resize-none bg-transparent px-4 pb-1 pt-3.5 text-[15.5px] outline-none placeholder:text-muted"
        />
        <div className="flex items-center gap-2 px-2.5 pb-2.5 pt-1">
          <input ref={fileRef} type="file" accept="application/pdf,.pdf" className="hidden" onChange={pickFile} />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading || busy}
            aria-label="Upload PDF"
            title="Upload a PDF"
            className="grid h-8 w-8 place-items-center rounded-full border border-line text-muted hover:text-ink disabled:opacity-50"
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Paperclip size={16} />}
          </button>

          <button onClick={onToggleSearch} className={pill(webSearch)} aria-pressed={webSearch}>
            <Globe size={14} /> Web search
          </button>

          <div className="hidden items-center rounded-full border border-line p-0.5 text-xs font-medium sm:flex">
            {["short", "detailed"].map((s) => (
              <button
                key={s}
                onClick={() => onStyle(s)}
                aria-pressed={style === s}
                className={`rounded-full px-2.5 py-1 capitalize ${style === s ? "bg-brand text-brand-ink" : "text-muted hover:text-ink"}`}
              >
                {s}
              </button>
            ))}
          </div>

          <div className="flex-1" />
          {busy ? (
            <button onClick={onStop} aria-label="Stop generating" className="grid h-9 w-9 place-items-center rounded-full bg-ink text-bg">
              <Square size={14} fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!text.trim()}
              aria-label="Send message"
              className="grid h-9 w-9 place-items-center rounded-full bg-brand text-brand-ink disabled:opacity-40"
            >
              <ArrowUp size={18} />
            </button>
          )}
        </div>
      </div>
      <p className="mt-2 text-center text-xs text-muted">
        AI can make mistakes. Check important facts with your course material.
      </p>
    </div>
  );
}
