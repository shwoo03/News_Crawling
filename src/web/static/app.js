const $ = (selector) => document.querySelector(selector);
const toastEl = $("#toast");

const state = {
  sources: [],
  webhooks: [],
  routes: [],
  settings: { hasGroqApiKey: false },
};

document.addEventListener("DOMContentLoaded", () => {
  bindWebhookForm();
  bindRouteForm();
  bindGroqForm();
  bindReset();
  refresh();
});

async function refresh() {
  try {
    const snapshot = await api("GET", "/api/state");
    state.sources = snapshot.sources ?? [];
    state.webhooks = snapshot.webhooks ?? [];
    state.routes = snapshot.routes ?? [];
    state.settings = snapshot.settings ?? { hasGroqApiKey: false };
    render();
  } catch (error) {
    toast(error.message || "상태를 불러오지 못했습니다.", "error");
  }
}

function render() {
  renderMetaSummary();
  renderWebhooks();
  renderRouteForm();
  renderRoutes();
  renderGroqStatus();
}

function renderMetaSummary() {
  const active = state.routes.filter((route) => route.enabled).length;
  const total = state.routes.length;
  const groq = state.settings.hasGroqApiKey ? "Groq ready" : "Groq missing";
  $("#meta-summary").textContent =
    `${state.webhooks.length} webhook · ${active}/${total} active route · ${groq}`;
}

function renderWebhooks() {
  const container = $("#webhook-list");
  if (state.webhooks.length === 0) {
    container.innerHTML = `<div class="empty">등록된 디스코드 웹훅이 없습니다. 위에서 추가하세요.</div>`;
    return;
  }

  container.innerHTML = "";
  for (const webhook of state.webhooks) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div>
        <div class="card__label"></div>
        <div class="card__preview"></div>
      </div>
      <div class="card__actions">
        <button type="button" class="btn btn--small" data-action="edit">수정</button>
        <button type="button" class="btn btn--small btn--danger" data-action="delete">삭제</button>
      </div>
    `;
    card.querySelector(".card__label").textContent = webhook.label;
    card.querySelector(".card__preview").textContent = webhook.preview;

    card.querySelector('[data-action="edit"]').addEventListener("click", () => {
      editWebhook(webhook);
    });
    card.querySelector('[data-action="delete"]').addEventListener("click", () => {
      deleteWebhook(webhook);
    });

    container.appendChild(card);
  }
}

function renderRouteForm() {
  const sourceSelect = $("#route-source");
  const webhookSelect = $("#route-webhook");
  sourceSelect.innerHTML = "";
  webhookSelect.innerHTML = "";

  for (const source of state.sources) {
    const opt = document.createElement("option");
    opt.value = source.id;
    opt.textContent = source.name;
    sourceSelect.appendChild(opt);
  }

  if (state.webhooks.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "웹훅을 먼저 등록하세요";
    opt.disabled = true;
    opt.selected = true;
    webhookSelect.appendChild(opt);
    webhookSelect.disabled = true;
  } else {
    webhookSelect.disabled = false;
    for (const webhook of state.webhooks) {
      const opt = document.createElement("option");
      opt.value = String(webhook.id);
      opt.textContent = webhook.label;
      webhookSelect.appendChild(opt);
    }
  }
}

function renderRoutes() {
  const container = $("#route-list");
  if (state.routes.length === 0) {
    container.innerHTML = `<div class="empty">아직 라우트가 없습니다. 위 폼에서 추가하세요.</div>`;
    return;
  }

  container.innerHTML = "";
  for (const route of state.routes) {
    const source = state.sources.find((item) => item.id === route.sourceId);
    const webhook = state.webhooks.find((item) => item.id === route.webhookId);

    const row = document.createElement("div");
    row.className = "route";
    row.innerHTML = `
      <div class="route__cell">
        <span class="route__heading">Source</span>
        <span class="route__value"></span>
        <span class="route__meta"></span>
      </div>
      <div class="route__cell">
        <span class="route__heading">Webhook</span>
        <span class="route__value"></span>
        <span class="route__meta"></span>
      </div>
      <div class="route__interval">
        <span class="route__heading">주기 (분)</span>
        <input type="number" min="1" step="1" value="" />
      </div>
      <div class="route__actions">
        <label class="toggle" title="활성/비활성">
          <input type="checkbox" data-action="toggle" />
          <span class="toggle__track"></span>
          <span class="toggle__label"></span>
        </label>
        <button type="button" class="btn btn--small btn--danger" data-action="delete">삭제</button>
      </div>
    `;

    const cells = row.querySelectorAll(".route__cell");
    cells[0].querySelector(".route__value").textContent = source?.name ?? route.sourceId;
    cells[0].querySelector(".route__meta").textContent = source?.rssUrl ?? "unknown source";
    cells[1].querySelector(".route__value").textContent = webhook?.label ?? `webhook #${route.webhookId}`;
    cells[1].querySelector(".route__meta").textContent = webhook?.preview ?? "missing webhook";

    const intervalInput = row.querySelector("input[type='number']");
    intervalInput.value = String(route.pollIntervalMinutes);
    intervalInput.addEventListener("change", () => {
      const minutes = Number.parseInt(intervalInput.value, 10);
      if (!Number.isInteger(minutes) || minutes < 1) {
        intervalInput.value = String(route.pollIntervalMinutes);
        toast("주기는 1 이상의 정수여야 합니다.", "error");
        return;
      }
      updateRoute(route.id, { pollIntervalMinutes: minutes });
    });

    const toggle = row.querySelector('[data-action="toggle"]');
    toggle.checked = route.enabled;
    row.querySelector(".toggle__label").textContent = route.enabled ? "ON" : "OFF";
    toggle.addEventListener("change", () => {
      updateRoute(route.id, { enabled: toggle.checked });
    });

    row.querySelector('[data-action="delete"]').addEventListener("click", () => {
      deleteRoute(route.id);
    });

    container.appendChild(row);
  }
}

function renderGroqStatus() {
  const el = $("#groq-status");
  el.textContent = state.settings.hasGroqApiKey
    ? "Groq API 키가 저장되어 있습니다."
    : "Groq API 키가 비어 있습니다. 워커는 키가 없을 때 발송을 건너뜁니다.";
}

function bindWebhookForm() {
  $("#webhook-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const label = $("#webhook-label").value.trim();
    const url = $("#webhook-url").value.trim();
    if (!label || !url) {
      toast("라벨과 URL을 모두 입력하세요.", "error");
      return;
    }
    try {
      await api("POST", "/api/webhooks", { label, url });
      $("#webhook-label").value = "";
      $("#webhook-url").value = "";
      toast("웹훅을 추가했습니다.");
      await refresh();
    } catch (error) {
      toast(translateError(error), "error");
    }
  });
}

async function editWebhook(webhook) {
  const nextLabel = window.prompt("라벨 변경", webhook.label);
  if (nextLabel === null) return;
  const nextUrl = window.prompt("URL 변경", webhook.url);
  if (nextUrl === null) return;

  try {
    await api("PATCH", `/api/webhooks/${webhook.id}`, {
      label: nextLabel.trim(),
      url: nextUrl.trim(),
    });
    toast("웹훅을 수정했습니다.");
    await refresh();
  } catch (error) {
    toast(translateError(error), "error");
  }
}

async function deleteWebhook(webhook) {
  const linkedRoutes = state.routes.filter((route) => route.webhookId === webhook.id).length;
  const message = linkedRoutes > 0
    ? `이 웹훅을 사용하는 라우트 ${linkedRoutes}개가 함께 삭제됩니다. 계속할까요?`
    : `웹훅 "${webhook.label}"을 삭제할까요?`;
  if (!window.confirm(message)) return;

  try {
    await api("DELETE", `/api/webhooks/${webhook.id}`);
    toast("웹훅을 삭제했습니다.");
    await refresh();
  } catch (error) {
    toast(translateError(error), "error");
  }
}

function bindRouteForm() {
  $("#route-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const sourceId = $("#route-source").value;
    const webhookId = Number($("#route-webhook").value);
    const minutes = Number.parseInt($("#route-interval").value, 10);
    if (!sourceId) {
      toast("소스를 선택하세요.", "error");
      return;
    }
    if (!Number.isInteger(webhookId) || webhookId <= 0) {
      toast("웹훅을 선택하세요.", "error");
      return;
    }
    if (!Number.isInteger(minutes) || minutes < 1) {
      toast("주기는 1 이상의 정수여야 합니다.", "error");
      return;
    }

    try {
      await api("POST", "/api/routes", {
        sourceId,
        webhookId,
        pollIntervalMinutes: minutes,
        enabled: true,
      });
      toast("라우트를 추가했습니다.");
      await refresh();
    } catch (error) {
      toast(translateError(error), "error");
    }
  });
}

async function updateRoute(id, patch) {
  try {
    await api("PATCH", `/api/routes/${id}`, patch);
    toast("라우트를 업데이트했습니다.");
    await refresh();
  } catch (error) {
    toast(translateError(error), "error");
  }
}

async function deleteRoute(id) {
  if (!window.confirm("이 라우트를 삭제할까요?")) return;
  try {
    await api("DELETE", `/api/routes/${id}`);
    toast("라우트를 삭제했습니다.");
    await refresh();
  } catch (error) {
    toast(translateError(error), "error");
  }
}

function bindGroqForm() {
  $("#groq-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const apiKey = $("#groq-key").value.trim();
    if (!apiKey) {
      toast("Groq API 키를 입력하세요.", "error");
      return;
    }
    try {
      await api("PUT", "/api/settings/groq", { apiKey });
      $("#groq-key").value = "";
      toast("Groq API 키를 저장했습니다.");
      await refresh();
    } catch (error) {
      toast(translateError(error), "error");
    }
  });

  $("#groq-clear").addEventListener("click", async () => {
    if (!window.confirm("저장된 Groq API 키를 삭제할까요?")) return;
    try {
      await api("DELETE", "/api/settings/groq");
      toast("Groq API 키를 삭제했습니다.");
      await refresh();
    } catch (error) {
      toast(translateError(error), "error");
    }
  });
}

function bindReset() {
  $("#reset-all").addEventListener("click", async () => {
    if (!window.confirm("모든 웹훅과 라우트, Groq API 키를 삭제합니다. 계속할까요?")) {
      return;
    }
    if (!window.confirm("정말로 초기화할까요? 되돌릴 수 없습니다.")) {
      return;
    }
    try {
      await api("POST", "/api/reset");
      toast("초기화 완료.");
      await refresh();
    } catch (error) {
      toast(translateError(error), "error");
    }
  });
}

async function api(method, path, body) {
  const init = {
    method,
    headers: { "content-type": "application/json" },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const response = await fetch(path, init);
  const text = await response.text();
  const payload = text ? safeParse(text) : null;

  if (!response.ok) {
    const message = payload?.error ?? `HTTP ${response.status}`;
    const error = new Error(message);
    error.code = payload?.error;
    throw error;
  }

  return payload;
}

function safeParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function translateError(error) {
  const code = error.code ?? error.message;
  switch (code) {
    case "invalid_discord_webhook_url":
      return "디스코드 웹훅 URL 형식이 아닙니다. (https://discord.com/api/webhooks/…)";
    case "label_required":
      return "라벨이 필요합니다.";
    case "unknown_source":
      return "알 수 없는 소스입니다.";
    case "unknown_webhook":
      return "알 수 없는 웹훅입니다.";
    case "invalid_interval":
      return "주기는 1 이상의 정수여야 합니다.";
    case "api_key_required":
      return "API 키가 필요합니다.";
    case "webhook_not_found":
      return "웹훅을 찾을 수 없습니다.";
    case "route_not_found":
      return "라우트를 찾을 수 없습니다.";
    default:
      return error.message || "요청을 처리하지 못했습니다.";
  }
}

let toastTimer;
function toast(message, kind = "info") {
  toastEl.textContent = message;
  toastEl.classList.toggle("toast--error", kind === "error");
  toastEl.classList.add("toast--visible");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.classList.remove("toast--visible");
  }, 2400);
}
