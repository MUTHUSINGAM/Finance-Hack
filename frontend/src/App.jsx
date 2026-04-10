import React, { useState, useRef } from 'react';
import Sidebar from './components/Sidebar';
import MainChat from './components/MainChat';
import SourceDrawer from './components/SourceDrawer';

function App() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerContent, setDrawerContent] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  
  const chatRef = useRef(null);

  const handleSourceClick = (content) => {
    setDrawerContent(content);
    setDrawerOpen(true);
  };
  
  const handleScopeChange = (files) => {
    setSelectedFiles(files);
    const msg = files.length > 0
      ? `**System:** Chat context successfully restricted to [${files.join(", ")}].`
      : `**System:** Chat context restored to global mode. Exploring all vectorized documents.`;
    if (chatRef.current) {
        chatRef.current.addSystemMessage(msg);
    }
  }

  return (
    <div className="flex h-screen w-full bg-[#09090b] text-zinc-100 overflow-hidden font-sans">
      <Sidebar selectedFiles={selectedFiles} onScopeChange={handleScopeChange} />
      <MainChat ref={chatRef} onSourceClick={handleSourceClick} selectedFiles={selectedFiles} />
      <SourceDrawer 
         open={drawerOpen} 
         onClose={() => setDrawerOpen(false)} 
         content={drawerContent} 
      />
    </div>
  );
}

export default App;
