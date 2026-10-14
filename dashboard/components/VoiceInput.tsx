"use client";
import { useState, useRef } from "react";

export default function VoiceInput({ onTranscript }: { onTranscript: (text: string) => void }) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  const toggle = () => {
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition not supported in this browser. Try Chrome.");
      return;
    }
    
    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = true;

    recognition.onresult = (e: any) => {
      let currentTranscript = "";
      for (let i = 0; i < e.results.length; ++i) {
        currentTranscript += e.results[i][0].transcript;
      }
      onTranscript(currentTranscript);
    };
    recognition.onerror = (e: any) => {
        console.error("Speech error", e.error);
        if(e.error === 'not-allowed') alert("Microphone access denied.");
        setListening(false);
    };
    recognition.onend = () => setListening(false);
    
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  };

  return (
    <button onClick={toggle} type="button" className="btn-icon" style={{
      width: 44, height: 44, flexShrink: 0,
      background: listening ? "var(--danger)" : "transparent",
      color: listening ? "#fff" : "var(--text-muted)",
      borderColor: listening ? "var(--danger)" : "var(--border-subtle)",
      cursor: "pointer",
      transition: "all 0.3s",
      animation: listening ? "pulse-ring 1.5s infinite" : "none",
    }} title={listening ? "Listening..." : "Click to speak"}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="23"/>
        <line x1="8" y1="23" x2="16" y2="23"/>
      </svg>
    </button>
  );
}
