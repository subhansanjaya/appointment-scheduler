const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";


export type ChatResponse = {
  response?: string | SchedulingResponse;
  error?: string;
};


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

  needs_input?: boolean;
};


export async function sendMessage(
  message: string
): Promise<ChatResponse> {

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
      }
    );


  const data =
    await response.json();


  if (!response.ok) {

    return {
      error:
        data?.error ||
        "Something went wrong.",
    };
  }


  return data;
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


  return response.json();
}