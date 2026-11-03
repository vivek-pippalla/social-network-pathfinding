import { api } from "./api.js";
import { showMessage } from "./dom.js";
import { initAuth } from "./views/auth.js";
import { initPath } from "./views/path.js";
import { initSocial, loadFriends, loadSuggestions } from "./views/social.js";

const viewNames = ["auth", "dashboard", "path", "friends", "suggestions", "profile"];

function showView(name, moveFocus = true) {
  viewNames.forEach((view) => {
    const section = document.getElementById(`${view}-view`);
    if (section) section.hidden = view !== name;
  });
  document.querySelectorAll("[data-view]").forEach((button) => {
    if (button.matches("nav [data-view]")) {
      if (button.dataset.view === name) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    }
  });
  if (moveFocus) document.querySelector(`#${name}-title`)?.focus();
  if (name === "friends") loadFriends();
  if (name === "suggestions") loadSuggestions();
  if (name === "profile") loadProfile();
  history.replaceState(null, "", name === "dashboard" ? "#dashboard" : `#${name}`);
}

function signedOut(message = "Sign in to continue.") {
  document.getElementById("primary-nav").hidden = true;
  document.getElementById("logout").hidden = true;
  showView("auth", false);
  showMessage(message, "error");
}

async function signedIn() {
  document.getElementById("primary-nav").hidden = false;
  document.getElementById("logout").hidden = false;
  try {
    const profile = await api.me();
    document.getElementById("welcome-name").textContent = profile.name;
    void refreshFriendCount().catch(() => {
      document.getElementById("dashboard-friend-count").textContent = "—";
    });
    showView("dashboard");
    showMessage(`Signed in as ${profile.name}.`);
  } catch (error) {
    if (error.status !== 401) showMessage(error.message, "error");
  }
}

async function refreshFriendCount() {
  let offset = 0;
  let count = 0;
  let page;
  do {
    page = await api.friends(offset, 100);
    count += page.items.length;
    offset += page.items.length;
  } while (page.items.length === 100);
  document.getElementById("dashboard-friend-count").textContent = String(count);
}

async function loadProfile() {
  try {
    const profile = await api.me();
    document.getElementById("profile-name").value = profile.name;
    document.getElementById("profile-email").value = profile.email;
    document.getElementById("profile-id").textContent = profile.id;
  } catch (error) {
    showMessage(error.message, "error");
  }
}

initAuth(signedIn);
initPath();
initSocial();
document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.view));
});
document.getElementById("logout").addEventListener("click", () => {
  api.signOut();
  signedOut("You have signed out.");
});
window.addEventListener("session-expired", () => signedOut("Your session ended. Please sign in again."));
document.getElementById("profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  try {
    const profile = await api.updateMe({ name: document.getElementById("profile-name").value.trim() });
    document.getElementById("welcome-name").textContent = profile.name;
    showMessage("Profile updated.");
  } catch (error) {
    showMessage(error.message, "error");
  }
});

if (api.isSignedIn()) signedIn();
else showView("auth", false);

export { showView, signedOut };
