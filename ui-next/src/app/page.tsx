"use client";

import React, { useState, useEffect, useRef } from "react";
import { gsap } from "gsap";
import { motion, AnimatePresence } from "framer-motion";
import { Send, ChevronDown, ChevronRight, CornerDownRight } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  sources?: any[];
  status?: string;
  thought_process?: string[];
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "agent",
      content: "Hello! I am a specialized RAG assistant. I can only answer questions related to Kubernetes and Intel based on the provided documents.",
    }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  // Animation Refs
  const headerRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);

  // Initial GSAP Entrance Animation
  useEffect(() => {
    const tl = gsap.timeline();
    
    tl.fromTo(
      headerRef.current,
      { y: -20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: "power2.out" }
    )
    .fromTo(
      chatContainerRef.current,
      { opacity: 0 },
      { opacity: 1, duration: 1, ease: "power2.out" },
      "-=0.6"
    )
    .fromTo(
      inputContainerRef.current,
      { y: 20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: "power2.out" },
      "-=0.8"
    );
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/query_stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q: userMessage.content, thread_id: "nextjs_user" }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      let currentAgentMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "agent",
        content: "",
        sources: [],
        status: "Thinking...",
        thought_process: []
      };

      setMessages((prev) => [...prev, currentAgentMessage]);
      setIsLoading(false); // Stop loading animation, start streaming

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        
        // Keep the last incomplete chunk in the buffer
        buffer = lines.pop() || "";
        
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === "plan") {
                currentAgentMessage = { ...currentAgentMessage, thought_process: data.content };
              } else if (data.type === "sources") {
                currentAgentMessage = { ...currentAgentMessage, sources: data.content };
              } else if (data.type === "token") {
                currentAgentMessage = { ...currentAgentMessage, content: currentAgentMessage.content + data.content };
              } else if (data.type === "error") {
                currentAgentMessage = { ...currentAgentMessage, content: data.content };
              }
              
              setMessages((prev) => prev.map(msg => msg.id === currentAgentMessage.id ? currentAgentMessage : msg));
            } catch (e) {
              console.error("Error parsing SSE JSON", e, line);
            }
          }
        }
      }
    } catch (error) {
      console.error("Query failed:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "agent",
          content: "Connection to the LangGraph backend failed. Please ensure FastAPI is running.",
        }
      ]);
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-full bg-[#FAFAFA] text-gray-900 font-sans selection:bg-gray-200">
      
      {/* MINIMALIST HEADER */}
      <header ref={headerRef} className="w-full flex items-center justify-center p-6 border-b border-gray-100 bg-white/50 backdrop-blur-md z-10 sticky top-0">
        <h1 className="text-[13px] font-semibold tracking-[0.2em] uppercase text-gray-400">
          LangGraph <span className="text-gray-900">RAG</span>
        </h1>
      </header>

      {/* CHAT DISPLAY */}
      <main 
        ref={chatContainerRef}
        className="flex-1 w-full max-w-3xl mx-auto overflow-y-auto px-4 md:px-0 py-8 custom-scrollbar"
      >
        <div className="flex flex-col gap-10 pb-20">
          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className="flex flex-col gap-2"
              >
                {/* Role Label */}
                <span className="text-[11px] font-semibold tracking-widest uppercase text-gray-400 pl-1">
                  {msg.role === "user" ? "You" : "Assistant"}
                </span>

                <div className={`text-[15px] leading-[1.7] text-gray-800 ${msg.role === "user" ? "bg-gray-100 rounded-2xl px-5 py-4 w-fit" : "px-1"}`}>
                  
                  {/* Thought Flow (For Agent) */}
                  {msg.role === "agent" && msg.thought_process && msg.thought_process.length > 0 && (
                    <ThoughtFlow process={msg.thought_process} />
                  )}

                  {/* Main Content */}
                  <div className="whitespace-pre-wrap font-medium">
                    {msg.content}
                  </div>

                  {/* Sources (For Agent) */}
                  {msg.role === "agent" && msg.sources && msg.sources.length > 0 && (
                    <div className="mt-6 pt-5 border-t border-gray-100">
                      <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3 block">
                        Retrieved Contexts
                      </span>
                      <div className="flex flex-col gap-3">
                        {msg.sources.map((src: any, idx: number) => (
                          <CollapsibleSource key={idx} source={src} index={idx} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Minimal Loading Indicator */}
          {isLoading && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col gap-2"
            >
              <span className="text-[11px] font-semibold tracking-widest uppercase text-gray-400 pl-1">
                Assistant
              </span>
              <div className="flex items-center gap-1.5 h-6 px-1">
                <div className="w-1.5 h-1.5 rounded-full bg-gray-300 animate-pulse" />
                <div className="w-1.5 h-1.5 rounded-full bg-gray-300 animate-pulse delay-75" />
                <div className="w-1.5 h-1.5 rounded-full bg-gray-300 animate-pulse delay-150" />
              </div>
            </motion.div>
          )}
        </div>
      </main>

      {/* INPUT AREA */}
      <footer 
        ref={inputContainerRef}
        className="w-full max-w-3xl mx-auto p-4 md:px-0 mb-4 bg-transparent"
      >
        <form 
          onSubmit={handleSubmit}
          className="flex items-end gap-3 p-2 rounded-2xl bg-white border border-gray-200 shadow-[0_8px_30px_rgb(0,0,0,0.04)] focus-within:border-gray-300 focus-within:shadow-[0_8px_40px_rgb(0,0,0,0.08)] transition-all duration-300"
        >
          <div className="flex-1 min-h-[44px] flex items-center px-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder="Message the LangGraph agent..."
              className="w-full bg-transparent border-none outline-none text-gray-800 placeholder-gray-400 text-[15px] resize-none overflow-hidden py-3"
              rows={1}
              disabled={isLoading}
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="flex-shrink-0 flex items-center justify-center w-9 h-9 mb-1 mr-1 rounded-xl bg-black text-white disabled:opacity-30 disabled:bg-gray-100 disabled:text-gray-400 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <p className="text-center text-[10px] text-gray-400 mt-3 font-medium">
          LangGraph may produce inaccurate information about people, places, or facts.
        </p>
      </footer>
    </div>
  );
}

// Collapsible Thought Flow Component
function ThoughtFlow({ process }: { process: string[] }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mb-4">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 text-[12px] font-medium text-gray-500 hover:text-gray-900 transition-colors px-2 py-1 -ml-2 rounded-md hover:bg-gray-100"
      >
        {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        View Agent Reasoning
      </button>
      
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-2 mt-3 p-4 bg-gray-50 rounded-xl border border-gray-100 text-[13px] text-gray-600 font-mono">
              {process.map((step, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <CornerDownRight className="w-3.5 h-3.5 mt-0.5 text-gray-400 flex-shrink-0" />
                  <span>{step}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function CollapsibleSource({ source, index }: { source: any; index: number }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="rounded-lg bg-white border border-gray-100 shadow-sm overflow-hidden">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 text-left bg-gray-50/50 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isOpen ? <ChevronDown className="w-3.5 h-3.5 text-gray-400" /> : <ChevronRight className="w-3.5 h-3.5 text-gray-400" />}
          <span className="text-[13px] font-semibold text-gray-900">
            {source.metadata?.source_type || `Retrieved Context ${index + 1}`}
          </span>
        </div>
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="p-4 text-[13px] text-gray-600 leading-relaxed border-t border-gray-100 bg-white">
              {source.page_content}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
