# Cloudflare Worker backend

Этот Worker хранит привязку шестизначного `PC-ID` к Telegram-чату и выдаёт одноразовые коды. Telegram-токен хранится в Cloudflare Secret, а не в Python-клиенте.

## Установка

В папке `cloudflare-worker`:

```powershell
npx wrangler login
npx wrangler kv namespace create LOCK_KV
```

Скопируйте полученный `id` в `wrangler.toml` вместо `PASTE_KV_NAMESPACE_ID_HERE`, затем выполните:

```powershell
npx wrangler secret put BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET
npx wrangler deploy
```

`WEBHOOK_SECRET` — случайная длинная строка. После деплоя установите webhook, подставив URL Worker:

```powershell
curl.exe -X POST "https://api.telegram.org/botYOUR_TOKEN/setWebhook" -H "Content-Type: application/json" -d '{"url":"https://YOUR-WORKER.workers.dev/telegram/webhook","secret_token":"YOUR_WEBHOOK_SECRET"}'
```

Токен не добавляйте в Git и не вставляйте в Python-программу. После деплоя URL Worker будет добавлен в `lock_screen.py` как публичный `API_URL`.
