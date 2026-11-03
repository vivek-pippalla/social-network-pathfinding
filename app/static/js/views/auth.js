import { api } from "../api.js";
import { showMessage } from "../dom.js";

let registering = false;

export function initAuth(onSignedIn) {
  const form = document.getElementById("auth-form");
  const nameField = document.getElementById("name-field");
  const nameInput = document.getElementById("auth-name");
  const password = document.getElementById("auth-password");
  const loginButton = document.getElementById("show-login");
  const registerButton = document.getElementById("show-register");
  const setMode = (isRegistering) => {
    registering = isRegistering;
    nameField.hidden = !registering;
    nameInput.required = registering;
    password.autocomplete = registering ? "new-password" : "current-password";
    loginButton.setAttribute("aria-pressed", String(!registering));
    registerButton.setAttribute("aria-pressed", String(registering));
    form.querySelector("button[type=submit]").textContent = registering ? "Create account" : "Sign in";
    showMessage("");
  };
  loginButton.addEventListener("click", () => setMode(false));
  registerButton.addEventListener("click", () => setMode(true));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = form.querySelector("button[type=submit]");
    if (!form.reportValidity()) return;
    submit.disabled = true;
    try {
      const email = document.getElementById("auth-email").value.trim();
      const secret = password.value;
      const result = registering
        ? await api.register({ name: nameInput.value.trim(), email, password: secret })
        : await api.login(email, secret);
      api.setToken(result);
      password.value = "";
      await onSignedIn();
    } catch (error) {
      showMessage(error.message, "error");
    } finally {
      submit.disabled = false;
    }
  });
  setMode(false);
}
