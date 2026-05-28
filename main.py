import os
import sys
import math
import json
import sqlite3
import random
import string
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Slot, Qt, QThread, Signal, QEventLoop
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel


def writable_app_path(filename):
    """Store writable files next to the app instead of inside PyInstaller temp files."""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, filename)


class PwnedWorker(QThread):
    finished = Signal(str)

    def __init__(self, password):
        super().__init__()
        self.password = password

    def run(self):
        import urllib.request
        import hashlib

        sha1_pwd = hashlib.sha1(self.password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1_pwd[:5], sha1_pwd[5:]
        url = f"https://api.pwnedpasswords.com/range/{prefix}"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AegisVault"})
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read().decode("utf-8")

            hashes = (line.split(":") for line in body.splitlines())
            for h, count in hashes:
                if h == suffix:
                    self.finished.emit(json.dumps({"status": "pwned", "count": count}))
                    return
            self.finished.emit(json.dumps({"status": "clean"}))
        except Exception as e:
            self.finished.emit(json.dumps({"status": "error", "message": str(e)}))


class AegisBackend(QObject):
    def __init__(self):
        super().__init__()
        self.db_path = writable_app_path("aegis_vault.db")
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")  # Fast WAL mode
        self._init_db()
        self.wordlist = [
            "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"
        ]
        self.cryptogen = random.SystemRandom()

    def _init_db(self):
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS history 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      timestamp TEXT, 
                      label TEXT, 
                      length INTEGER, 
                      entropy REAL)"""
        )
        self._conn.commit()

    @Slot(int, bool, bool, bool, bool, bool, result=str)
    def generate_password(self, length, upper, lower, digits, symbols, unicode_inc):
        charset = ""
        if upper:
            charset += string.ascii_uppercase
        if lower:
            charset += string.ascii_lowercase
        if digits:
            charset += string.digits
        if symbols:
            charset += "!@#$%^&*()_+-=[]{}|;:,.<>?"

        if not charset:
            charset = string.ascii_letters + string.digits

        # Loop with system random choices for fast cryptographic generation
        for _ in range(20):
            password = "".join(self.cryptogen.choices(charset, k=length))
            if not self._has_weak_patterns(password):
                break

        entropy = length * math.log2(len(charset))
        res = {
            "password": password,
            "entropy": entropy,
            "brute_force": self._estimate_brute_force(entropy),
        }
        return json.dumps(res)

    @Slot(int, int, result=str)
    def generate_batch(self, count, length):
        results = []
        charset = string.ascii_letters + string.digits + "!@#$%^&*"
        # Highly optimized batch generation using SystemRandom.choices (C-level array processing)
        for _ in range(count):
            pwd = "".join(self.cryptogen.choices(charset, k=length))
            results.append({"password": pwd, "entropy": length * math.log2(len(charset))})
        return json.dumps(results)

    @Slot(int, result=str)
    def generate_diceware(self, num_words):
        words = self.cryptogen.choices(self.wordlist, k=num_words)
        passphrase = "-".join(words)
        entropy = num_words * math.log2(len(self.wordlist))
        res = {
            "password": passphrase,
            "entropy": entropy,
            "brute_force": self._estimate_brute_force(entropy),
        }
        return json.dumps(res)

    def _estimate_brute_force(self, entropy):
        log10_seconds = entropy * math.log10(2) - 12
        log10_years = log10_seconds - math.log10(3600 * 24 * 365)

        if log10_years < 0:
            return f"{10**log10_seconds:.2e} seconds"
        if log10_years > 15:
            return "> 10^15 years"
        return f"{10**log10_years:.2e} years"

    def _has_weak_patterns(self, pwd):
        # Single-pass checking with early exit for performance.
        # Added descending pattern detection (e.g. 321, cba) for enhanced security.
        for i in range(len(pwd) - 2):
            a, b, c = ord(pwd[i]), ord(pwd[i + 1]), ord(pwd[i + 2])
            if (b == a + 1 and c == a + 2) or (b == a - 1 and c == a - 2):  # Sequential check
                return True
            if a == b == c:  # Triple character repeat
                return True
        return False

    @Slot(str, result=str)
    def check_pwned(self, password):
        # Non-blocking breach check: Run request inside a QThread,
        # and wait via a local QEventLoop so the GUI event loop remains fully responsive.
        worker = PwnedWorker(password)
        result = None

        def on_finished(res):
            nonlocal result
            result = res

        worker.finished.connect(on_finished)
        worker.start()

        loop = QEventLoop()
        worker.finished.connect(loop.quit)
        loop.exec()

        return result

    @Slot(str, int, float, result=bool)
    def save_to_history(self, label, length, entropy):
        self._conn.execute(
            "INSERT INTO history (timestamp, label, length, entropy) VALUES (?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), label, length, entropy),
        )
        self._conn.commit()
        return True

    @Slot(result=str)
    def get_history(self):
        cur = self._conn.execute("SELECT * FROM history ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
        return json.dumps(
            [{"id": r[0], "time": r[1], "label": r[2], "len": r[3], "entropy": r[4]} for r in rows]
        )

    @Slot(result=bool)
    def clear_history(self):
        self._conn.execute("DELETE FROM history")
        self._conn.commit()
        return True


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AegisVault - Premium Password Security")
        self.resize(980, 760)

        self.backend = AegisBackend()

        # Initialize Qt WebEngine View for rendering beautiful modern glassmorphic Web UI
        self.view = QWebEngineView()
        self.setCentralWidget(self.view)

        # Set up QWebChannel to connect Javascript Frontend with Python Backend
        self.channel = QWebChannel()
        self.channel.registerObject("backend", self.backend)
        self.view.page().setWebChannel(self.channel)

        # Find absolute path of the HTML file, supporting both source run and compiled EXE modes
        ui_path = self.get_ui_path()
        url = f"file:///{ui_path.replace(os.sep, '/')}"
        self.view.setUrl(url)

    def get_ui_path(self):
        if getattr(sys, "frozen", False):
            # Check PyInstaller extraction folder (onefile mode)
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                path = os.path.join(meipass, "ui", "index.html")
                if os.path.exists(path):
                    return path
            
            # Check sibling folder to executable (onedir mode)
            base_dir = os.path.dirname(sys.executable)
            path = os.path.join(base_dir, "ui", "index.html")
            if os.path.exists(path):
                return path

            # Fallback sibling folder under _internal
            path = os.path.join(base_dir, "_internal", "ui", "index.html")
            if os.path.exists(path):
                return path
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_dir, "ui", "index.html")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
