import { GraduationCap, Plus, MessageSquare, Trash2, Sun, Moon, X } from "lucide-react";

export default function Sidebar({ chats, activeId, onNew, onOpen, onDelete, theme, onToggleTheme, open, onClose }) {
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={onClose} />}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-line bg-panel transition-transform duration-200 md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-4 pb-3 pt-4">
          <div className="flex items-center gap-2.5">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-brand-ink">
              <GraduationCap size={20} />
            </div>
            <div className="leading-tight">
              <div className="text-[15px] font-semibold">Iqra LMS Assistant</div>
              <div className="text-xs text-muted">Study help, any subject</div>
            </div>
          </div>
          <button className="rounded-lg p-1.5 text-muted hover:bg-bg md:hidden" onClick={onClose} aria-label="Close sidebar">
            <X size={18} />
          </button>
        </div>

        <div className="px-3 pb-2">
          <button
            onClick={onNew}
            className="flex w-full items-center gap-2 rounded-xl border border-line px-3 py-2.5 text-sm font-medium hover:bg-bg"
          >
            <Plus size={16} /> New chat
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-1">
          {chats.length === 0 && (
            <p className="px-2 py-6 text-center text-sm text-muted">Your chats will appear here.</p>
          )}
          {chats.map((c) => (
            <div
              key={c.id}
              className={`group mb-0.5 flex items-center rounded-lg ${
                c.id === activeId ? "bg-brand-soft" : "hover:bg-bg"
              }`}
            >
              <button onClick={() => onOpen(c.id)} className="flex min-w-0 flex-1 items-center gap-2 px-2.5 py-2 text-left text-sm">
                <MessageSquare size={15} className="shrink-0 text-muted" />
                <span className="truncate">{c.title}</span>
              </button>
              <button
                onClick={() => onDelete(c.id)}
                aria-label={`Delete chat ${c.title}`}
                className="mr-1 rounded-md p-1.5 text-muted opacity-100 hover:text-red-500 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </nav>

        <div className="border-t border-line p-3">
          <button
            onClick={onToggleTheme}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-muted hover:bg-bg hover:text-ink"
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </aside>
    </>
  );
}
