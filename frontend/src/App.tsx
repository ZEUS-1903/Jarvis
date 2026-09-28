import { useCallback, useEffect, useState } from "react";
import { ApiError, checkHealth, getConversationMessages, getMemories, sendMessage, transcribe } from "./api";
import { MemoryPanel } from "./components/MemoryPanel";
import { WakeToggle } from "./components/WakeToggle";
import { loadConversationId, saveConversationId } from "./conversationStorage";
import { MicButton } from "./components/MicButton";
import { MessageInput } from "./components/MessageInput";
import { MessageList } from "./components/MessageList";
import { isSpeaking, playSpeech } from "./speech";
import type { ChatMessage, Memory } from "./types";

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  // Returned by the backend on the first reply; sent back so it can find the history.
  const [conversationId, setConversationIdState] = useState<string | null>(loadConversationId);
  const setConversationId = (id: string | null) => {
    setConversationIdState(id);
    saveConversationId(id);
  };
  const [thinking, setThinking] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [memories, setMemories] = useState<{ active: Memory[]; pending: Memory[] }>({ active: [], pending: [] });
  const [showMemory, setShowMemory] = useState(false);

  const refreshMemories = useCallback(() => {
    getMemories().then(setMemories).catch(() => {}); // non-critical: chat still works without it
  }, []);

  useEffect(() => {
    checkHealth().then(setOnline);
    refreshMemories();
    // Restore the previous conversation (stored in Postgres) after a page reload.
    const saved = loadConversationId();
    if (saved) {
      getConversationMessages(saved)
        .then(({ messages }) =>
          setMessages(
            messages.map((m): ChatMessage =>
              m.role === "user"
                ? { role: "user", content: m.content }
                : { role: "assistant", content: m.content, tools: [], requestId: null },
            ),
          ),
        )
        .catch(() => {
          // Conversation is gone (e.g. database reset): start fresh.
          setConversationIdState(null);
          saveConversationId(null);
        });
    }
  }, [refreshMemories]);

  // Voice turn: recording -> Whisper -> normal chat -> spoken reply.
  async function handleVoice(audio: Blob, player: HTMLAudioElement) {
    setError(null);
    setTranscribing(true);
    let text: string;
    try {
      text = (await transcribe(audio)).text;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    } finally {
      setTranscribing(false);
    }
    // Drop the wake phrase if Whisper heard it ("Hey Jarvis, what's the time?").
    text = text.replace(/^\s*(hey|hi|okay|ok)?[\s,]*jarvis\b[\s,.!?:-]*/i, "").trim();
    if (!text) {
      setError("I didn't catch that. Try again, a little closer to the mic.");
      return;
    }
    await handleSend(text, player);
  }

  async function handleSend(text: string, speakWith?: HTMLAudioElement) {
    setError(null);
    // Optimistic update: show the user's message immediately.
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setThinking(true);
    try {
      const res = await sendMessage(text, conversationId, Boolean(speakWith));
      setConversationId(res.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reply, tools: res.tool_calls, requestId: res.request_id },
      ]);
      setOnline(true);
      refreshMemories(); // the reply may have saved or proposed a memory
      // Spoken question -> spoken answer. Speech errors shouldn't hide the text reply.
      if (speakWith) {
        playSpeech(res.reply, speakWith).catch((e) =>
          setError(`Couldn't speak the reply: ${e instanceof Error ? e.message : e}`),
        );
      }
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, String(e));
      if (err.status === 404) {
        // Backend restarted and lost in-memory history (expected in V1).
        setConversationId(null);
        setError("Jarvis restarted and lost this conversation. Send your message again to start fresh.");
      } else {
        setError(err.message);
        if (err.status === 0) setOnline(false);
      }
    } finally {
      setThinking(false);
    }
  }

  function newChat() {
    setMessages([]);
    setConversationId(null);
    setError(null);
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className={`status ${online === false ? "down" : online ? "up" : ""}`} />
          Jarvis
        </div>
        <div className="header-actions">
          <WakeToggle
            isBusy={() => thinking || transcribing || isSpeaking()}
            onCommand={(wav) => handleVoice(wav, new Audio())}
          />
          <button
            className="ghost"
            onClick={() => {
              refreshMemories();
              setShowMemory((v) => !v);
            }}
          >
            Memory
            {memories.pending.length > 0 && (
              <span className="badge" title="Waiting for your approval">{memories.pending.length}</span>
            )}
          </button>
          <button className="ghost" onClick={newChat} disabled={thinking}>New chat</button>
        </div>
      </header>
      {showMemory && (
        <MemoryPanel {...memories} onChange={refreshMemories} onClose={() => setShowMemory(false)} />
      )}
      <MessageList messages={messages} thinking={thinking || transcribing} />
      {error && <div className="error" role="alert">{error}</div>}
      <MessageInput
        onSend={(text) => handleSend(text)}
        disabled={thinking || transcribing}
        extra={
          <MicButton disabled={thinking || transcribing} onRecorded={handleVoice} onError={setError} />
        }
      />
    </div>
  );
}
