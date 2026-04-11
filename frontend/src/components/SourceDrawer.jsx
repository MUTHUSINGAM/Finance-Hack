import React from 'react';
import { X, FileText, Database } from 'lucide-react';

export default function SourceDrawer({ open, onClose, content }) {
  if (!open) return null;

  return (
    <div className="w-[400px] h-full flex flex-col p-5 gap-4 glass-panel mr-4 my-4 animate-in slide-in-from-right-10 duration-200 shadow-2xl relative z-20">
       <div className="flex items-center justify-between border-b border-zinc-800/50 pb-5 pt-1">
          <h2 className="text-sm font-semibold tracking-wider uppercase text-zinc-300 flex items-center gap-2 font-mono">
            <Database size={16} className="text-blue-500" /> Vector Database
          </h2>
          <button onClick={onClose} className="p-1.5 text-zinc-500 hover:text-white transition-colors bg-zinc-800 hover:bg-zinc-700 rounded-md border border-zinc-700">
            <X size={16} />
          </button>
       </div>

       <div className="flex-1 overflow-y-auto terminal-scroll pr-3 text-xs text-zinc-400 font-mono leading-relaxed mt-2 p-2 bg-[#0c0c0e]/50 border border-zinc-800/30 rounded-md">
          <span className="text-emerald-500/80">root@chromadb:~$ GET /documents/match</span><br/><br/>
          {content || "No context selected. Click a citation like [Source 1] in the chat to view the raw chunk."}
       </div>
    </div>
  );
}
