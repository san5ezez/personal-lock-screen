# Personal Lock Screen

[RU](README_RU.md) | **EN**

Application-level fullscreen self-lock screen for Windows with one-time codes delivered through Telegram and Cloudflare Workers.

> This project is designed for voluntary self-control on your own computer. It is not a replacement for the Windows sign-in screen and does not protect against Task Manager or administrator access.

## Features

- Fullscreen lock screen for the current Windows user.
- Russian / English language choice during installation.
- The selected language is used by the lock screen and Telegram bot.
- New six-digit `PC_ID` on every launch.
- One-time OTP delivered through Telegram.
- OTP verification through Cloudflare Workers.
- Backup password requested during installation.
- Backup password protected with Windows DPAPI after first launch.
- Keyboard layout indicator (`RU`, `EN`, `DE`, `FR`, `UK`).
- Winlogon Shell integration with recovery fallback.
- Telegram token stored only in Cloudflare Secrets, never in the client.

## How it works

```text
lock_screen.exe -> Cloudflare Worker -> Telegram Bot
```

At startup the application displays a six-digit `PC_ID`, for example:

```text
482913
```

Send the following command to your Telegram bot:

```text
/start 482913
```

The bot sends a one-time code. Enter it in the lock screen.

The `PC_ID` changes on every launch and is not a secret. Security is provided by the temporary OTP and Telegram chat binding.

## Cloudflare Worker setup

Open the `cloudflare-worker` directory:

```powershell
npx wrangler login
npx wrangler kv namespace create LOCK_KV
```

Copy the returned KV namespace ID into `cloudflare-worker/wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "LOCK_KV"
id = "YOUR_KV_NAMESPACE_ID"
```

Create the secrets and deploy:

```powershell
npx wrangler secret put BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET
npx wrangler deploy
```

When Wrangler asks for `Enter a secret value:`, paste the value there. Do not put tokens in the command itself.

Set your deployed Worker URL in `lock_screen.py`:

```python
API_URL = "https://YOUR-WORKER.workers.dev"
```

## Installation

Run `PersonalLockScreenSetup.exe`.

1. Select `Русский` or `English`.
2. Set the backup password.
3. Confirm the password.
4. Confirm the Winlogon Shell warning.
5. Restart Windows.

The selected language is saved for the current Windows user. The lock screen and Telegram messages use the same language.

## Build the installer

Install PyInstaller and Inno Setup, then run:

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

The installer is created in `installer-output`.

## Recovery and uninstall

If Explorer does not appear, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\emergency_restore_shell.ps1
```

To remove the Winlogon integration from source files:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_winlogon.ps1
```

Do not delete the installation directory manually before restoring the Winlogon Shell.

## Limitations

- This is a self-control tool, not a security boundary.
- Task Manager, administrator access, Safe Mode, and external recovery tools are not blocked.
- OTP attempts are limited and expire, but a six-digit `PC_ID` is not a secret.

## Security rules

- Never commit Telegram tokens, chat IDs, passwords, Worker URLs, or KV IDs.
- If a Telegram token is exposed, revoke it through `@BotFather` and create a new one.
- Keep `.wrangler`, `.env`, and local secret files out of Git.
