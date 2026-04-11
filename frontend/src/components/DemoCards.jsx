import React from 'react';
import { TrendingUp, PieChart, Activity } from 'lucide-react';

export default function DemoCards({ onCardClick }) {
  const demos = [
    {
      title: "Analyze Intel R&D vs Revenue",
      desc: "Compare INTC investments across 2020-2023",
      icon: <Activity className="text-blue-500" size={24} />
    },
    {
      title: "Disney Streaming Impact",
      desc: "How did D+ affect total profit margins?",
      icon: <TrendingUp className="text-emerald-500" size={24} />
    },
    {
      title: "Microsoft Cloud Growth",
      desc: "Azure revenue trends vs Google Cloud",
      icon: <PieChart className="text-purple-500" size={24} />
    }
  ];

  return (
    <div className="flex flex-col items-center gap-10 mt-[-50px]">
       <div className="text-center">
           <h2 className="text-4xl font-light tracking-tight text-white mb-2">
             Financial <span className="font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-500">Intelligence Core</span>
           </h2>
           <p className="text-zinc-500 text-sm mt-3">Questions grounded in your financial filings</p>
       </div>
       
       <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl w-full">
         {demos.map((demo, idx) => (
           <div 
             key={idx}
             onClick={() => onCardClick(demo.title)}
             className="bg-black/30 border border-zinc-800 hover:border-emerald-500/50 hover:bg-zinc-800/60 p-6 rounded-xl cursor-pointer transition-all duration-300 group shadow-lg"
           >
              <div className="bg-zinc-900/80 p-3 w-12 h-12 flex items-center justify-center rounded-lg border border-zinc-800 mb-5 group-hover:scale-110 transition-transform">
                {demo.icon}
              </div>
              <h3 className="text-zinc-200 font-medium text-sm mb-1">{demo.title}</h3>
              <p className="text-zinc-500 text-xs leading-relaxed mt-2">{demo.desc}</p>
           </div>
         ))}
       </div>
    </div>
  );
}
