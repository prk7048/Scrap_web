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
  status.textContent = "설정을 저장했습니다.";
});

button.addEventListener("click", async () => {
  button.disabled = true;
  try {
    status.textContent = "저장 중...";
    const settings = await loadSettings();
    if (!settings.token) {
      status.textContent = "확장 토큰을 먼저 입력하세요.";
      return;
    }
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab.url) {
      status.textContent = "URL을 찾지 못했습니다.";
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
    status.textContent = response.ok ? "저장 대기열에 추가했습니다." : "저장에 실패했습니다. 백엔드 URL과 토큰을 확인하세요.";
  } catch {
    status.textContent = "저장에 실패했습니다. 아카이브가 실행 중인지 확인하세요.";
  } finally {
    button.disabled = false;
  }
});

void hydrateSettings();
