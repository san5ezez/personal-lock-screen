"""Personal fullscreen lock screen for Windows.

This is an application-level lock, not a replacement for the Windows sign-in
screen. It does not disable Windows hotkeys, Task Manager, or power controls.
"""

from __future__ import annotations

import json
import ctypes
import os
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import ttk


# Public Worker URL. The Telegram token is intentionally not stored here.
API_URL = "https://YOUR-WORKER.workers.dev"
static_password = os.environ.get("PERSONAL_LOCK_PASSWORD", "CHANGE_ME_BEFORE_RUNNING")
UI_FONT = "Segoe UI"

def get_device_id() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class CloudflareClient:
    def __init__(self, device_id: str, on_status, on_success):
        self.device_id = device_id
        self.on_status = on_status
        self.on_success = on_success
        self.stop_event = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._register, daemon=True).start()

    def stop(self) -> None:
        self.stop_event.set()

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            API_URL.rstrip("/") + path,
            data=data,
            headers={
                "content-type": "application/json",
                "User-Agent": "PersonalLockScreen/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _register(self) -> None:
        try:
            self._post("/api/register", {"device_id": self.device_id})
            self.on_status(f"Ваш PC-ID: {self.device_id}. Отправьте боту /start {self.device_id}")
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            self.on_status("Нет соединения с сервером — используйте резервный пароль")

    def verify_code(self, code: str) -> None:
        threading.Thread(target=self._verify, args=(code,), daemon=True).start()

    def _verify(self, code: str) -> None:
        try:
            result = self._post("/api/verify", {
                "device_id": self.device_id,
                "code": code,
            })
            if result.get("ok"):
                self.on_success()
            else:
                self.on_status("Неверный или просроченный код")
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            self.on_status("Нет соединения с сервером")


class TelegramClient:
    def __init__(self, token: str, chat_id: str, otp: str, on_status, on_code):
        self.token = token.strip()
        self.chat_id = chat_id.strip()
        self.otp = otp
        self.on_status = on_status
        self.on_code = on_code
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.offset = 0

    @property
    def configured(self) -> bool:
        return bool(self.token and self.token != "YOUR_BOT_TOKEN_HERE")

    def start(self) -> None:
        if not self.configured:
            self.on_status("Telegram не настроен — доступен резервный пароль")
            return
        self.thread = threading.Thread(target=self._poll, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def _request(self, method: str, payload: dict, timeout: int = 25) -> dict:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _send_code(self) -> None:
        if not self.chat_id:
            return
        self._request("sendMessage", {
            "chat_id": self.chat_id,
            "text": "Ваш одноразовый код для разблокировки: " + self.otp,
        }, timeout=15)

    def _poll(self) -> None:
        self.on_status("Telegram подключается… отправьте боту /start")
        while not self.stop_event.is_set():
            try:
                result = self._request("getUpdates", {
                    "offset": self.offset,
                    "timeout": 20,
                    "allowed_updates": json.dumps(["message"]),
                }, timeout=25)
                if not result.get("ok"):
                    raise RuntimeError("Telegram API вернул ошибку")

                for update in result.get("result", []):
                    self.offset = int(update["update_id"]) + 1
                    message = update.get("message", {})
                    chat = message.get("chat", {})
                    incoming_chat_id = str(chat.get("id", ""))
                    text = str(message.get("text", "")).strip()

                    if text == "/start" and not self.chat_id:
                        self.chat_id = incoming_chat_id
                        self._send_code()
                        self.on_status("Код отправлен в Telegram")
                        continue

                    if not self.chat_id or incoming_chat_id != self.chat_id:
                        continue

                    if text == "/start":
                        self._send_code()
                        self.on_status("Код отправлен в Telegram")
                    elif text == self.otp:
                        self.on_code()
                        return
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                self.on_status("Нет соединения с Telegram — попробуйте резервный пароль")
                self.stop_event.wait(5)
            except Exception:
                # Do not expose API responses, token, or other sensitive data.
                self.on_status("Ошибка Telegram API — попробуйте резервный пароль")
                self.stop_event.wait(5)


class LockScreen:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.unlocked = False
        self.explorer_stopped = False
        self.device_id = get_device_id()
        self.telegram = CloudflareClient(self.device_id, self.set_status,
                                          self.telegram_success)
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.bind("<Return>", lambda _event: self.check_password())
        self.root.bind("<Escape>", lambda _event: "break")
        self.root.after(200, self._focus_input)
        self._create_language_indicator()
        # Explorer is stopped only after the lock window is ready.
        self.root.after(500, self.stop_explorer)
        self.telegram.start()

    def _create_language_indicator(self) -> None:
        self.layout_label = tk.Label(
            self.root, text="", bg="#101318", fg="#aeb6c2",
            font=("Segoe UI", 10), padx=8, pady=4,
        )
        self.layout_label.place(relx=1.0, rely=1.0, anchor="se", x=-18, y=-14)
        self._update_language_indicator()

    @staticmethod
    def _current_layout() -> str:
        if os.name != "nt":
            return "--"
        try:
            name = ctypes.create_unicode_buffer(9)
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            if user32.GetKeyboardLayoutNameW(name):
                layout_id = name.value[-4:].upper()
                return {
                    "0409": "EN",
                    "0419": "RU",
                    "0422": "UK",
                    "0407": "DE",
                    "040C": "FR",
                }.get(layout_id, layout_id)
        except (AttributeError, OSError):
            pass
        return "--"

    def _update_language_indicator(self) -> None:
        if self.unlocked:
            return
        self.layout_label.config(text=self._current_layout())
        self.root.after(500, self._update_language_indicator)

    def _build_ui(self) -> None:
        self.root.title("Личная блокировка")
        self.root.configure(bg="#101318")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Lock.TButton", font=("Segoe UI", 12), padding=(26, 11))

        container = tk.Frame(self.root, bg="#101318")
        container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(container, text="Введите одноразовый код", bg="#101318",
                 fg="#f4f6f8", font=("Segoe UI", 25, "bold")).pack(pady=(0, 12))
        tk.Label(container, text="Код отправлен через @mysyspassword_bot", bg="#101318",
                 fg="#aeb6c2", font=("Segoe UI", 12)).pack(pady=(0, 26))

        self.entry = tk.Entry(container, width=22, justify="center", show="•",
                              bg="#1b2029", fg="#ffffff", insertbackground="#ffffff",
                              relief="flat", font=("Segoe UI", 18),
                              highlightthickness=1, highlightbackground="#3a4350",
                              highlightcolor="#6ea8fe")
        self.entry.pack(ipady=10, pady=(0, 15))
        self.entry.focus_set()

        ttk.Button(container, text="Подтвердить", style="Lock.TButton",
                   command=self.check_password).pack()

        self.status = tk.Label(container, text="Проверка подключения…", bg="#101318",
                                fg="#8893a2", font=("Segoe UI", 10))
        self.status.pack(pady=(18, 16))
        tk.Label(container, text="Можно использовать резервный пароль", bg="#101318",
                 fg="#717b89", font=("Segoe UI", 10)).pack()

        tk.Label(self.root, text=f"Шрифт: {UI_FONT}", bg="#101318",
                 fg="#596372", font=(UI_FONT, 9)).place(
                     relx=0.99, rely=0.98, anchor="se")

    def _focus_input(self) -> None:
        self.root.focus_force()
        self.entry.focus_set()

    def set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status.config(text=text))

    def check_password(self) -> None:
        value = self.entry.get()
        if value == static_password:
            self.unlock()
        elif value.isdigit() and len(value) == 6:
            self.status.config(text="Проверка одноразового кода…")
            self.entry.delete(0, tk.END)
            self.telegram.verify_code(value)
        else:
            self.status.config(text="Неверный код или пароль")
            self.entry.delete(0, tk.END)
            self._focus_input()

    def telegram_success(self) -> None:
        self.root.after(0, self.unlock)

    def stop_explorer(self) -> None:
        if os.name != "nt" or self.unlocked:
            return
        try:
            result = subprocess.run(
                ["taskkill", "/f", "/im", "explorer.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            self.explorer_stopped = result.returncode == 0
        except OSError:
            self.set_status("Не удалось временно остановить Explorer")

    def restore_explorer(self) -> None:
        if not self.explorer_stopped:
            return
        try:
            subprocess.Popen(
                ["explorer.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except OSError:
            pass
        finally:
            self.explorer_stopped = False

    def unlock(self) -> None:
        if self.unlocked:
            return
        self.unlocked = True
        self.telegram.stop()
        self.restore_explorer()
        self.root.destroy()


def main() -> None:
    global app
    app = LockScreen(tk.Tk())
    app.root.mainloop()


if __name__ == "__main__":
    main()
