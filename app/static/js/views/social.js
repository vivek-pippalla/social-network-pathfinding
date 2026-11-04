import { api } from "../api.js";
import { element, emptyState, showMessage } from "../dom.js";

let friendOffset = 0;
let suggestionOffset = 0;

export function initSocial() {
  document.getElementById("search-form").addEventListener("submit", searchUsers);
  document.getElementById("friends-more").addEventListener("click", loadFriends);
  document.getElementById("suggestions-more").addEventListener("click", loadSuggestions);
}

export async function loadFriends(reset = true) {
  const list = document.getElementById("friend-list");
  const more = document.getElementById("friends-more");
  if (reset) {
    friendOffset = 0;
    list.replaceChildren(element("p", "muted", "Loading friends…"));
  }
  try {
    const page = await api.friends(friendOffset);
    if (reset) list.replaceChildren();
    if (!page.items.length && reset) list.append(emptyState("No friends yet. Search for someone to add."));
    page.items.forEach((user) => list.append(userCard(user, { remove: true })));
    friendOffset += page.items.length;
    more.hidden = page.items.length < 20;
  } catch (error) {
    list.replaceChildren(emptyState(error.message));
    showMessage(error.message, "error");
  }
}

export async function loadSuggestions(reset = true) {
  const list = document.getElementById("suggestion-list");
  const more = document.getElementById("suggestions-more");
  if (reset) {
    suggestionOffset = 0;
    list.replaceChildren(element("p", "muted", "Finding introductions…"));
  }
  try {
    const page = await api.mySuggestions(suggestionOffset);
    if (reset) list.replaceChildren();
    if (!page.items.length && reset) list.append(emptyState("No suggestions yet. Add a few friends first."));
    page.items.forEach((suggestion) => {
      list.append(userCard({ id: suggestion.user_id, name: suggestion.name }, {
        detail: `${suggestion.mutual_friends} mutual ${suggestion.mutual_friends === 1 ? "friend" : "friends"}`,
        add: true,
        mutual: true,
      }));
    });
    suggestionOffset += page.items.length;
    more.hidden = page.items.length < 20;
  } catch (error) {
    list.replaceChildren(emptyState(error.message));
    showMessage(error.message, "error");
  }
}

async function searchUsers(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const query = document.getElementById("search-query").value.trim();
  const results = document.getElementById("search-results");
  results.replaceChildren(element("p", "muted", "Searching…"));
  try {
    const page = await api.search(query);
    if (!page.items.length) {
      results.replaceChildren(emptyState("No people found. Try another name."));
      return;
    }
    results.replaceChildren(...page.items.map((user) => userCard(user, { add: true })));
  } catch (error) {
    results.replaceChildren(emptyState(error.message));
    showMessage(error.message, "error");
  }
}

function userCard(user, options = {}) {
  const card = element("article", "user-card");
  const meta = element("div", "person-meta");
  meta.append(element("span", "person-name", user.name || `User ${user.id}`));
  meta.append(element("p", "", `ID ${user.id}${user.source ? ` · ${user.source}` : ""}`));
  if (options.detail) meta.append(element("p", "", options.detail));
  card.append(meta);
  if (options.add) {
    const button = element("button", "button button-primary", "Add friend");
    button.type = "button";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const result = await api.addFriend(user.id);
        button.textContent = result.created ? "Added" : "Already friends";
        showMessage(result.created ? `${user.name || user.id} added to friends.` : "You are already friends.");
        await loadFriends();
      } catch (error) {
        button.disabled = false;
        showMessage(error.message, "error");
      }
    });
    card.append(button);
  }
  if (options.remove) {
    const button = element("button", "button button-quiet", "Remove");
    button.type = "button";
    button.setAttribute("aria-label", `Remove ${user.name || user.id} from friends`);
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await api.removeFriend(user.id);
        card.remove();
        showMessage(`${user.name || user.id} removed from friends.`);
      } catch (error) {
        button.disabled = false;
        showMessage(error.message, "error");
      }
    });
    card.append(button);
  }
  if (options.mutual) {
    const button = element("button", "button button-quiet", "View mutual friends");
    button.type = "button";
    button.addEventListener("click", () => showMutual(user));
    card.append(button);
  }
  return card;
}

async function showMutual(user) {
  const panel = document.getElementById("mutual-panel");
  const list = document.getElementById("mutual-list");
  document.getElementById("mutual-title").textContent = `Mutual friends with ${user.name || user.id}`;
  panel.hidden = false;
  list.replaceChildren(element("p", "muted", "Loading mutual friends…"));
  try {
    const page = await api.mutual(user.id);
    list.replaceChildren(...(page.items.length ? page.items.map((person) => userCard(person)) : [emptyState("No mutual friends yet.")]));
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    list.replaceChildren(emptyState(error.message));
    showMessage(error.message, "error");
  }
}
