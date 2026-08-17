const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "content-type",
    "access-control-allow-methods": "POST, OPTIONS",
  },
});

const text = (value) => String(value || "").trim();
const deviceKey = (id) => `device:${id}`;
const otpKey = (id) => `otp:${id}`;

function validDeviceId(id) {
  return /^\d{6}$/.test(id);
}

async function digest(value) {
  const bytes = new TextEncoder().encode(value);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

function makeOtp() {
  const value = crypto.getRandomValues(new Uint32Array(1))[0] % 1000000;
  return String(value).padStart(6, "0");
}

async function telegram(env, method, body) {
  const response = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error("Telegram request failed");
  return response.json();
}

async function issueCode(env, id, chatId) {
  const code = makeOtp();
  await env.LOCK_KV.put(otpKey(id), JSON.stringify({
    hash: await digest(code),
    expiresAt: Date.now() + 5 * 60 * 1000,
  }), { expirationTtl: 300 });
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: `Одноразовый код для ${id}: ${code}\nКод действует 5 минут.`,
  });
}

async function handleTelegram(request, env) {
  if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
    return new Response("Not found", { status: 404 });
  }
  const update = await request.json();
  const message = update.message;
  if (!message || !message.chat) return json({ ok: true });

  const parts = text(message.text).split(/\s+/);
  const command = parts[0]?.split("@")[0];
  const id = text(parts[1]).toUpperCase();
  if (!["/start", "/code"].includes(command)) return json({ ok: true });
  if (!validDeviceId(id)) {
    await telegram(env, "sendMessage", {
      chat_id: message.chat.id,
      text: "Отправьте команду в формате: /start 123456",
    });
    return json({ ok: true });
  }

  const key = deviceKey(id);
  const record = await env.LOCK_KV.get(key, "json");
  if (!record) {
    await telegram(env, "sendMessage", {
      chat_id: message.chat.id,
      text: "Этот PC-ID ещё не зарегистрирован в приложении.",
    });
    return json({ ok: true });
  }

  const chatId = String(message.chat.id);
  if (record.chatId && record.chatId !== chatId) {
    await telegram(env, "sendMessage", {
      chat_id: message.chat.id,
      text: "Этот PC-ID уже привязан к другому Telegram-чату.",
    });
    return json({ ok: true });
  }

  record.chatId = chatId;
  await env.LOCK_KV.put(key, JSON.stringify(record));
  await issueCode(env, id, chatId);
  return json({ ok: true });
}

async function handleApi(request, env, url) {
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);
  const body = await request.json().catch(() => null);
  const id = text(body?.device_id).toUpperCase();
  if (!validDeviceId(id)) return json({ error: "Invalid device_id" }, 400);

  if (url.pathname === "/api/register") {
    const key = deviceKey(id);
    const existing = await env.LOCK_KV.get(key, "json");
    if (!existing) {
      await env.LOCK_KV.put(key, JSON.stringify({
        chatId: null,
        createdAt: new Date().toISOString(),
      }));
    }
    return json({ ok: true, device_id: id });
  }

  if (url.pathname === "/api/verify") {
    const code = text(body?.code);
    const saved = await env.LOCK_KV.get(otpKey(id), "json");
    if (!saved || saved.expiresAt < Date.now() || !(await digest(code) === saved.hash)) {
      return json({ ok: false, error: "Invalid or expired code" }, 401);
    }
    await env.LOCK_KV.delete(otpKey(id));
    return json({ ok: true });
  }

  return json({ error: "Not found" }, 404);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return json({ ok: true });
    try {
      if (url.pathname === "/health") return json({ ok: true });
      if (url.pathname === "/telegram/webhook") return await handleTelegram(request, env);
      if (url.pathname.startsWith("/api/")) return await handleApi(request, env, url);
      return json({ error: "Not found" }, 404);
    } catch (_) {
      return json({ error: "Internal server error" }, 500);
    }
  },
};
