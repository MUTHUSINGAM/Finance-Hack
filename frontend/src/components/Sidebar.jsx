import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, BarChart2, Briefcase, FileText } from 'lucide-react';

export default function Sidebar() {
  const [budget, setBudget] = useState({ spent: 0, limit: 7.50, circuit_breaker_active: false });

  useEffect(() => {
    const fetchBudget = async () => {
      try {
        const res = await axios.get('http://localhost:8000/api/budget');
        setBudget(res.data);
      } catch (err) {
        console.error('Failed to fetch budget:', err);
      }
    };
    fetchBudget();
    const intv = setInterval(fetchBudget, 5000);
    return () => clearInterval(intv);
  }, []);

  const progress = Math.min((budget.spent / budget.limit) * 100, 100);

  return (
    <div className="w-80 h-full flex flex-col p-4 gap-4 glass-panel ml-4 my-4 z-10 relative">
      {/* Header */}
      <div className="flex items-center gap-3 pb-4 border-b border-zinc-800">
        <BarChart2 className="text-emerald-500" size={24} />
        <h1 className="text-xl font-bold tracking-tight text-white">CIT Hackathon '26</h1>
      </div>

      {/* Tickers */}
      <div className="flex flex-col gap-2 relative mt-2">
        <label className="text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1">Target Companies</label>
        <div className="flex flex-wrap gap-2">
          {['AAPL', 'MSFT', 'DIS', 'TSLA'].map(ticker => (
            <span key={ticker} className="px-3 py-1 bg-zinc-800 border border-zinc-700 rounded-md text-xs font-mono cursor-pointer hover:bg-zinc-700 transition-colors shadow-sm">
              {ticker}
            </span>
          ))}
        </div>
      </div>

      {/* Year Range */}
      <div className="mt-6 flex flex-col gap-2">
         <label className="text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1">Time Horizon (Years)</label>
         <div className="flex items-center gap-4 mt-2">
            <span className="text-xs text-zinc-500 font-mono">2015</span>
            <input type="range" min="2015" max="2023" className="w-full accent-emerald-500 bg-zinc-800 h-1 rounded-full appearance-none outline-none" />
            <span className="text-xs text-zinc-500 font-mono">2023</span>
         </div>
      </div>

      <div className="flex-1"></div>

      {/* Budget Tracker Widget */}
      <div className="mt-auto bg-black/40 border border-zinc-800 p-4 rounded-lg flex flex-col gap-3 shadow-inner">
        <div className="flex items-center justify-between">
            <span className="text-xs font-semibold flex items-center gap-1.5 text-zinc-300">
              <Settings size={14} className="text-zinc-500" /> API Tracker
            </span>
            <span className="text-xs font-mono bg-zinc-800 px-2 py-1 rounded text-emerald-400 border border-zinc-700">
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
          <div className="text-[10px] text-red-500 uppercase font-mono tracking-wider flex justify-center border border-red-900/50 bg-red-950/20 py-1.5 rounded animate-pulse">
            CIRCUIT BREAKER ACTIVE
          </div>
        )}
      </div>
    </div>
  );
}
