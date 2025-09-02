<script src="script.js"></script>
const API_URL = "http://127.0.0.1:5000";

// Handle registration
document.getElementById("register-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const firstName = document.getElementById("first_name").value;
  const lastName = document.getElementById("last_name").value;
  const email = document.getElementById("register-email").value;
  const password = document.getElementById("register-password").value;

  const res = await fetch(`${API_URL}/api/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ first_name: firstName, last_name: lastName, email, password })
  });

  const data = await res.json();
  alert(data.message);
});

// Handle login
document.getElementById("login-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;

  const res = await fetch(`${API_URL}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      username: email.split("@")[0],  // simple username from email
      email,
      password
    })
  });

const data = await res.json();
alert(data.message || data.error);

 

  if (data.success) {
    // Example: redirect to dashboard
    window.location.href = "/dashboard.html";
  }
});

// Handle mood entry
document.getElementById("mood-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const moodLabel = document.getElementById("mood-label").value;
  const moodValue = document.getElementById("mood-value").value;
  const moodNote = document.getElementById("mood-note").value;

  const res = await fetch(`${API_URL}/api/mood-entry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ mood_label: moodLabel, mood_value: moodValue, mood_note: moodNote })
  });

  const data = await res.json();
  alert(data.message);
});
