const API_URL = import.meta.env.VITE_API_URL;

export async function sendMessage(
  message: string
): Promise<{ response: string }> {

  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",

    credentials: "include",

    headers: {
      "Content-Type": "application/json",
    },

    body: JSON.stringify({ message }),
  });

  return res.json();
}