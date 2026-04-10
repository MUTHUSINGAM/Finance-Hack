import React, { useState, forwardRef, useImperativeHandle } from 'react';
import axios from 'axios';
import { Send, Cpu, Zap, Archive } from 'lucide-react';
import DemoCards from './DemoCards';

import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const MainChat = forwardRef(({ onSourceClick, selectedFiles }, ref) => {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState('');

  // Allow App.jsx to manually push generic System updates into the RAG stream UI
  useImperativeHandle(ref, () => ({
    addSystemMessage: (msgText) => {
      setMessages(prev => [...prev, { role: 'assistant', content: msgText, isSystem: true }]);
    }
  }));

  const preProcessText = (text) => {
    if (!text) return '';
    // Wrap Sources so ReactMarkdown treats them natively as links
    return text.replace(/\[Source (\d+)\]/g, '[$&](source://$1)');
  };

  const handleSend = async (text) => {
    const q = text || query;
    if (!q.trim()) return;

    const newMsgs = [...messages, { role: 'user', content: q }];
    setMessages(newMsgs);
    setQuery('');
    setIsLoading(true);
    setStatusText('Routing via Open-Native Logic...');

    try {
      const res = await axios.post('http://localhost:8000/api/ask', { 
        query: q,
        // Enforce active exact bounding constraint arrays into generic payloads
        selected_files: selectedFiles && selectedFiles.length > 0 ? selectedFiles : null 
      });
      
      const isComplex = res.data.model.includes('gpt-4o') && !res.data.model.includes('mini');
      
      setMessages([...newMsgs, { 
        role: 'assistant', 
        content: res.data.answer, 
        model: res.data.model,
        isComplex 
      }]);
    } catch (err) {
      const errorDetail = err.response?.data?.detail || 'System Error: Connection Failed';
      setMessages([...newMsgs, { role: 'assistant', content: `**Error:** ${errorDetail}`, error: true }]);
    } finally {
      setIsLoading(false);
      setStatusText('');
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full m-4 ml-0 glass-panel overflow-hidden relative shadow-2xl">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto terminal-scroll p-8 pb-32">
        {messages.length === 0 ? (
           <div className="h-full flex flex-col items-center justify-center">
             <DemoCards onCardClick={(q) => handleSend(q)} />
           </div>
        ) : (
          <div className="flex flex-col gap-6 max-w-4xl mx-auto w-full">
            {messages.map((msg, i) => (
              <div key={i} className={`flex flex-col gap-1.5 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                 <div className={`p-4 rounded-xl max-w-[85%] text-[15px] leading-relaxed ${
                   msg.role === 'user' 
                     ? 'bg-zinc-800 text-white border border-zinc-700/50' 
                     : msg.isSystem 
                     ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-mono shadow-[0_4px_12px_rgba(0,0,0,0.2)]'
                     : 'bg-[#18181b]/90 border border-zinc-800 shadow-[0_4px_12px_rgba(0,0,0,0.2)] text-zinc-300'
                 }`}>
                   {msg.role === 'user' ? (
                     <div className="whitespace-pre-wrap">{msg.content}</div>
                   ) : (
                     <div className={`markdown-body space-y-3 prose max-w-none ${msg.isSystem ? 'prose-emerald' : 'prose-invert'} text-sm`}>
                       <ReactMarkdown
                         remarkPlugins={[remarkMath]}
                         rehypePlugins={[rehypeKatex]}
                         components={{
                           a: ({ node, ...props }) => {
                             if (props.href && props.href.startsWith("source://")) {
                               return (
                                  <span 
                                    onClick={() => onSourceClick("This is the raw context retrieved from the database representing: " + props.children)}
                                    className="text-blue-400 font-bold mx-1 cursor-pointer hover:underline"
                                  >
                                    {props.children}
                                  </span>
                               );
                             }
                             return <a className="text-emerald-400 hover:text-emerald-300 underline" target="_blank" rel="noopener noreferrer" {...props} />;
                           },
                           p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                           ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />,
                           ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />,
                           li: ({ node, ...props }) => <li className="" {...props} />,
                           strong: ({ node, ...props }) => <strong className={`${msg.isSystem ? 'text-emerald-400' : 'text-emerald-400'} font-semibold`} {...props} />,
                           code: ({ node, inline, className, children, ...props }) => {
                             const match = /language-([\w-]+)/.exec(className || '');
                             if (!inline && match && match[1] === 'chart-data') {
                               try {
                                 const data = JSON.parse(String(children).replace(/\n$/, ''));
                                 const keys = Object.keys(data[0] || {}).filter(k => !['year', 'date', 'name'].includes(k.toLowerCase()));
                                 const colors = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444"];
                                 
                                 return (
                                   <div className="w-full h-72 mt-6 mb-4 bg-black/40 p-5 rounded-xl border border-zinc-800 shadow-inner">
                                     <ResponsiveContainer width="100%" height="100%">
                                       <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: -20 }}>
                                         <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                                         <XAxis dataKey={Object.keys(data[0] || {}).find(k => ['year', 'date'].includes(k.toLowerCase())) || "year"} stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                                         <YAxis stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                                         <Tooltip 
                                           contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: '8px' }}
                                           itemStyle={{ color: '#e4e4e7' }}
                                         />
                                         <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                                         {keys.map((key, idx) => (
                                           <Line type="monotone" key={key} dataKey={key} stroke={colors[idx % colors.length]} strokeWidth={2} dot={{ r: 4, fill: '#18181b', strokeWidth: 2 }} activeDot={{ r: 6 }} />
                                         ))}
                                       </LineChart>
                                     </ResponsiveContainer>
                                   </div>
                                 );
                               } catch (e) {
                                 console.error("Chart Parse Error", e);
                               }
                             }
                             
                             return inline ? (
                               <code className="bg-black/50 px-1 py-0.5 rounded font-mono text-emerald-300 text-[13px]" {...props}>
                                 {children}
                               </code>
                             ) : (
                               <pre className="bg-black/50 p-3 rounded-lg overflow-x-auto my-2 border border-zinc-800/50">
                                 <code className={`font-mono text-emerald-300 text-sm ${className || ''}`} {...props}>
                                   {children}
                                 </code>
                               </pre>
                             );
                           }
                         }}
                       >
                         {preProcessText(msg.content)}
                       </ReactMarkdown>
                     </div>
                   )}
                 </div>
                 
                 {msg.role === 'assistant' && msg.model && !msg.isSystem && (
                   <div className="flex items-center gap-1.5 px-2 mt-1 text-[10px] uppercase font-mono tracking-wider text-zinc-500">
                     {msg.isComplex ? <Cpu size={12} className="text-blue-500" /> : <Zap size={12} className="text-emerald-500" />}
                     Processed by {msg.model}
                   </div>
                 )}
              </div>
            ))}
            
            {isLoading && (
              <div className="flex items-center gap-3 text-sm text-zinc-400 bg-zinc-900/50 self-start p-3 px-5 rounded-xl border border-zinc-800 mt-2">
                <div className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-ping"></div>
                <span className="font-mono text-xs tracking-wide">{statusText}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input Form */}
      <div className="absolute bottom-0 w-full p-6 pt-12 bg-gradient-to-t from-[#0c0c0e] via-[#0c0c0e]/90 to-transparent">
         <div className="max-w-4xl mx-auto flex items-center gap-3 bg-zinc-900 border border-zinc-700 shadow-[0_-10px_40px_rgba(0,0,0,0.5)] rounded-xl p-2 px-4 transition-all focus-within:border-emerald-500/50">
            <Archive size={20} className="text-zinc-500 cursor-pointer hover:text-white transition-colors ml-1" />
            <input 
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Query financial intelligence. e.g. Analyze MSFT Cloud Margins..."
              className="flex-1 bg-transparent text-white focus:outline-none placeholder-zinc-500 text-sm h-11 ml-2 font-mono"
            />
            <button 
              onClick={() => handleSend()} 
              disabled={isLoading || !query.trim()}
              className="px-4 h-9 bg-zinc-100 hover:bg-emerald-500 hover:text-white text-zinc-950 font-semibold rounded disabled:opacity-50 transition-all flex items-center justify-center"
            >
              <Send size={16} />
            </button>
         </div>
      </div>
    </div>
  );
});

export default MainChat;
