import { useState } from "react";
import { sendMessage } from "./api";

type Message = {
  role: "user" | "ai";
  text: string;
};

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>("");

  const handleSend = async () => {
    if (!input.trim()) return;

    // user message
    const userMsg: Message = {
      role: "user",
      text: input,
    };

    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await sendMessage(input);

      const aiMsg: Message = {
        role: "ai",
        text: res.response,
      };

      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      const errorMsg: Message = {
        role: "ai",
        text: "Error connecting to server",
      };

      setMessages((prev) => [...prev, errorMsg]);
    }

    setInput("");
  };

  return (
    <div style={{ padding: 20, maxWidth: 600, margin: "0 auto" }}>
      <h2>AI Scheduling Assistant</h2>

      <div
        style={{
          border: "1px solid #ddd",
          padding: 10,
          height: 400,
          overflowY: "auto",
          marginBottom: 10,
        }}
      >
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 8 }}>
            <b>{msg.role === "user" ? "You" : "AI"}:</b> {msg.text}
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          style={{ flex: 1, padding: 8 }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
        />

        <button onClick={handleSend}>Send</button>
      </div>
    </div>
  );
}