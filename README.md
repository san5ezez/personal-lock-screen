# Personal Lock Screen

Полноэкранная блокировка Windows с одноразовым кодом через Telegram и Cloudflare Workers.

Проект предназначен для добровольного ограничения доступа к собственному компьютеру. Он не удаляет файлы, не шифрует данные и не отключает системные механизмы безопасности Windows.

## Как это работает

```text
lock_screen.py -> Cloudflare Worker -> Telegram Bot
```

При каждом запуске создаётся новый шестизначный `PC_ID`. Отправьте боту:

```text
/start 123456
```

После этого бот отправит одноразовый код, который проверяется через Worker.

## Настройка Worker

В папке `cloudflare-worker` выполните:

```powershell
npx wrangler login
npx wrangler kv namespace create LOCK_KV
```

Скопируйте выданный ID в `cloudflare-worker/wrangler.toml` вместо `PASTE_KV_NAMESPACE_ID_HERE`.

Добавьте секреты и опубликуйте Worker:

```powershell
npx wrangler secret put BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET
npx wrangler deploy
```

Значения секретов вводятся только после приглашения `Enter a secret value:`. Не вставляйте токен в саму команду.

Затем замените URL в `lock_screen.py`:

```python
API_URL = "https://YOUR-WORKER.workers.dev"
```

## Запуск

Установщик сначала предлагает выбрать язык `Русский` или `English`. Выбор используется интерфейсом блокировки и сообщениями Telegram-бота.

```powershell
$env:PERSONAL_LOCK_PASSWORD = "your-private-password"
python .\lock_screen.py
```

`PERSONAL_LOCK_PASSWORD` — резервный пароль для запуска из исходников. Установщик спрашивает его сам, а клиент после первого запуска переносит его в Windows DPAPI и удаляет переменную окружения.

## Автозапуск Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\install_startup.ps1
```

Для режима Winlogon Shell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_winlogon.ps1
```

Откат выполняется скриптами `uninstall_startup.ps1` и `uninstall_winlogon.ps1`.

## Сборка установщика

Установите PyInstaller и Inno Setup, затем выполните:

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

Готовый файл появится в `installer-output`.

## Безопасность

- Не добавляйте токены, chat ID, Worker ID и пароли в Git.
- Если токен был опубликован, отзовите его через `@BotFather` и создайте новый.
- Шестизначный `PC_ID` не является секретом; защиту обеспечивают OTP и привязка Telegram-чата.
- OTP ограничен пятью попытками и действует пять минут.
- При краше или принудительном завершении lock screen wrapper не считает это успешной авторизацией; после нескольких неудачных запусков он возвращает Explorer для восстановления системы.
- Это блокировка уровня приложения, а не замена системному экрану входа Windows.
