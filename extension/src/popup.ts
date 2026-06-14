const status = document.querySelector<HTMLParagraphElement>("#status")!;
const button = document.querySelector<HTMLButtonElement>("#save")!;
const settingsForm = document.querySelector<HTMLFormElement>("#settings")!;
const backendUrlInput = document.querySelector<HTMLInputElement>("#backend-url")!;
const tokenInput = document.querySelector<HTMLInputElement>("#token")!;

type PopupSettings = {
  backendUrl: string;
  token: string;
};

const defaultSettings: PopupSettings = {
  backendUrl: "http://localhost:8000",
  token: "",
};

function normalizeBackendUrl(value: string): string {
  return value.trim().replace(/\/+$/, "") || defaultSettings.backendUrl;
}

async function loadSettings(): Promise<PopupSettings> {
  const stored = await chrome.storage.local.get(defaultSettings);
  return {
    backendUrl: normalizeBackendUrl(String(stored.backendUrl ?? defaultSettings.backendUrl)),
    token: String(stored.token ?? ""),
  };
}

async function saveSettings(settings: PopupSettings): Promise<void> {
  await chrome.storage.local.set(settings);
}

async function hydrateSettings() {
  const settings = await loadSettings();
  backendUrlInput.value = settings.backendUrl;
  tokenInput.value = settings.token;
}

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveSettings({
    backendUrl: normalizeBackendUrl(backendUrlInput.value),
    token: tokenInput.value.trim(),
  });
  status.textContent = "Settings saved.";
});

button.addEventListener("click", async () => {
  button.disabled = true;
  try {
    status.textContent = "Saving...";
    const settings = await loadSettings();
    if (!settings.token) {
      status.textContent = "Add an extension token first.";
      return;
    }
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab.url) {
      status.textContent = "No URL found.";
      return;
    }
    const response = await fetch(`${settings.backendUrl}/api/items/save`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${settings.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url: tab.url }),
    });
    status.textContent = response.ok ? "Saved to queue." : "Save failed. Check the backend URL and token.";
  } catch {
    status.textContent = "Save failed. Is the archive running?";
  } finally {
    button.disabled = false;
  }
});

void hydrateSettings();
