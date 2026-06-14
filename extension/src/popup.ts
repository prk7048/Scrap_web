const status = document.querySelector<HTMLParagraphElement>("#status")!;
const button = document.querySelector<HTMLButtonElement>("#save")!;

button.addEventListener("click", async () => {
  status.textContent = "Saving...";
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab.url) {
    status.textContent = "No URL found.";
    return;
  }
  const response = await fetch("http://localhost:8000/api/items/save", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: tab.url }),
  });
  status.textContent = response.ok ? "Saved to queue." : "Save failed. Open the archive app and log in.";
});
