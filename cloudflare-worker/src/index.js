const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { "content-type": "application/json; charset=utf-8" },
});

const text = (value) => String(value || "").trim();
const deviceKey = (id) => `device:${id}`;
const otpKey = (id) => `otp:${id}`;
const attemptKey = (id) => `attempts:${id}`;

function validDeviceId(id) {
  return /^\d{6}$/.test(id);
}

async function digest(value) {
  const bytes = new TextEncoder().encode(value);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

function equalConstantTime(left, right) {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function makeOtp() {
  const limit = 4294000000;
  let value;
  do {
    value = crypto.getRandomValues(new Uint32Array(1))[0];
  } while (value >= limit);
  return String(value % 1000000).padStart(6, "0");
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

function localized(language, russian, english) {
  return language === "en" ? english : russian;
}

async function issueCode(env, id, chatId, language) {
  const code = makeOtp();
  await env.LOCK_KV.put(otpKey(id), JSON.stringify({
    hash: await digest(code),
    expiresAt: Date.now() + 5 * 60 * 1000,
  }), { expirationTtl: 300 });
  await env.LOCK_KV.delete(attemptKey(id));
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: language === "en"
      ? `One-time code for ${id}: ${code}\nThe code is valid for 5 minutes.`
      : `Одноразовый код для ${id}: ${code}\nКод действует 5 минут.`,
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
  const id = text(parts[1]);
  if (!["/start", "/code"].includes(command)) return json({ ok: true });
  if (!validDeviceId(id)) {
    await telegram(env, "sendMessage", { chat_id: message.chat.id, text: "Формат: /start 123456" });
    return json({ ok: true });
  }

  const key = deviceKey(id);
  const record = await env.LOCK_KV.get(key, "json");
  if (!record) {
    await telegram(env, "sendMessage", { chat_id: message.chat.id, text: "This PC-ID is not registered or has expired." });
    return json({ ok: true });
  }

  const chatId = String(message.chat.id);
  const language = record.language === "en" ? "en" : "ru";
  if (record.chatId && record.chatId !== chatId) {
    await telegram(env, "sendMessage", { chat_id: message.chat.id, text: localized(language, "Этот PC-ID уже привязан к другому Telegram-чату.", "This PC-ID is already linked to another Telegram chat.") });
    return json({ ok: true });
  }

  record.chatId = chatId;
  await env.LOCK_KV.put(key, JSON.stringify(record), { expirationTtl: 2592000 });
  await issueCode(env, id, chatId, language);
  return json({ ok: true });
}

async function handleApi(request, env, url) {
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);
  const body = await request.json().catch(() => null);
  const id = text(body?.device_id);
  if (!validDeviceId(id)) return json({ error: "Invalid device_id" }, 400);

  if (url.pathname === "/api/register") {
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const ipKey = `register-ip:${await digest(ip)}`;
    const requestCount = Number(await env.LOCK_KV.get(ipKey) || "0");
    if (requestCount >= 30) return json({ error: "Too many registration requests" }, 429);
    await env.LOCK_KV.put(ipKey, String(requestCount + 1), { expirationTtl: 3600 });
    const key = deviceKey(id);
    const existing = await env.LOCK_KV.get(key, "json");
    const language = body?.language === "en" ? "en" : "ru";
    if (!existing) {
      await env.LOCK_KV.put(key, JSON.stringify({ chatId: null, language, createdAt: new Date().toISOString() }), { expirationTtl: 86400 });
    }
    return json({ ok: true, device_id: id });
  }

  if (url.pathname === "/api/verify") {
    const code = text(body?.code);
    const attempts = Number(await env.LOCK_KV.get(attemptKey(id)) || "0");
    if (attempts >= 5) return json({ ok: false, error: "Слишком много попыток. Запросите новый код." }, 429);
    const saved = await env.LOCK_KV.get(otpKey(id), "json");
    const valid = saved && saved.expiresAt >= Date.now() && equalConstantTime(await digest(code), saved.hash);
    if (!valid) {
      await env.LOCK_KV.put(attemptKey(id), String(attempts + 1), { expirationTtl: 300 });
      return json({ ok: false, error: "Неверный или просроченный код" }, 401);
    }
    await env.LOCK_KV.delete(otpKey(id));
    await env.LOCK_KV.delete(attemptKey(id));
    return json({ ok: true });
  }

  return json({ error: "Not found" }, 404);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
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
