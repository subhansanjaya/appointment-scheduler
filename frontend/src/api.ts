const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";


// ============================================================
// TYPES
// ============================================================

export type AppointmentSlot = {
  start: string;
  end: string;
};

export type SchedulingResponse = {
  success: boolean;

  message?: string;

  slots?: AppointmentSlot[];

  available_slots?: AppointmentSlot[];

  start?: string;

  end?: string;

  event_id?: string;

  link?: string;

  status?: string;

  needs_input?: boolean;
};

export type ChatResponse = {
  response?: string | SchedulingResponse;

  error?: string;
};


// ============================================================
// CHAT
// ============================================================

export async function sendMessage(
  message: string
): Promise<ChatResponse> {

  const controller =
    new AbortController();

  // This is intentionally longer than the current
  // Lambda execution time (~79 seconds).
  //
  // IMPORTANT:
  // This does NOT increase API Gateway's timeout.
  // It only prevents the browser from giving up too early.
  const timeoutId =
    window.setTimeout(() => {

      controller.abort();

    }, 120000);


  try {

    console.log(
      "Sending chat request:",
      message
    );

    const response =
      await fetch(
        `${API_BASE_URL}/chat`,
        {
          method: "POST",

          credentials: "include",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            message,
          }),

          signal:
            controller.signal,
        }
      );


    // --------------------------------------------------------
    // Read response safely
    // --------------------------------------------------------

    const contentType =
      response.headers.get(
        "content-type"
      );

    let data: any = null;


    if (
      contentType?.includes(
        "application/json"
      )
    ) {

      data =
        await response.json();

    } else {

      const text =
        await response.text();

      console.error(
        "Non-JSON API response:",
        text
      );

      return {
        error:
          `Server returned ${response.status}: ${text || "Unknown error"}`,
      };
    }


    console.log(
      "Chat API response:",
      data
    );


    // --------------------------------------------------------
    // HTTP error
    // --------------------------------------------------------

    if (!response.ok) {

      return {
        error:
          data?.error ||
          data?.response?.message ||
          `Server returned ${response.status}.`,
      };
    }


    // --------------------------------------------------------
    // Backend error returned with HTTP 200
    // --------------------------------------------------------

    if (
      data?.error
    ) {

      return {
        error:
          data.error,
      };
    }


    // --------------------------------------------------------
    // Successful response
    // --------------------------------------------------------

    return data;

  } catch (error) {

    console.error(
      "Chat API error:",
      error
    );


    if (
      error instanceof DOMException &&
      error.name === "AbortError"
    ) {

      return {
        error:
          "The scheduling service took too long to respond. Please try again.",
      };
    }


    return {
      error:
        "Unable to connect to the scheduling service.",
    };

  } finally {

    window.clearTimeout(
      timeoutId
    );

  }
}


// ============================================================
// CURRENT USER
// ============================================================

export async function getCurrentUser() {

  const response =
    await fetch(
      `${API_BASE_URL}/auth/me`,
      {
        credentials: "include",
      }
    );


  if (!response.ok) {

    throw new Error(
      `Authentication request failed: ${response.status}`
    );
  }


  return response.json();
}


// ============================================================
// LOGOUT
// ============================================================

export async function logout() {

  const response =
    await fetch(
      `${API_BASE_URL}/auth/logout`,
      {
        method: "POST",

        credentials: "include",
      }
    );


  if (!response.ok) {

    throw new Error(
      `Logout request failed: ${response.status}`
    );
  }


  return response.json();
}