#!/usr/bin/env python3
"""
TikTok Downloader — macOS Desktop App
Descarga videos de TikTok con yt-dlp y transcribe audio con Whisper.
"""
import os, sys, subprocess, threading, json, urllib.request, urllib.error, ssl
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# ── Config ──
WHISPER_MODEL = "base"
APP_NAME = "TikTok Downloader"
APP_VERSION = "1.2"
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads" / "TikTok Downloads")
FFMPEG_LOCATION = "/opt/homebrew/bin"

# Paquetes pip a monitorear: (nombre_pip, nombre_import, pypi_name)
PIP_PACKAGES = [
    ("yt-dlp",          "yt_dlp",    "yt-dlp"),
    ("openai-whisper",   "whisper",   "openai-whisper"),
    ("curl_cffi",        "curl_cffi", "curl-cffi"),
]

# ── Helpers ──

def log_append(text_widget, msg):
    text_widget.after(0, lambda: text_widget.insert(tk.END, msg + "\n"))
    text_widget.after(0, lambda: text_widget.see(tk.END))

def run_cmd(cmd, log_widget=None):
    if log_widget:
        log_append(log_widget, "$ " + " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    full_out = []
    for line in proc.stdout:
        line = line.rstrip()
        full_out.append(line)
        if log_widget:
            log_append(log_widget, "  " + line)
    proc.wait()
    return "\n".join(full_out), proc.returncode


# ── Update Checker ──

def get_installed_versions():
    """Return dict: {pypi_name: installed_version_string}"""
    versions = {}
    for pip_name, import_name, pypi_name in PIP_PACKAGES:
        try:
            mod = __import__(import_name)
            v = getattr(mod, "__version__", None)
            if not v and hasattr(mod, "version"):
                v = getattr(mod, "version", None)
                if hasattr(v, "__version__"):
                    v = v.__version__
            versions[pypi_name] = v or "?"
        except Exception:
            versions[pypi_name] = "no instalado"
    return versions

def get_latest_versions():
    """Query PyPI JSON API. Return dict: {pypi_name: latest_version_string}"""
    latest = {}
    ctx = ssl.create_default_context()
    for pip_name, import_name, pypi_name in PIP_PACKAGES:
        url = f"https://pypi.org/pypi/{pypi_name}/json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TikTokDownloader/1.0"})
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                data = json.loads(resp.read().decode())
                info = data.get("info", {})
                latest[pypi_name] = info.get("version", "?")
        except Exception:
            latest[pypi_name] = "?"
    return latest

def _parse_version(v):
    """Convierte '2026.07.04' -> (2026, 7, 4) para comparar."""
    parts = v.replace("-", ".").split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    return tuple(nums)

def check_for_updates():
    """Returns (outdated_list, current_versions, latest_versions) or raises."""
    installed = get_installed_versions()
    latest = get_latest_versions()
    outdated = []
    for pypi_name in installed:
        iv = installed[pypi_name]
        lv = latest.get(pypi_name, "?")
        if iv and lv and iv != "?" and lv != "?" and iv != "no instalado":
            try:
                if _parse_version(lv) > _parse_version(iv):
                    outdated.append((pypi_name, iv, lv))
            except Exception:
                if iv != lv:
                    outdated.append((pypi_name, iv, lv))
    return outdated, installed, latest


# ── Download ──

def download_video(url, output_dir, log_widget, btn_widget, status_label):
    try:
        btn_widget.config(state=tk.DISABLED, text="Descargando...")
        log_append(log_widget, "\n" + "=" * 60)
        log_append(log_widget, "Descargando video: " + url)
        log_append(log_widget, "Destino: " + output_dir)
        log_append(log_widget, "=" * 60)

        os.makedirs(output_dir, exist_ok=True)

        # Attempt 1: con impersonate
        cmd = ["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mp4",
               "--embed-thumbnail", "--embed-metadata",
               "--impersonate", "Chrome-146:Macos-26",
               "--ffmpeg-location", FFMPEG_LOCATION,
               "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
               "--no-playlist", "--print", "filename", url]
        stdout, rc = run_cmd(cmd, log_widget)

        # Attempt 2: si fallo por DNS/red, reintentar sin impersonate
        if rc != 0 and ("Could not resolve" in stdout or "curl:" in stdout):
            log_append(log_widget, "Reintentando sin impersonate...")
            cmd = ["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mp4",
                   "--embed-thumbnail", "--embed-metadata",
                   "--ffmpeg-location", FFMPEG_LOCATION,
                   "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
                   "--no-playlist", "--print", "filename", url]
            stdout, rc = run_cmd(cmd, log_widget)

        if rc == 0:
            lines = [l.strip() for l in stdout.split("\n") if l.strip()]
            saved_file = lines[-1] if lines else "desconocido"
            log_append(log_widget, "\nDescarga completa: " + saved_file)
            if status_label:
                status_label.config(text="Listo: " + Path(saved_file).name)
            messagebox.showinfo("Descarga completa", "Video guardado en:\n" + saved_file)
        else:
            log_append(log_widget, "\nError en la descarga (codigo " + str(rc) + ")")
            messagebox.showerror("Error", "Fallo la descarga. Revisa el log.")
    except Exception as e:
        log_append(log_widget, "\nExcepcion: " + str(e))
        messagebox.showerror("Error", str(e))
    finally:
        btn_widget.config(state=tk.NORMAL, text="Descargar Video")


# ── Transcript ──

WHISPER_LOCK = threading.Lock()

def transcribe_video(url, output_dir, log_widget, btn_widget, status_label, model_var):
    def _work():
        nonlocal model_var
        try:
            btn_widget.config(state=tk.DISABLED, text="Procesando...")
            log_append(log_widget, "\n" + "=" * 60)
            log_append(log_widget, "Transcribiendo: " + url)
            log_append(log_widget, "=" * 60)

            os.makedirs(output_dir, exist_ok=True)

            audio_template = os.path.join(output_dir, "%(title)s.%(ext)s")
            log_append(log_widget, "Descargando audio...")

            def _try_download(with_impersonate):
                extra = ["--impersonate", "Chrome-146:Macos-26"] if with_impersonate else []
                return run_cmd(
                    ["yt-dlp", "-x", "--audio-format", "wav", "--audio-quality", "0",
                     "--ffmpeg-location", FFMPEG_LOCATION]
                    + extra
                    + ["-o", audio_template, "--no-playlist",
                       "--print", "after_move:filename", url],
                    log_widget
                )

            stdout, rc = _try_download(True)
            if rc != 0 and ("Could not resolve" in stdout or "curl:" in stdout):
                log_append(log_widget, "Reintentando sin impersonate...")
                stdout, rc = _try_download(False)

            if rc != 0:
                log_append(log_widget, "\nError descargando audio (codigo " + str(rc) + ")")
                messagebox.showerror("Error", "Fallo la descarga del audio.")
                return

            lines = [l.strip() for l in stdout.split("\n") if l.strip()]
            audio_file = None
            for l in lines:
                if l.endswith(".wav"):
                    audio_file = l
                    break
            if not audio_file or not os.path.exists(audio_file):
                wav_files = sorted(Path(output_dir).glob("*.wav"), key=os.path.getmtime, reverse=True)
                if wav_files:
                    audio_file = str(wav_files[0])
                else:
                    log_append(log_widget, "No se encontro el archivo de audio (.wav).")
                    messagebox.showerror("Error", "No se pudo localizar el audio descargado.")
                    return

            log_append(log_widget, "Audio descargado: " + audio_file)

            model_name = model_var.get()
            log_append(log_widget, "Transcribiendo con whisper (" + model_name + ")... Primeras carga descarga el modelo.")

            with WHISPER_LOCK:
                import whisper
                model = whisper.load_model(model_name)
                result = model.transcribe(audio_file, language="es", verbose=False)

            base_name = os.path.splitext(audio_file)[0]
            txt_path = base_name + ".txt"

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("Transcripcion de: " + url + "\n")
                f.write("=" * 60 + "\n\n")
                for seg in result["segments"]:
                    f.write("[%06.2f -> %06.2f] %s\n" % (seg["start"], seg["end"], seg["text"].strip()))
                f.write("\n" + "=" * 60 + "\n")
                f.write("Modelo: whisper/" + model_name + "\n")

            log_append(log_widget, "\nTranscripcion guardada: " + txt_path)
            log_append(log_widget, "\nVista previa del guion:")
            for seg in result["segments"][:5]:
                log_append(log_widget, "  " + seg['text'].strip())
            if len(result["segments"]) > 5:
                log_append(log_widget, "  ... y " + str(len(result["segments"]) - 5) + " segmentos mas.")

            if status_label:
                status_label.config(text="Listo: " + Path(txt_path).name)
            messagebox.showinfo("Transcripcion completa", "Guion guardado en:\n" + txt_path)

        except ImportError:
            log_append(log_widget, "Whisper no instalado. Corre: pip install openai-whisper")
            messagebox.showerror("Error", "Whisper no esta instalado.")
        except Exception as e:
            log_append(log_widget, "\nExcepcion: " + str(e))
            messagebox.showerror("Error", str(e))
        finally:
            btn_widget.config(state=tk.NORMAL, text="Descargar Guion")

    threading.Thread(target=_work, daemon=True).start()


# ── GUI ──

class TikTokDownloaderApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME + " v" + APP_VERSION)
        self.root.geometry("720x600")
        self.root.minsize(600, 480)

        style = ttk.Style(self.root)
        try:
            style.theme_use("aqua")
        except:
            pass

        self.dl_url_var = tk.StringVar()
        self.dl_dir_var = tk.StringVar(value=DEFAULT_DOWNLOAD_DIR)
        self.tr_url_var = tk.StringVar()
        self.tr_dir_var = tk.StringVar(value=DEFAULT_DOWNLOAD_DIR)
        self.whisper_model_var = tk.StringVar(value=WHISPER_MODEL)

        self._build_menu()
        self._build_tabs()

        self.status_bar = ttk.Label(self.root, text="Listo", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry("+" + str(x) + "+" + str(y))

        # ── Verificar actualizaciones al inicio ──
        self.after_check = self.root.after(500, self._check_updates_startup)

    def _check_updates_startup(self):
        """Corre la verificacion de actualizaciones al iniciar (en background)."""
        self.status_bar.config(text="Verificando actualizaciones...")
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        """Ejecuta la verificacion (en thread). Muestra dialogo si hay updates."""
        try:
            outdated, installed, latest = check_for_updates()
            if outdated:
                msg = "Hay actualizaciones disponibles:\n\n"
                for pkg, cur, new in outdated:
                    msg += "  - %s: %s -> %s\n" % (pkg, cur, new)
                msg += "\nDeseas descargarlas ahora?"

                def ask():
                    if messagebox.askyesno("Actualizaciones disponibles", msg):
                        self._run_updates(outdated)
                    else:
                        self.status_bar.config(text="Listo")
                self.root.after(0, ask)
            else:
                self.root.after(0, lambda: self.status_bar.config(text="Listo"))
        except Exception as e:
            self.root.after(0, lambda: self.status_bar.config(text="Listo (no se pudo verificar update)"))

    def _run_updates(self, outdated):
        """Descarga e instala las actualizaciones."""
        top = tk.Toplevel(self.root)
        top.title("Actualizando...")
        top.geometry("600x300")
        top.transient(self.root)
        top.grab_set()

        ttk.Label(top, text="Descargando e instalando actualizaciones...").pack(pady=8)
        log_text = tk.Text(top, height=12, wrap=tk.WORD, font=("Menlo", 10))
        scroll = ttk.Scrollbar(top, orient=tk.VERTICAL, command=log_text.yview)
        log_text.config(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        def _upgrade():
            all_ok = True
            for pkg, cur, new in outdated:
                log_append(log_text, "Actualizando %s (%s -> %s)..." % (pkg, cur, new))
                pip_name = None
                for pn, impn, pypi in PIP_PACKAGES:
                    if pypi == pkg:
                        pip_name = pn
                        break
                if not pip_name:
                    log_append(log_text, "  ERROR: no se encontro nombre pip para %s" % pkg)
                    all_ok = False
                    continue

                stdout, rc = run_cmd(
                    [sys.executable, "-m", "pip", "install", "--upgrade", pip_name],
                    log_text
                )
                if rc != 0:
                    log_append(log_text, "  ERROR: codigo %d" % rc)
                    all_ok = False
                else:
                    log_append(log_text, "  OK")

            if all_ok:
                log_append(log_text, "\nTodas las actualizaciones se instalaron correctamente.")
                log_append(log_text, "Reinicia la app para usar las nuevas versiones.")
            else:
                log_append(log_text, "\nAlgunas actualizaciones fallaron. Revisa el log.")

            self.root.after(0, lambda: top.destroy())
            self.root.after(0, lambda: self.status_bar.config(text="Listo"))

        threading.Thread(target=_upgrade, daemon=True).start()

    def _manual_check_updates(self):
        """Menu action: verificar actualizaciones manualmente."""
        self.status_bar.config(text="Verificando actualizaciones...")
        threading.Thread(target=self._do_manual_check, daemon=True).start()

    def _do_manual_check(self):
        try:
            outdated, installed, latest = check_for_updates()
            if outdated:
                msg = "Actualizaciones disponibles:\n\n"
                for pkg, cur, new in outdated:
                    msg += "  %s: %s -> %s\n" % (pkg, cur, new)
                msg += "\n¿Actualizar ahora?"
                def ask():
                    if messagebox.askyesno("Actualizaciones", msg):
                        self._run_updates(outdated)
                    else:
                        self.status_bar.config(text="Listo")
                self.root.after(0, ask)
            else:
                msg = "Todo esta actualizado.\n\nVersiones actuales:\n"
                for pkg in installed:
                    msg += "  %s: %s\n" % (pkg, installed[pkg])
                self.root.after(0, lambda: messagebox.showinfo("Actualizaciones", msg))
                self.root.after(0, lambda: self.status_bar.config(text="Listo"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", "No se pudo verificar:\n" + str(e)))
            self.root.after(0, lambda: self.status_bar.config(text="Listo"))

    # ── GUI Builders ──

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Abrir carpeta de descargas", command=self._open_downloads)
        file_menu.add_separator()
        file_menu.add_command(label="Buscar actualizaciones...", command=self._manual_check_updates)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.root.quit)
        menubar.add_cascade(label="Archivo", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Acerca de", command=self._show_about)
        menubar.add_cascade(label="Ayuda", menu=help_menu)

    def _build_tabs(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ── Tab 1 ──
        tab1 = ttk.Frame(notebook, padding=12)
        notebook.add(tab1, text="Descargar Video")

        ttk.Label(tab1, text="URL de TikTok:").grid(row=0, column=0, sticky=tk.W, pady=(0,4))
        ttk.Entry(tab1, textvariable=self.dl_url_var, width=60).grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(0,8))

        ttk.Label(tab1, text="Carpeta de destino:").grid(row=2, column=0, sticky=tk.W, pady=(0,4))
        ttk.Entry(tab1, textvariable=self.dl_dir_var, width=50).grid(row=3, column=0, sticky=tk.EW, pady=(0,8))
        ttk.Button(tab1, text="Examinar", command=self._browse_dl_dir).grid(row=3, column=1, padx=(6,0), pady=(0,8))
        ttk.Button(tab1, text="Abrir", command=self._open_dl_dir).grid(row=3, column=2, padx=(6,0), pady=(0,8))

        self.dl_btn = ttk.Button(tab1, text="Descargar Video", command=self._on_download_video)
        self.dl_btn.grid(row=4, column=0, columnspan=3, pady=(4,8))

        ttk.Separator(tab1, orient=tk.HORIZONTAL).grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=8)

        ttk.Label(tab1, text="Log:").grid(row=6, column=0, sticky=tk.W)
        log_frame = ttk.Frame(tab1)
        log_frame.grid(row=7, column=0, columnspan=3, sticky=tk.NSEW)
        tab1.columnconfigure(0, weight=1)
        tab1.rowconfigure(7, weight=1)

        self.dl_log = tk.Text(log_frame, height=12, wrap=tk.WORD, font=("Menlo", 10))
        scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.dl_log.yview)
        self.dl_log.config(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.dl_log.pack(fill=tk.BOTH, expand=True)

        # ── Tab 2 ──
        tab2 = ttk.Frame(notebook, padding=12)
        notebook.add(tab2, text="Descargar Guion")

        ttk.Label(tab2, text="URL de TikTok:").grid(row=0, column=0, sticky=tk.W, pady=(0,4))
        ttk.Entry(tab2, textvariable=self.tr_url_var, width=60).grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(0,8))

        ttk.Label(tab2, text="Carpeta de destino:").grid(row=2, column=0, sticky=tk.W, pady=(0,4))
        ttk.Entry(tab2, textvariable=self.tr_dir_var, width=50).grid(row=3, column=0, sticky=tk.EW, pady=(0,8))
        ttk.Button(tab2, text="Examinar", command=self._browse_tr_dir).grid(row=3, column=1, padx=(6,0), pady=(0,8))
        ttk.Button(tab2, text="Abrir", command=self._open_tr_dir).grid(row=3, column=2, padx=(6,0), pady=(0,8))

        model_frame = ttk.Frame(tab2)
        model_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(0,8))
        ttk.Label(model_frame, text="Modelo Whisper:").pack(side=tk.LEFT)
        models = ["tiny", "base", "small", "medium", "large", "turbo"]
        model_menu = ttk.Combobox(model_frame, textvariable=self.whisper_model_var,
                                  values=models, state="readonly", width=10)
        model_menu.pack(side=tk.LEFT, padx=(6,0))
        ttk.Label(model_frame, text="  (tiny=rapido, large=preciso)").pack(side=tk.LEFT)

        self.tr_btn = ttk.Button(tab2, text="Descargar Guion", command=self._on_transcribe)
        self.tr_btn.grid(row=5, column=0, columnspan=3, pady=(4,8))

        ttk.Separator(tab2, orient=tk.HORIZONTAL).grid(row=6, column=0, columnspan=3, sticky=tk.EW, pady=8)

        ttk.Label(tab2, text="Log:").grid(row=7, column=0, sticky=tk.W)
        log_frame2 = ttk.Frame(tab2)
        log_frame2.grid(row=8, column=0, columnspan=3, sticky=tk.NSEW)
        tab2.columnconfigure(0, weight=1)
        tab2.rowconfigure(8, weight=1)

        self.tr_log = tk.Text(log_frame2, height=12, wrap=tk.WORD, font=("Menlo", 10))
        scroll2 = ttk.Scrollbar(log_frame2, orient=tk.VERTICAL, command=self.tr_log.yview)
        self.tr_log.config(yscrollcommand=scroll2.set)
        scroll2.pack(side=tk.RIGHT, fill=tk.Y)
        self.tr_log.pack(fill=tk.BOTH, expand=True)

    # ── Actions ──

    def _browse_dl_dir(self):
        d = filedialog.askdirectory(initialdir=self.dl_dir_var.get() or DEFAULT_DOWNLOAD_DIR)
        if d:
            self.dl_dir_var.set(d)

    def _browse_tr_dir(self):
        d = filedialog.askdirectory(initialdir=self.tr_dir_var.get() or DEFAULT_DOWNLOAD_DIR)
        if d:
            self.tr_dir_var.set(d)

    def _open_dl_dir(self):
        d = self.dl_dir_var.get() or DEFAULT_DOWNLOAD_DIR
        os.makedirs(d, exist_ok=True)
        subprocess.Popen(["open", d])

    def _open_tr_dir(self):
        d = self.tr_dir_var.get() or DEFAULT_DOWNLOAD_DIR
        os.makedirs(d, exist_ok=True)
        subprocess.Popen(["open", d])

    def _open_downloads(self):
        d = self.dl_dir_var.get() or DEFAULT_DOWNLOAD_DIR
        os.makedirs(d, exist_ok=True)
        subprocess.Popen(["open", d])

    def _on_download_video(self):
        url = self.dl_url_var.get().strip()
        if not url:
            messagebox.showwarning("URL vacia", "Pega un link de TikTok primero.")
            return
        d = self.dl_dir_var.get().strip() or DEFAULT_DOWNLOAD_DIR
        self.status_bar.config(text="Descargando...")
        threading.Thread(target=download_video, args=(url, d, self.dl_log, self.dl_btn, self.status_bar), daemon=True).start()

    def _on_transcribe(self):
        url = self.tr_url_var.get().strip()
        if not url:
            messagebox.showwarning("URL vacia", "Pega un link de TikTok primero.")
            return
        d = self.tr_dir_var.get().strip() or DEFAULT_DOWNLOAD_DIR
        self.status_bar.config(text="Transcribiendo...")
        transcribe_video(url, d, self.tr_log, self.tr_btn, self.status_bar, self.whisper_model_var)

    def _show_about(self):
        messagebox.showinfo("Acerca de " + APP_NAME,
            APP_NAME + " v" + APP_VERSION + "\n\n"
            "Descarga videos de TikTok y transcribe su audio.\n\n"
            "Motor: yt-dlp + Whisper (OpenAI)\n"
            "Hecho para Dr. Walter Garcia - Julio 2026")

    def run(self):
        self.root.mainloop()


# ── Entry ──
if __name__ == "__main__":
    app = TikTokDownloaderApp()
    app.run()
