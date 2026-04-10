import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Settings, BarChart2, CheckSquare, UploadCloud, Search } from 'lucide-react';
import { API_BASE } from '../config';

export default function Sidebar({ selectedFiles, onScopeChange }) {
  const [budget, setBudget] = useState({ spent: 0, limit: 7.50, circuit_breaker_active: false });
  const [allDocs, setAllDocs] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [localSelection, setLocalSelection] = useState(selectedFiles || []);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  useEffect(() => {
    setLocalSelection(selectedFiles || []);
  }, [selectedFiles]);

  useEffect(() => {
    // Poll Budget Constraints
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

  const fetchDocs = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/documents`);
      setAllDocs(res.data.documents || []);
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  }, []);

  useEffect(() => {
    fetchDocs();
    // First request may run before the API is up; poll like budget until the list appears
    const intv = setInterval(fetchDocs, 5000);
    return () => clearInterval(intv);
  }, [fetchDocs]);

  const handleUpload = async (e) => {
    if (!e.target.files?.length) return;
    setIsUploading(true);
    setUploadError('');
    const formData = new FormData();
    for (const file of e.target.files) {
      formData.append('files', file);
    }
    try {
      const res = await axios.post(`${API_BASE}/api/upload`, formData);
      if (Array.isArray(res.data?.documents)) {
        setAllDocs(res.data.documents);
      } else {
        await fetchDocs();
      }
    } catch (err) {
      console.error('Upload failed:', err);
      setUploadError(
        err.response?.data?.detail || err.message || 'Upload failed — check API is running and VITE_API_URL matches the backend port.'
      );
    } finally {
      setIsUploading(false);
      e.target.value = null; // Clear physical target reference
    }
  };

  const toggleSelection = (doc) => {
    if(localSelection.includes(doc)) {
       setLocalSelection(localSelection.filter(d => d !== doc));
    } else {
       setLocalSelection([...localSelection, doc]);
    }
  };

  const progress = Math.min((budget.spent / budget.limit) * 100, 100);
  const filteredDocs = allDocs.filter(d => d.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="w-[340px] h-full flex flex-col p-4 gap-4 glass-panel ml-4 my-4 z-10 relative">
      {/* Header */}
      <div className="flex items-center gap-3 pb-4 border-b border-zinc-800">
        <BarChart2 className="text-emerald-500" size={24} />
        <h1 className="text-xl font-bold tracking-tight text-white">CIT Hackathon '26</h1>
      </div>

      {/* Document Context Selector */}
      <div className="flex flex-col gap-2 relative mt-2 flex-1 min-h-0">
        <label className="text-xs uppercase tracking-wider text-zinc-400 font-semibold flex justify-between items-center mb-1">
            Data Context
            {isUploading && <span className="text-emerald-400 animate-ping text-[10px]">(Vectorizing...)</span>}
        </label>
        
        {/* Search */}
        <div className="relative">
           <Search size={14} className="absolute left-2.5 top-[9px] text-zinc-500" />
           <input 
             type="text" 
             placeholder="Search active metadata..."
             value={searchQuery}
             onChange={e => setSearchQuery(e.target.value)}
             className="w-full bg-zinc-900 border border-zinc-800 text-sm rounded-lg pl-8 pr-3 py-1.5 text-zinc-300 focus:outline-none focus:border-emerald-500/50 transition-colors"
           />
        </div>

        {/* Scrollable Doc List */}
        <div className="flex-1 overflow-y-auto terminal-scroll border border-zinc-800 rounded-lg bg-black/20 p-1.5 mt-1">
           {filteredDocs.map(doc => (
             <div 
                key={doc} 
                onClick={() => toggleSelection(doc)}
                className={`flex items-center gap-2 p-2 rounded cursor-pointer text-sm font-mono transition-colors ${localSelection.includes(doc) ? 'bg-emerald-500/10 text-emerald-400' : 'hover:bg-zinc-800 text-zinc-400'}`}
             >
                <div className={`shrink-0 w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-colors ${localSelection.includes(doc) ? 'border-emerald-500 bg-emerald-500' : 'border-zinc-600'}`}>
                   {localSelection.includes(doc) && <CheckSquare size={10} className="text-zinc-950" />}
                </div>
                <span className="truncate">{doc}</span>
             </div>
           ))}
           {allDocs.length === 0 && <div className="text-xs text-zinc-600 p-2 text-center">No documents vectorized.</div>}
        </div>

        <div className="flex gap-2 mt-1">
            <button 
               onClick={() => setLocalSelection([])} 
               className="px-3 py-2 text-xs font-semibold rounded bg-zinc-800 text-zinc-400 hover:bg-zinc-700 w-[70px] transition-colors"
            >
               Clear
            </button>
            <button 
               onClick={() => onScopeChange(localSelection)} 
               className="flex-1 px-3 py-2 text-xs font-semibold rounded bg-zinc-100 text-zinc-950 hover:bg-emerald-500 hover:text-white transition-all text-center flex items-center justify-center"
            >
               Scope Chat ({localSelection.length})
            </button>
        </div>
        
        {/* Quick Upload */}
        <div className="mt-2 text-center border border-dashed border-zinc-700 bg-zinc-900/50 rounded-lg p-3 hover:bg-zinc-800 transition-colors relative cursor-pointer group shrink-0">
            <UploadCloud size={18} className="mx-auto text-zinc-500 group-hover:text-emerald-500 transition-colors" />
            <span className="text-xs text-zinc-400 block mt-1 font-mono group-hover:text-zinc-300">Fast-Upload PDFs</span>
            <input type="file" multiple accept=".pdf" onChange={handleUpload} className="absolute inset-0 opacity-0 cursor-pointer" />
            {uploadError && (
              <p className="text-[10px] text-red-400 mt-2 px-1 font-mono relative z-10 pointer-events-none">{uploadError}</p>
            )}
        </div>
      </div>

      {/* Budget Tracker Widget */}
      <div className="mt-4 bg-black/40 border border-zinc-800 p-4 rounded-lg flex flex-col gap-3 shadow-inner shrink-0">
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
