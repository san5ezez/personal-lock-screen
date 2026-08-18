# Personal Lock Screen

**RU** | [EN](README.md)

Полноэкранное приложение для добровольного самоограничения на собственном компьютере Windows. Для выдачи одноразовых кодов используются Telegram-бот и Cloudflare Workers.

> Проект предназначен для личного использования владельцем компьютера. Это не замена стандартному экрану входа Windows и не защита от доступа через Диспетчер задач или права администратора.

## Возможности

- Полноэкранный экран блокировки текущего пользователя Windows.
- Выбор русского или английского языка при установке.
- Использование выбранного языка в интерфейсе и Telegram-боте.
- Новый шестизначный `PC_ID` при каждом запуске.
- Получение одноразового OTP-кода через Telegram.
- Проверка OTP через Cloudflare Worker.
- Настройка резервного пароля во время установки.
- Защита резервного пароля через Windows DPAPI после первого запуска.
- Индикатор раскладки клавиатуры: `RU`, `EN`, `DE`, `FR`, `UK`.
- Интеграция с Winlogon Shell и аварийное восстановление Explorer.
- Telegram-токен хранится только в Cloudflare Secrets и не попадает в клиентскую программу.

## Как это работает

```text
lock_screen.exe -> Cloudflare Worker -> Telegram Bot
```

При запуске приложение показывает шестизначный `PC_ID`, например:

```text
482913
```

Отправьте своему Telegram-боту команду:

```text
/start 482913
```

Вместо `482913` используйте ID, который показан в окне. Бот отправит одноразовый код. Введите его в экран блокировки.

`PC_ID` меняется при каждом запуске и не является секретом. Защиту обеспечивают временный OTP-код и привязка Telegram-чата.

## Настройка Cloudflare Worker

Откройте папку `cloudflare-worker` и выполните:

```powershell
npx wrangler login
npx wrangler kv namespace create LOCK_KV
```

Скопируйте полученный ID KV-namespace в `cloudflare-worker/wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "LOCK_KV"
id = "YOUR_KV_NAMESPACE_ID"
```

Создайте секреты и опубликуйте Worker:

```powershell
npx wrangler secret put BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET
npx wrangler deploy
```

Когда Wrangler покажет `Enter a secret value:`, вставьте значение именно туда. Не вставляйте токен прямо в команду.

После деплоя укажите URL Worker в `lock_screen.py`:

```python
API_URL = "https://YOUR-WORKER.workers.dev"
```

Для GitHub-версии оставляйте placeholder `YOUR-WORKER.workers.dev`, а личный URL добавляйте только в локальную копию перед сборкой.

## Установка

Запустите `PersonalLockScreenSetup.exe`.

1. Выберите `Русский` или `English`.
2. Задайте резервный пароль.
3. Повторите пароль для подтверждения.
4. Подтвердите предупреждение о включении Winlogon Shell.
5. Перезагрузите Windows.

Выбранный язык сохраняется для текущего пользователя Windows. Экран блокировки и сообщения Telegram используют один и тот же язык.

## Сборка установщика

Установите PyInstaller и Inno Setup, затем выполните:

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

Готовый установщик появится в папке `installer-output`.

## Восстановление и удаление

Если Explorer не появился, выполните:

```powershell
powershell -ExecutionPolicy Bypass -File .\emergency_restore_shell.ps1
```

Для удаления интеграции Winlogon из исходной папки выполните:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_winlogon.ps1
```

Не удаляйте папку установки вручную до восстановления Winlogon Shell.

## Ограничения

- Это приложение для самоограничения, а не граница безопасности.
- Диспетчер задач, права администратора, безопасный режим и внешние средства восстановления не блокируются.
- OTP-коды имеют ограниченный срок действия и число попыток, но шестизначный `PC_ID` не является секретом.
- При необходимости восстановления используйте аварийный скрипт до удаления файлов приложения.

## Правила безопасности

- Не добавляйте Telegram-токены, chat ID, пароли, Worker URL или KV ID в Git.
- Если Telegram-токен был раскрыт, отзовите его через `@BotFather` и создайте новый.
- Не публикуйте `.wrangler`, `.env` и локальные файлы с секретами.
- Перед распространением проверьте, что в `lock_screen.py` установлен placeholder Worker URL.
