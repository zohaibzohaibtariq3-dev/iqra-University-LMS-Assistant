import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Check, Copy, RefreshCw, GraduationCap, Globe } from "lucide-react";
import { copyText } from "../api.js";

function CodeBlock({ children }) {
  const ref = useRef(null);
  const [copied, setCopied] = useState(false);
  const lang = children?.props?.className?.match(/language-([\w+-]+)/)?.[1] || "code";

  const copy = async () => {
    await copyText(ref.current?.innerText || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="codeblock">
      <div className="codehead">
        <span>{lang}</span>
        <button onClick={copy} aria-label="Copy code">
          {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre ref={ref}>{children}</pre>
    </div>
  );
}

function hostname(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function Sources({ sources }) {
  if (!sources?.length) return null;
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted">
        <Globe size={14} /> Sources
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {sources.map((s, i) => (
          <a
            key={s.url}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex gap-2.5 rounded-xl border border-line bg-panel p-2.5 text-sm hover:border-brand"
          >
            <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-brand-soft text-xs font-semibold text-brand">
              {i + 1}
            </span>
            <span className="min-w-0">
              <span className="line-clamp-2 font-medium leading-snug">{s.title}</span>
              <span className="block truncate text-xs text-muted">{hostname(s.url)}</span>
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}

export default function Message({ message, status, canRegenerate, onRegenerate }) {
  const [copied, setCopied] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-brand-soft px-4 py-2.5 text-[15.5px] leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  const waiting = message.streaming && !message.content;

  const copy = async () => {
    await copyText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex gap-3">
      <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand text-brand-ink">
        <GraduationCap size={17} />
      </div>
      <div className="min-w-0 flex-1">
        {waiting ? (
          <div className="flex items-center gap-3 py-2 text-sm text-muted">
            <span className="dots flex gap-1"><span /><span /><span /></span>
            {status || "Thinking"}
          </div>
        ) : (
          <div className={`md ${message.streaming ? "cursor" : ""}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
              components={{
                pre: CodeBlock,
                a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {!message.streaming && <Sources sources={message.sources} />}

        {!message.streaming && message.content && (
          <div className="mt-2 flex items-center gap-1 text-muted">
            <button onClick={copy} className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs hover:bg-panel hover:text-ink">
              {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy"}
            </button>
            {canRegenerate && (
              <button onClick={onRegenerate} className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs hover:bg-panel hover:text-ink">
                <RefreshCw size={14} /> Regenerate
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
