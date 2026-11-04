import { api } from "../api.js";
import { element, emptyState, showMessage } from "../dom.js";

let network;

export function initPath() {
  setupPicker("path-start", "path-start-options");
  setupPicker("path-end", "path-end-options");
  document.getElementById("path-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    const rawStart = document.getElementById("path-start").value.trim();
    const rawEnd = document.getElementById("path-end").value.trim();
    const result = document.getElementById("path-result");
    const graph = document.getElementById("path-network");
    result.replaceChildren(element("p", "muted", "Looking for the shortest connection…"));
    graph.hidden = true;
    try {
      const [start, end] = await Promise.all([resolveUser(rawStart), resolveUser(rawEnd)]);
      const data = await api.path(start, end);
      const details = element("div", "path-meta");
      details.append(element("span", "pill", `${data.hops} ${data.hops === 1 ? "hop" : "hops"}`));
      details.append(element("span", "pill", data.cached ? "Cached result" : "Fresh result"));
      const chain = element("div", "path-chain");
      data.path.forEach((person, index) => {
        if (index) chain.append(element("span", "path-arrow", "→"));
        const label = person.name ? `${person.name} · ${person.id}` : person.id;
        chain.append(element("span", "path-person", label));
      });
      result.replaceChildren(details, chain);
      graph.hidden = false;
      drawGraph(data.path, graph);
      showMessage("Shortest path found.");
    } catch (error) {
      result.replaceChildren(emptyState(error.message));
      showMessage(error.message, "error");
    }
  });
}

function setupPicker(inputId, listId) {
  const input = document.getElementById(inputId);
  const list = document.getElementById(listId);
  let timer;
  let searchNumber = 0;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    const query = input.value.trim();
    if (query.length < 2) {
      list.replaceChildren();
      return;
    }
    const current = ++searchNumber;
    timer = setTimeout(async () => {
      try {
        const page = await api.search(query);
        if (current !== searchNumber) return;
        list.replaceChildren(...page.items.map((user) => {
          const option = document.createElement("option");
          option.value = `${user.name} [${user.id}]`;
          return option;
        }));
      } catch {
        // The path form reports actionable errors when the user submits.
      }
    }, 250);
  });
}

async function resolveUser(value) {
  const selected = value.match(/ \[([A-Za-z0-9_-]{1,64})\]$/);
  if (selected) return selected[1];
  if (value.length >= 2) {
    const page = await api.search(value);
    const exact = page.items.filter((user) => user.name.toLocaleLowerCase() === value.toLocaleLowerCase());
    if (exact.length === 1) return exact[0].id;
    if (exact.length > 1) throw new Error("More than one person has that name. Choose a name and ID from the suggestions.");
  }
  if (/^[A-Za-z0-9_-]{1,64}$/.test(value)) return value;
  throw new Error("Choose a person from the name suggestions or enter a valid user ID.");
}

function drawGraph(path, target) {
  if (!window.vis?.Network || !window.vis?.DataSet) {
    target.textContent = path.map((person) => person.name || person.id).join(" → ");
    target.setAttribute("role", "group");
    return;
  }
  if (network) network.destroy();
  const nodes = new window.vis.DataSet(path.map((person, index) => ({
    id: person.id,
    label: person.name || person.id,
    color: index === 0 ? "#9de1cf" : index === path.length - 1 ? "#f5a5a5" : "#a8a7ee",
    font: { color: "#111116", size: 16 },
    shape: "dot",
    size: 24,
  })));
  const edges = new window.vis.DataSet(path.slice(1).map((person, index) => ({
    id: `${path[index].id}-${person.id}`,
    from: path[index].id,
    to: person.id,
    arrows: "to",
    color: "#9de1cf",
  })));
  network = new window.vis.Network(target, { nodes, edges }, {
    physics: false,
    layout: { hierarchical: { enabled: true, direction: "LR", sortMethod: "directed" } },
    interaction: { keyboard: true, hover: true },
  });
}
