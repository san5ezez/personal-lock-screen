"""Personal self-lock screen for Windows.

This is an application-level self-control tool, not a security boundary.
Windows Task Manager and administrator controls are intentionally untouched.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import ttk


API_URL = "https://YOUR-WORKER.workers.dev"
BOT_USERNAME = "Telegram-бота"
PASSWORD_ENV = "PERSONAL_LOCK_PASSWORD"
LANGUAGE_ENV = "PERSONAL_LOCK_LANGUAGE"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PersonalLockScreen"
PASSWORD_FILE = APP_DIR / "password.dpapi"

TEXT = {
    "ru": {"title": "Личная блокировка", "heading": "Введите одноразовый код", "sent": "Код отправлен через Telegram-бота", "confirm": "Подтвердить", "backup": "Можно использовать резервный пароль", "connecting": "Подключение к серверу…", "checking": "Проверка одноразового кода…", "wrong": "Неверный код или пароль", "configure": "Сначала настройте URL Cloudflare Worker", "pcid": "PC-ID: {id}. Отправьте боту /start {id}", "offline": "Сервер недоступен — используйте резервный пароль"},
    "en": {"title": "Personal Lock Screen", "heading": "Enter one-time code", "sent": "The code was sent by the Telegram bot", "confirm": "Confirm", "backup": "You can use the backup password", "connecting": "Connecting to server…", "checking": "Checking one-time code…", "wrong": "Invalid code or password", "configure": "Configure the Cloudflare Worker URL first", "pcid": "PC-ID: {id}. Send /start {id} to the bot", "offline": "Server unavailable — use the backup password"},
}


def get_language() -> str:
    value = os.environ.get(LANGUAGE_ENV, "")
    if not value and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as key:
                value = winreg.QueryValueEx(key, LANGUAGE_ENV)[0]
        except (FileNotFoundError, OSError):
            value = "ru"
    return "en" if str(value).lower().startswith("en") else "ru"


def tr(language: str, key: str) -> str:
    return TEXT[language][key]


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes = b"") -> DATA_BLOB:
    buffer = (ctypes.c_byte * len(data))(*data) if data else None
    return DATA_BLOB(len(data), buffer)


def _dpapi_protect(data: bytes) -> bytes:
    input_blob = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    input_blob = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def load_password() -> str:
    try:
        value = os.environ.get(PASSWORD_ENV, "")
        if value:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            PASSWORD_FILE.write_bytes(_dpapi_protect(value.encode("utf-8")))
            os.environ.pop(PASSWORD_ENV, None)
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, PASSWORD_ENV)
            except (FileNotFoundError, OSError):
                pass
            return value
        if PASSWORD_FILE.exists():
            return _dpapi_unprotect(PASSWORD_FILE.read_bytes()).decode("utf-8")
    except (OSError, UnicodeError):
        pass
    return ""


def get_device_id() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class CloudflareClient:
    def __init__(self, device_id: str, language: str, on_status, on_success):
        self.device_id = device_id
        self.language = language
        self.on_status = on_status
        self.on_success = on_success
        self.stop_event = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._register_localized, daemon=True).start()

    def stop(self) -> None:
        self.stop_event.set()

    def _post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            API_URL.rstrip("/") + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json", "User-Agent": "PersonalLockScreen/1.1"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _register(self) -> None:
        if "YOUR-WORKER" in API_URL:
            self.on_status("Сначала настройте URL Cloudflare Worker")
            return
        try:
            self._post("/api/register", {"device_id": self.device_id, "language": self.language})
            self.on_status(f"PC-ID: {self.device_id}. Отправьте боту /start {self.device_id}")
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            self.on_status("Сервер недоступен — используйте резервный пароль")

    def _register_localized(self) -> None:
        if "YOUR-WORKER" in API_URL:
            self.on_status(tr(self.language, "configure"))
            return
        try:
            self._post("/api/register", {"device_id": self.device_id, "language": self.language})
            self.on_status(tr(self.language, "pcid").format(id=self.device_id))
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            self.on_status(tr(self.language, "offline"))

    def verify_code(self, code: str) -> None:
        threading.Thread(target=self._verify, args=(code,), daemon=True).start()

    def _verify(self, code: str) -> None:
        try:
            result = self._post("/api/verify", {"device_id": self.device_id, "code": code})
            if result.get("ok"):
                self.on_success()
            else:
                self.on_status(result.get("error", "Неверный или просроченный код"))
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            self.on_status("Сервер недоступен")


class LockScreen:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.unlocked = False
        self.exit_code = 1
        self.language = get_language()
        self.static_password = load_password()
        self.device_id = get_device_id()
        self.client = CloudflareClient(self.device_id, self.language, self.set_status, self.telegram_success)
        self._build_ui()
        self._apply_language()
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.bind("<Return>", lambda _event: self.check_password())
        self.root.bind("<Escape>", lambda _event: "break")
        self.root.after(200, self._focus_input)
        self._create_language_indicator()
        self.root.after(500, self.stop_explorer)
        self.client.start()

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
        self.container = container
        container.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(container, text="Введите одноразовый код", bg="#101318", fg="#f4f6f8", font=("Segoe UI", 25, "bold")).pack(pady=(0, 12))
        tk.Label(container, text=f"Код отправлен через {BOT_USERNAME}", bg="#101318", fg="#aeb6c2", font=("Segoe UI", 12)).pack(pady=(0, 26))
        self.entry = tk.Entry(container, width=22, justify="center", show="•", bg="#1b2029", fg="#ffffff", insertbackground="#ffffff", relief="flat", font=("Segoe UI", 18), highlightthickness=1, highlightbackground="#3a4350", highlightcolor="#6ea8fe")
        self.entry.pack(ipady=10, pady=(0, 15))
        self.entry.focus_set()
        ttk.Button(container, text="Подтвердить", style="Lock.TButton", command=self.check_password).pack()
        self.status = tk.Label(container, text="Подключение к серверу…", bg="#101318", fg="#8893a2", font=("Segoe UI", 10))
        self.status.pack(pady=(18, 16))
        tk.Label(container, text="Можно использовать резервный пароль", bg="#101318", fg="#717b89", font=("Segoe UI", 10)).pack()

    def _apply_language(self) -> None:
        widgets = self.container.winfo_children()
        widgets[0].config(text=tr(self.language, "heading"))
        widgets[1].config(text=tr(self.language, "sent"))
        widgets[3].config(text=tr(self.language, "confirm"))
        widgets[4].config(text=tr(self.language, "connecting"))
        widgets[5].config(text=tr(self.language, "backup"))
        self.root.title(tr(self.language, "title"))

    def _create_language_indicator(self) -> None:
        self.layout_label = tk.Label(self.root, text="", bg="#101318", fg="#aeb6c2", font=("Segoe UI", 10), padx=8, pady=4)
        self.layout_label.place(relx=1.0, rely=1.0, anchor="se", x=-18, y=-14)
        self._update_language_indicator()

    @staticmethod
    def _current_layout() -> str:
        if os.name != "nt":
            return "--"
        try:
            name = ctypes.create_unicode_buffer(9)
            if ctypes.windll.user32.GetKeyboardLayoutNameW(name):
                code = name.value[-4:].upper()
                return {"0409": "EN", "0419": "RU", "0422": "UK", "0407": "DE", "040C": "FR"}.get(code, code)
        except (AttributeError, OSError):
            pass
        return "--"

    def _update_language_indicator(self) -> None:
        if not self.unlocked:
            self.layout_label.config(text=self._current_layout())
            self.root.after(500, self._update_language_indicator)

    def _focus_input(self) -> None:
        self.root.focus_force()
        self.entry.focus_set()

    def set_status(self, message: str) -> None:
        self.root.after(0, lambda: self.status.config(text=message))

    def check_password(self) -> None:
        value = self.entry.get()
        if self.static_password and value == self.static_password:
            self.unlock()
        elif value.isdigit() and len(value) == 6:
            self.status.config(text="Проверка одноразового кода…")
            self.entry.delete(0, tk.END)
            self.client.verify_code(value)
        else:
            self.status.config(text="Неверный код или пароль")
            self.entry.delete(0, tk.END)
            self._focus_input()

    def check_password(self) -> None:
        value = self.entry.get()
        if self.static_password and value == self.static_password:
            self.unlock()
        elif value.isdigit() and len(value) == 6:
            self.status.config(text=tr(self.language, "checking"))
            self.entry.delete(0, tk.END)
            self.client.verify_code(value)
        else:
            self.status.config(text=tr(self.language, "wrong"))
            self.entry.delete(0, tk.END)
            self._focus_input()

    def telegram_success(self) -> None:
        self.root.after(0, self.unlock)

    def stop_explorer(self) -> None:
        if os.name != "nt" or self.unlocked:
            return
        try:
            subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except OSError:
            self.set_status("Не удалось остановить Explorer")

    def restore_explorer(self) -> None:
        try:
            subprocess.Popen(["explorer.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        except OSError:
            pass

    def unlock(self) -> None:
        if self.unlocked:
            return
        self.unlocked = True
        self.exit_code = 0
        self.client.stop()
        self.restore_explorer()
        self.root.destroy()


def main() -> int:
    app = LockScreen(tk.Tk())
    app.root.mainloop()
    return app.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
