import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  sendMessage,
} from "./api";

// ============================================================
// TYPES
// ============================================================

type AppointmentSlot = {
  start: string;
  end: string;
};

type SchedulingResponse = {
  success: boolean;

  message?: string;

  slots?: AppointmentSlot[];

  available_slots?: AppointmentSlot[];

  start?: string;

  end?: string;

  event_id?: string;

  link?: string;

  needs_input?: boolean;
};

type Message = {
  role: "user" | "ai";

  text: string;

  schedulingData?: SchedulingResponse;
};

type User = {
  id: number;

  email: string;

  name?: string;
};

type ChatProps = {
  user: User | null;

  onLogout: () => void;
};

// ============================================================
// CONSTANTS
// ============================================================

const WELCOME_MESSAGE =
  "Hi! I'm your AI Scheduling Assistant. How can I help you today?";

// ============================================================
// CHAT
// ============================================================

export default function Chat({
  user,
  onLogout,
}: ChatProps) {

  const [messages, setMessages] =
    useState<Message[]>([
      {
        role: "ai",
        text: WELCOME_MESSAGE,
      },
    ]);

  const [input, setInput] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [isListening, setIsListening] =
    useState(false);

  const recognitionRef =
    useRef<any>(null);

  const messagesEndRef =
    useRef<HTMLDivElement>(null);

  const inputRef =
    useRef<HTMLTextAreaElement>(null);

  // ==========================================================
  // VOICE INPUT
  // ==========================================================

const handleVoiceInput = () => {
  const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    alert(
      "Speech recognition is not supported. Please use Google Chrome."
    );
    return;
  }

  if (recognitionRef.current) {
    recognitionRef.current.stop();
    recognitionRef.current = null;
    setIsListening(false);
    return;
  }

  const recognition = new SpeechRecognition();

  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    console.log("🎙️ MICROPHONE STARTED");
    setIsListening(true);
  };

  recognition.onresult = (event: any) => {
    console.log("🎙️ RESULT EVENT:", event);

    const transcript =
      event.results[0][0].transcript.trim();

    console.log(
      "🎙️ FINAL TRANSCRIPT:",
      transcript
    );

    if (transcript) {
      setInput(transcript);

      // Force textarea resize/focus after React updates
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.style.height = "auto";

          inputRef.current.style.height =
            `${Math.min(
              inputRef.current.scrollHeight,
              140
            )}px`;

          inputRef.current.focus();
        }
      }, 50);
    }
  };

  recognition.onerror = (event: any) => {
    console.error(
      "🎙️ SPEECH ERROR:",
      event.error
    );

    setIsListening(false);
    recognitionRef.current = null;

    if (event.error === "not-allowed") {
      alert(
        "Microphone permission was denied. Please allow microphone access."
      );
    }

    if (event.error === "no-speech") {
      alert(
        "I didn't hear anything. Please try speaking again."
      );
    }
  };

  recognition.onend = () => {
    console.log(
      "🎙️ MICROPHONE ENDED"
    );

    setIsListening(false);
    recognitionRef.current = null;
  };

  recognitionRef.current = recognition;

  try {
    recognition.start();
  } catch (error) {
    console.error(
      "🎙️ START ERROR:",
      error
    );

    setIsListening(false);
    recognitionRef.current = null;
  }
};

  // ==========================================================
  // STOP VOICE WHEN COMPONENT UNMOUNTS
  // ==========================================================

  useEffect(() => {

    return () => {

      recognitionRef.current?.stop();

    };

  }, []);

  // ==========================================================
  // SCROLL TO BOTTOM
  // ==========================================================

  useEffect(() => {

    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });

  }, [
    messages,
    loading,
  ]);

  // ==========================================================
  // AUTO RESIZE TEXTAREA
  // ==========================================================

  const resizeTextarea = () => {

    const textarea =
      inputRef.current;

    if (!textarea) {

      return;
    }

    textarea.style.height =
      "auto";

    const maxHeight =
      140;

    textarea.style.height =
      `${Math.min(
        textarea.scrollHeight,
        maxHeight
      )}px`;
  };

  // ==========================================================
  // SEND MESSAGE
  // ==========================================================

  const handleSend = async (
    messageOverride?: string
  ) => {

    const message =
      (
        messageOverride ??
        input
      ).trim();

    if (
      !message ||
      loading
    ) {

      return;
    }

    // --------------------------------------------------------
    // USER MESSAGE
    // --------------------------------------------------------

    const userMessage: Message = {
      role: "user",

      text: message,
    };

    setMessages((prev) => [

      ...prev,

      userMessage,

    ]);

    // --------------------------------------------------------
    // CLEAR INPUT
    // --------------------------------------------------------

    setInput("");

    setLoading(true);

    if (inputRef.current) {

      inputRef.current.style.height =
        "auto";
    }

    // --------------------------------------------------------
    // CALL BACKEND
    // --------------------------------------------------------

    try {

      const result =
        await sendMessage(
          message
        );

      // ------------------------------------------------------
      // AUTHENTICATION EXPIRED
      // ------------------------------------------------------

      if (
        result.error ===
        "Authentication required"
      ) {

        onLogout();

        return;
      }

      // ------------------------------------------------------
      // BACKEND ERROR
      // ------------------------------------------------------

      if (result.error) {

        setMessages((prev) => [

          ...prev,

          {
            role: "ai",

            text:
              result.error!,
          },

        ]);

        return;
      }

      // ------------------------------------------------------
      // RESPONSE
      // ------------------------------------------------------

      const response =
        result.response;

      // ------------------------------------------------------
      // STRUCTURED RESPONSE
      // ------------------------------------------------------

      if (
        response &&
        typeof response === "object"
      ) {

        const aiMessage: Message = {

          role: "ai",

          text:
            response.message ??
            "I couldn't process that request.",

          schedulingData:
            response,
        };

        setMessages((prev) => [

          ...prev,

          aiMessage,

        ]);

      }

      // ------------------------------------------------------
      // NORMAL TEXT RESPONSE
      // ------------------------------------------------------

      else {

        const aiMessage: Message = {

          role: "ai",

          text:
            response ??
            "I couldn't process that request.",
        };

        setMessages((prev) => [

          ...prev,

          aiMessage,

        ]);
      }

    } catch (error) {

      console.error(
        "Chat error:",
        error
      );

      setMessages((prev) => [

        ...prev,

        {
          role: "ai",

          text:
            "Sorry, I couldn't connect to the server. Please try again.",
        },

      ]);

    } finally {

      setLoading(false);

      setTimeout(() => {

        inputRef.current?.focus();

      }, 50);
    }
  };

  // ==========================================================
  // SELECT APPOINTMENT SLOT
  // ==========================================================

  const handleSlotSelect = (
    slot: AppointmentSlot
  ) => {

    const start =
      new Date(
        slot.start
      );

    const selectedTime =
      start.toLocaleTimeString(
        [],
        {
          hour: "numeric",
          minute: "2-digit",
        }
      );

    setInput(
      selectedTime
    );

    setTimeout(() => {

      resizeTextarea();

      inputRef.current?.focus();

    }, 50);
  };

  // ==========================================================
  // KEYBOARD
  // ==========================================================

  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {

    // --------------------------------------------------------
    // SHIFT + ENTER
    // --------------------------------------------------------

    if (
      event.key === "Enter" &&
      event.shiftKey
    ) {

      return;
    }

    // --------------------------------------------------------
    // ENTER
    // --------------------------------------------------------

    if (
      event.key === "Enter"
    ) {

      event.preventDefault();

      handleSend();
    }
  };

  // ==========================================================
  // NEW CHAT
  // ==========================================================

  const handleNewChat = () => {

    if (loading) {

      return;
    }

    // Stop microphone if active

    if (isListening) {

      recognitionRef.current?.stop();

      setIsListening(false);
    }

    setMessages([

      {
        role: "ai",

        text:
          WELCOME_MESSAGE,
      },

    ]);

    setInput("");

    if (inputRef.current) {

      inputRef.current.style.height =
        "auto";
    }

    setTimeout(() => {

      inputRef.current?.focus();

    }, 50);
  };

  // ==========================================================
  // LOGOUT
  // ==========================================================

  const handleLogout = () => {

    if (loading) {

      return;
    }

    if (isListening) {

      recognitionRef.current?.stop();

      setIsListening(false);
    }

    onLogout();
  };

  // ==========================================================
  // RENDER
  // ==========================================================

  return (

    <div className="app-shell">

      {/* ====================================================
          HEADER
      ==================================================== */}

      <header className="chat-header">

        <div className="brand">

          <div className="brand-icon">
            📅
          </div>

          <div>

            <div className="brand-name">
              AI Scheduling Assistant
            </div>

            <div className="brand-status">

              <span className="status-dot" />

              Online

            </div>

          </div>

        </div>

        <div className="header-actions">

          <div className="user-info">

            <div className="user-name">
              {user?.name || "User"}
            </div>

            <div className="user-email">
              {user?.email}
            </div>

          </div>

          <button
            type="button"
            className="new-chat-button"
            onClick={handleNewChat}
            disabled={loading}
          >
            + New chat
          </button>

          <button
            type="button"
            className="logout-button"
            onClick={handleLogout}
            disabled={loading}
          >
            Logout
          </button>

        </div>

      </header>

      {/* ====================================================
          CHAT
      ==================================================== */}

      <main className="chat-container">

        <div className="messages">

          {messages.map(
            (
              message,
              index
            ) => (

              <div
                key={index}
                className={
                  message.role === "user"
                    ? "message-row user-row"
                    : "message-row ai-row"
                }
              >

                {/* AI AVATAR */}

                {message.role === "ai" && (

                  <div className="avatar ai-avatar">
                    AI
                  </div>

                )}

                {/* MESSAGE */}

                <div
                  className={
                    message.role === "user"
                      ? "message user-message"
                      : "message ai-message"
                  }
                >

                  {renderMessage(
                    message.text
                  )}

                  {/* AVAILABLE SLOTS */}

                  {message.schedulingData && (

                    <AppointmentSlots
                      data={
                        message.schedulingData
                      }
                      onSelect={
                        handleSlotSelect
                      }
                    />

                  )}

                </div>

                {/* USER AVATAR */}

                {message.role === "user" && (

                  <div className="avatar user-avatar">
                    You
                  </div>

                )}

              </div>

            )
          )}

          {/* =================================================
              TYPING INDICATOR
          ================================================= */}

          {loading && (

            <div className="message-row ai-row">

              <div className="avatar ai-avatar">
                AI
              </div>

              <div className="message ai-message">

                <div className="typing">

                  <span />

                  <span />

                  <span />

                </div>

              </div>

            </div>

          )}

          <div
            ref={messagesEndRef}
          />

        </div>

      </main>

      {/* ====================================================
          INPUT
      ==================================================== */}

      <footer className="composer-wrapper">

        <div className="composer">

          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => {

              setInput(
                event.target.value
              );

              resizeTextarea();

            }}
            onKeyDown={
              handleKeyDown
            }
            placeholder="Ask me to book, cancel, reschedule, or find an appointment..."
            disabled={loading}
            rows={1}
          />

          {/* ==================================================
              VOICE BUTTON
          ================================================== */}

          <button
            type="button"
            className={
              isListening
                ? "voice-button listening"
                : "voice-button"
            }
            onClick={
              handleVoiceInput
            }
            disabled={loading}
            aria-label={
              isListening
                ? "Stop listening"
                : "Voice input"
            }
            title={
              isListening
                ? "Stop listening"
                : "Voice input"
            }
          >
            {isListening
              ? "⏹️"
              : "🎙️"}
          </button>

          {/* ==================================================
              SEND BUTTON
          ================================================== */}

          <button
            type="button"
            className="send-button"
            onClick={() =>
              handleSend()
            }
            disabled={
              loading ||
              !input.trim()
            }
            aria-label="Send message"
          >
            ➤
          </button>

        </div>

        <div className="composer-hint">

          {isListening
            ? "Listening... speak now"
            : "Enter to send · Shift + Enter for a new line"}

        </div>

      </footer>

    </div>
  );
}


// ============================================================
// MESSAGE RENDERING
// ============================================================

function renderMessage(
  text: string
) {

  const urlRegex =
    /(https?:\/\/[^\s]+)/g;

  const parts =
    text.split(
      urlRegex
    );

  return parts.map(
    (
      part,
      index
    ) => {

      if (
        part.match(
          urlRegex
        )
      ) {

        return (

          <a
            key={index}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            className="calendar-link"
          >
            Open in Google Calendar ↗
          </a>

        );
      }

      return (

        <span
          key={index}
        >
          {part}
        </span>

      );
    }
  );
}


// ============================================================
// APPOINTMENT SLOTS
// ============================================================

function AppointmentSlots({
  data,
  onSelect,
}: {
  data: SchedulingResponse;

  onSelect: (
    slot: AppointmentSlot
  ) => void;
}) {

  const slots =
    data.slots ||
    data.available_slots ||
    [];

  if (
    !slots.length
  ) {

    return null;
  }

  return (

    <div className="appointment-slots">

      <div className="slots-title">
        Available times
      </div>

      <div className="slots-list">

        {slots.map(
          (
            slot,
            index
          ) => {

            const start =
              new Date(
                slot.start
              );

            const end =
              new Date(
                slot.end
              );

            const startTime =
              start.toLocaleTimeString(
                [],
                {
                  hour: "numeric",
                  minute: "2-digit",
                }
              );

            const endTime =
              end.toLocaleTimeString(
                [],
                {
                  hour: "numeric",
                  minute: "2-digit",
                }
              );

            return (

              <button
                key={
                  `${slot.start}-${index}`
                }
                type="button"
                className="appointment-slot"
                onClick={() =>
                  onSelect(slot)
                }
              >
                {startTime}
                {" – "}
                {endTime}
              </button>

            );
          }
        )}

      </div>

    </div>
  );
}