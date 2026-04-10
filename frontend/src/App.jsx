import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import MainChat from './components/MainChat';
import SourceDrawer from './components/SourceDrawer';

function App() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerContent, setDrawerContent] = useState("");

  const handleSourceClick = (content) => {
    setDrawerContent(content);
    setDrawerOpen(true);
  };

  return (
    <div className="flex h-screen w-full bg-[#09090b] text-zinc-100 overflow-hidden font-sans">
      <Sidebar />
      <MainChat onSourceClick={handleSourceClick} />
      <SourceDrawer 
         open={drawerOpen} 
         onClose={() => setDrawerOpen(false)} 
         content={drawerContent} 
      />
    </div>
  );
}

export default App;
