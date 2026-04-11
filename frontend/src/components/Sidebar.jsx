import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, BarChart2 } from 'lucide-react';
import { API_BASE } from '../config';

export default function Sidebar() {
  const [budget, setBudget] = useState({ spent: 0, limit: 7.50, circuit_breaker_active: false });

  useEffect(() => {
    const fetchBudget = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/budget`);
        setBudget(res.data);
      } catch (err) {}
    };
    fetchBudget();
    const intv = setInterval(fetchBudget, 5000);
    return () => clearInterval(intv);
  }, []);

  const progress = Math.min((budget.spent / budget.limit) * 100, 100);

  return (
    <div className="w-[300px] h-full flex flex-col p-4 gap-4 glass-panel ml-4 my-4 z-10 relative">
      <div className="flex items-center gap-3 pb-4 border-b border-zinc-800">
        <BarChart2 className="text-emerald-500" size={24} />
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-white">Financial Intelligence</h1>
          <p className="text-[11px] text-zinc-500 mt-0.5">Portal</p>
        </div>
      </div>

      <div className="flex flex-col gap-3 mt-1 flex-1 min-h-0">
        <div className="rounded-lg border border-zinc-800/80 bg-black/25 p-4 text-sm text-zinc-400 leading-relaxed">
          <p className="text-zinc-300 font-medium text-[13px] mb-2">How to use this</p>
          <ul className="space-y-2 text-[13px] list-disc pl-4 marker:text-emerald-600/80">
            <li>Ask in plain language about metrics, risks, segments, or periods that appear in your filings.</li>
            <li>
              To compare companies, name them and use words like{' '}
              <span className="text-emerald-500/90">compare</span>,{' '}
              <span className="text-emerald-500/90">vs</span>, or{' '}
              <span className="text-emerald-500/90">between … and</span>.
            </li>
            <li>Answers cite sources from the retrieved excerpts—open the sources section under a reply when you need detail.</li>
          </ul>
        </div>
      </div>

      <div className="mt-auto bg-black/40 border border-zinc-800 p-4 rounded-lg flex flex-col gap-3 shadow-inner shrink-0">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium flex items-center gap-1.5 text-zinc-300">
            <Settings size={14} className="text-zinc-500" /> Usage
          </span>
          <span className="text-xs tabular-nums bg-zinc-800 px-2 py-1 rounded text-emerald-400 border border-zinc-700">
            ${budget.spent.toFixed(4)} / ${budget.limit.toFixed(2)}
          </span>
        </div>
        <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden shadow-inner">
          <div
            className={`h-full ${budget.circuit_breaker_active ? 'bg-red-500' : 'bg-emerald-500'} transition-all duration-500`}
            style={{ width: `${progress}%` }}
          />
        </div>
        {budget.circuit_breaker_active && (
          <div className="text-[10px] text-red-400 text-center border border-red-900/50 bg-red-950/20 py-1.5 rounded">
            Usage limit reached for this session
          </div>
        )}
      </div>
    </div>
  );
}
