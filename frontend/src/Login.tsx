import "./App.css";

const API_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

export default function Login() {
  const handleGoogleLogin = () => {
    window.location.href = `${API_URL}/auth/google`;
  };

  

  return (
    <div className="login-page">
      <div className="login-card">

        <div className="login-icon">
          📅
        </div>

        <h1>
          AI Scheduling Assistant
        </h1>

        <p className="login-description">
          Schedule, manage, cancel and
          reschedule your appointments
          using natural language.
        </p>

        <button
          className="google-login-button"
          onClick={handleGoogleLogin}
        >
          <span className="google-icon">
            G
          </span>

          Continue with Google
        </button>

        <p className="login-footer">
          Your appointments are managed
          through your Google Calendar.
        </p>

      </div>
    </div>
  );
}