export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function replaceChildren(target, ...children) {
  target.replaceChildren(...children);
}

export function emptyState(message) {
  return element("p", "empty-state", message);
}

export function showMessage(message, kind = "info") {
  const status = document.getElementById("status");
  status.textContent = message;
  status.dataset.kind = kind;
}
