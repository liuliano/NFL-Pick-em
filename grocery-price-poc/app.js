const DEFAULT_LIST = [
  "whole milk 1 gallon",
  "large eggs 12 count",
  "boneless chicken breast",
  "bananas",
  "sandwich bread"
].join("\n");

const listEl = document.querySelector("#shoppingList");
const messageEl = document.querySelector("#message");
const resultsEl = document.querySelector("#results");
const summaryEl = document.querySelector("#summary");

listEl.value = localStorage.getItem("grocery-list-33579") || DEFAULT_LIST;

document.querySelector("#saveButton").addEventListener("click", () => {
  localStorage.setItem("grocery-list-33579", listEl.value.trim());
  messageEl.textContent = "Shopping list saved on this phone.";
});

document.querySelector("#copyButton").addEventListener("click", async () => {
  const items = listEl.value.split("\n").map(v => v.trim()).filter(Boolean);
  await navigator.clipboard.writeText(items.join(" | "));
  messageEl.textContent = "Copied. Paste it into the shopping_list field when you run the workflow.";
});

function money(value) {
  return typeof value === "number" ? `$${value.toFixed(2)}` : "—";
}

function render(data) {
  const results = Array.isArray(data.results) ? data.results : [];
  const available = results.flatMap(item => item.offers || []).filter(o => Number.isFinite(o.price));
  summaryEl.innerHTML = `
    <div class="summary-card"><span>Last refreshed</span><strong>${data.updatedAt ? new Date(data.updatedAt).toLocaleString() : "Not yet"}</strong></div>
    <div class="summary-card"><span>Offers found</span><strong>${available.length}</strong></div>`;

  if (!results.length) {
    resultsEl.innerHTML = '<div class="panel empty">No results yet. Run the GitHub Actions refresh, then reload this page.</div>';
    return;
  }

  resultsEl.innerHTML = results.map(item => {
    const offers = [...(item.offers || [])].sort((a,b) => (a.unitPrice ?? a.price ?? Infinity) - (b.unitPrice ?? b.price ?? Infinity));
    return `<article class="card">
      <h2>${escapeHtml(item.query)}</h2>
      ${offers.length ? offers.map((offer, index) => `
        <div class="offer">
          <div><div class="store">${escapeHtml(offer.store)}${index === 0 ? " · Best value" : ""}</div><div class="product">${escapeHtml(offer.product || "No matching product")}</div></div>
          <div class="price">${money(offer.price)}<div class="unit">${offer.unitLabel ? `${money(offer.unitPrice)} ${escapeHtml(offer.unitLabel)}` : ""}</div></div>
        </div>`).join("") : '<div class="product">No offers captured.</div>'}
    </article>`;
  }).join("");
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
}

fetch(`data/prices.json?ts=${Date.now()}`)
  .then(response => response.ok ? response.json() : Promise.reject(new Error("No data")))
  .then(render)
  .catch(() => render({ results: [] }));
