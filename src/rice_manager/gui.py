
"""Rice Manager desktop application."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .shell_switch import ShellSwitchError, switch_shell, _running_shells, _shells
from .github_import import GitHubImportError, scan_github_repository
from .shell_deletion import ShellDeletionError, preview_shell_deletion
from .github_install import (
    GitHubInstallError,
    prepare_github_shell,
    preview_github_install,
    install_github_shell,
    delete_github_shell,
)


BG = "#11111b"
SIDEBAR = "#181825"
PANEL = "#1e1e2e"
CARD = "#242438"
HOVER = "#313149"
ACCENT = "#cba6f7"
BLUE = "#89b4fa"
GREEN = "#a6e3a1"
TEXT = "#cdd6f4"
MUTED = "#9399b2"
BORDER = "#363650"


class RiceManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Rice Manager")
        self.root.geometry("1120x740")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)

        self.nav_buttons = {}
        self.active_page = "Dashboard"
        self.github_stage_path = None
        self.github_scan_queue = queue.Queue()
        self.github_task_queue = queue.Queue()
        self.github_progress_queue = queue.Queue()
        self.github_task_thread = None
        self.github_task_busy = False
        self.github_pending_preview = None

        self.configure_style()
        self.build_layout()
        self.show_dashboard()

    def configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=CARD,
            foreground=TEXT,
            fieldbackground=CARD,
            rowheight=34,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=SIDEBAR,
            foreground=ACCENT,
            borderwidth=0,
        )

    def build_layout(self):
        self.sidebar = tk.Frame(self.root, bg=SIDEBAR, width=225)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=SIDEBAR)
        brand.pack(fill="x", padx=22, pady=(30, 8))

        tk.Label(
            brand,
            text="◈",
            bg=SIDEBAR,
            fg=ACCENT,
            font=("Sans", 23, "bold"),
        ).pack(side="left", padx=(0, 10))

        tk.Label(
            brand,
            text="RICE MANAGER",
            bg=SIDEBAR,
            fg=TEXT,
            font=("Sans", 14, "bold"),
        ).pack(side="left")

        tk.Label(
            self.sidebar,
            text="DESKTOP ENVIRONMENT",
            bg=SIDEBAR,
            fg=MUTED,
            font=("Sans", 8, "bold"),
        ).pack(anchor="w", padx=24, pady=(3, 35))

        tk.Label(
            self.sidebar,
            text="WORKSPACE",
            bg=SIDEBAR,
            fg=MUTED,
            font=("Sans", 8, "bold"),
        ).pack(anchor="w", padx=24, pady=(0, 10))

        pages = [
            ("Dashboard", "⌂", self.show_dashboard),
            ("Shells", "◈", self.show_shells),
            ("Profiles", "▤", self.show_profiles),
            ("GitHub Import", "⇩", self.show_github_import),
            ("Backups", "◷", self.show_backups),
            ("Settings", "⚙", self.show_settings),
        ]

        for name, symbol, callback in pages:
            button = tk.Button(
                self.sidebar,
                text=f"   {symbol}    {name}",
                command=callback,
                anchor="w",
                bg=SIDEBAR,
                fg=MUTED,
                activebackground=HOVER,
                activeforeground=ACCENT,
                relief="flat",
                bd=0,
                font=("Sans", 11),
                padx=15,
                pady=13,
                cursor="hand2",
            )
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[name] = button

        footer = tk.Frame(self.sidebar, bg=SIDEBAR)
        footer.pack(side="bottom", fill="x", padx=20, pady=22)

        tk.Frame(footer, bg=BORDER, height=1).pack(fill="x", pady=(0, 14))

        tk.Label(
            footer,
            text="RICE MANAGER",
            bg=SIDEBAR,
            fg=ACCENT,
            font=("Sans", 9, "bold"),
        ).pack(anchor="w")

        tk.Label(
            footer,
            text="Version 0.19.1  •  Desktop",
            bg=SIDEBAR,
            fg=MUTED,
            font=("Sans", 8),
        ).pack(anchor="w", pady=(4, 0))

        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="right", fill="both", expand=True)

        self.topbar = tk.Frame(self.main, bg=BG, height=65)
        self.topbar.pack(fill="x", padx=35, pady=(18, 0))
        self.topbar.pack_propagate(False)

        tk.Label(
            self.topbar,
            text="◉  SYSTEM READY",
            bg=BG,
            fg=GREEN,
            font=("Sans", 9, "bold"),
        ).pack(side="right", anchor="center")

        tk.Frame(self.main, bg=BORDER, height=1).pack(
            fill="x", padx=35, pady=(0, 5)
        )

        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True)

    def set_active(self, page):
        self.active_page = page
        for name, button in self.nav_buttons.items():
            selected = name == page
            button.configure(
                bg=HOVER if selected else SIDEBAR,
                fg=ACCENT if selected else MUTED,
                font=("Sans", 11, "bold" if selected else "normal"),
            )

    def clear(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def heading(self, title, subtitle, page):
        self.set_active(page)

        tk.Label(
            self.content,
            text=title,
            bg=BG,
            fg=TEXT,
            font=("Sans", 25, "bold"),
        ).pack(anchor="w", padx=38, pady=(25, 5))

        tk.Label(
            self.content,
            text=subtitle,
            bg=BG,
            fg=MUTED,
            font=("Sans", 10),
        ).pack(anchor="w", padx=40, pady=(0, 26))

    def card(self, parent, title, description, accent=ACCENT):
        frame = tk.Frame(
            parent,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=22,
            pady=20,
        )

        tk.Frame(frame, bg=accent, width=4).pack(side="left", fill="y", padx=(0, 17))

        body = tk.Frame(frame, bg=CARD)
        body.pack(side="left", fill="both", expand=True)

        tk.Label(
            body,
            text=title,
            bg=CARD,
            fg=TEXT,
            font=("Sans", 13, "bold"),
        ).pack(anchor="w")

        tk.Label(
            body,
            text=description,
            bg=CARD,
            fg=MUTED,
            font=("Sans", 10),
            justify="left",
            wraplength=570,
        ).pack(anchor="w", pady=(8, 0))

        return frame

    def make_button(self, parent, label, command, primary=False):
        background = ACCENT if primary else PANEL
        foreground = BG if primary else TEXT

        return tk.Button(
            parent,
            text=label,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=BLUE if primary else HOVER,
            activeforeground=BG if primary else ACCENT,
            relief="flat",
            bd=0,
            padx=17,
            pady=10,
            font=("Sans", 9, "bold"),
            cursor="hand2",
        )

    def show_dashboard(self):
        self.clear()
        self.heading(
            "Dashboard",
            "Welcome to your desktop environment.",
            "Dashboard",
        )

        try:
            running = _running_shells()
            active = [
                name for name, instances in running.items() if instances
            ]
            status = ", ".join(active) if active else "No managed shell detected"
            status_color = GREEN if active else MUTED
        except (ShellSwitchError, OSError) as exc:
            status = f"Status unavailable: {exc}"
            status_color = "#f38ba8"

        status_card = self.card(
            self.content,
            "Active Desktop Shell",
            status,
            status_color,
        )
        status_card.pack(fill="x", padx=38, pady=8)

        self.card(
            self.content,
            "Available Environments",
            "Cartoon Shell     •     Caelestia",
            BLUE,
        ).pack(fill="x", padx=38, pady=8)

        self.card(
            self.content,
            "Safety Protection",
            "Preview-first operations and protected configuration workflows.",
            GREEN,
        ).pack(fill="x", padx=38, pady=8)

        self.make_button(
            self.content,
            "Manage Shells  →",
            self.show_shells,
            primary=True,
        ).pack(anchor="w", padx=38, pady=20)

    def show_shells(self):
        self.clear()
        self.heading(
            "Shell Manager",
            "Choose and manage your desktop environment.",
            "Shells",
        )

        try:
            shells = _shells()
        except ShellSwitchError as exc:
            messagebox.showerror("Shell Manager", str(exc))
            return

        for shell_id, config in shells.items():
            name = config["name"]

            if config.get("type") == "caelestia":
                description = "The Caelestia shell environment."
            elif shell_id == "cartoon-shell":
                description = "Your custom Quickshell desktop environment."
            else:
                description = (
                    "GitHub-installed Quickshell environment.\n"
                    f"Repository: {config.get('repository', 'Unknown')}"
                )

            frame = self.card(self.content, name, description, ACCENT)
            frame.pack(fill="x", padx=38, pady=10)

            buttons = tk.Frame(frame, bg=CARD)
            buttons.pack(anchor="w", pady=(17, 0))

            self.make_button(
                buttons,
                "Preview",
                lambda target=shell_id: self.switch(target, False),
            ).pack(side="left", padx=(0, 9))

            self.make_button(
                buttons,
                "Switch Environment",
                lambda target=shell_id: self.switch(target, True),
                primary=True,
            ).pack(side="left")

            self.make_button(
                buttons,
                "Preview Deletion",
                lambda target=shell_id: self.delete_shell(target),
            ).pack(side="left", padx=(9, 0))

            if shell_id not in {"cartoon-shell", "caelestia"} and config.get("repository"):
                self.make_button(
                    buttons,
                    "Delete Installed Shell",
                    lambda target=shell_id: self.delete_installed_shell(target),
                ).pack(side="left", padx=(9, 0))

    def delete_shell(self, shell_id):
        try:
            report = preview_shell_deletion(shell_id)
        except (ShellDeletionError, OSError) as exc:
            messagebox.showerror("Deletion Preview", str(exc))
            return

        details = [
            f"Shell: {report['name']}",
            "Status: Not running",
            "",
            "Paths planned for removal:",
        ]
        details.extend(
            f"  • {item}" for item in report["paths"]
        )

        details.append("")
        details.append("Packages planned for removal:")
        details.extend(
            f"  • {item}" for item in report["packages"]
        )

        if report["protected_packages"]:
            details.append("")
            details.append("Protected packages (will not be removed):")
            details.extend(
                f"  • {item}" for item in report["protected_packages"]
            )

        details.extend([
            "",
            "PREVIEW ONLY",
            "No files, packages, or registry entries were removed.",
        ])

        messagebox.showinfo("Deletion Preview", "\n".join(details))

    def delete_installed_shell(self, shell_id):
        """Delete a registered GitHub shell after explicit confirmation."""
        try:
            preview = preview_shell_deletion(shell_id)
        except (ShellDeletionError, OSError) as exc:
            messagebox.showerror("Delete Installed Shell", str(exc))
            return

        if shell_id in {"cartoon-shell", "caelestia"}:
            messagebox.showwarning(
                "Delete Installed Shell",
                "Built-in shells cannot be deleted here.",
            )
            return

        confirmed = messagebox.askyesno(
            "Permanently Delete Shell",
            f"Delete {preview['name']} and its Rice Manager registry entry?\\n\\n"
            + "\\n".join(preview["paths"])
            + "\\n\\nThis cannot be undone.",
        )
        if not confirmed:
            return
        try:
            result = delete_github_shell(shell_id, confirm=True)
        except (GitHubInstallError, OSError) as exc:
            messagebox.showerror("Delete Installed Shell", str(exc))
            return

        messagebox.showinfo(
            "Shell Deleted",
            f"{result['name']} was deleted and unregistered.",
        )
        self.show_shells()

    def switch(self, target, apply):
        if apply:
            try:
                name = _shells()[target]["name"]
            except (ShellSwitchError, KeyError) as exc:
                messagebox.showerror("Shell Manager", str(exc))
                return

            confirmed = messagebox.askyesno(
                "Confirm Shell Switch",
                f"Switch your desktop shell to {name}?\n\n"
                "The currently running shell will be stopped.",
            )
            if not confirmed:
                return

        try:
            report = switch_shell(target, apply=apply)
        except (ShellSwitchError, OSError) as exc:
            messagebox.showerror("Shell Manager", str(exc))
            return

        if not apply:
            messagebox.showinfo(
                "Switch Preview",
                f"Target: {report['name']}\n"
                f"Currently running: "
                f"{', '.join(report['currently_running']) or 'None'}\n\n"
                "No changes were made.",
            )
            return

        messagebox.showinfo(
            "Shell Manager",
            f"{report['name']} switch completed.",
        )
        self.show_dashboard()

    def show_profiles(self):
        self.clear()
        self.heading(
            "Profiles",
            "Manage your desktop configuration profiles.",
            "Profiles",
        )
        self.card(
            self.content,
            "Profile Management",
            "Use the existing Rice Manager profile commands "
            "to inspect, import and manage profiles.\n\n"
            "The desktop profile controls can be connected to "
            "the profile backend in a later step.",
            BLUE,
        ).pack(fill="x", padx=38)

    def show_github_import(self):
        self.clear()
        self.heading(
            "GitHub Import",
            "Scan, preview and safely install public Quickshell repositories.",
            "GitHub Import",
        )

        card = self.card(
            self.content,
            "Repository Scanner",
            "Paste a public GitHub repository URL. Rice Manager will "
            "inspect its Quickshell configuration before preparing an install.",
            ACCENT,
        )
        card.pack(fill="x", padx=38, pady=8)

        body = card.winfo_children()[1]

        tk.Label(
            body,
            text="GITHUB REPOSITORY URL",
            bg=CARD,
            fg=MUTED,
            font=("Sans", 9, "bold"),
        ).pack(anchor="w", pady=(18, 7))

        self.github_url = tk.StringVar()
        url_entry = tk.Entry(
            body,
            textvariable=self.github_url,
            bg=PANEL,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Sans", 11),
        )
        url_entry.pack(fill="x", ipady=10)

        self.github_scan_button = self.make_button(
            body,
            "Scan Repository",
            self.scan_github,
            primary=True,
        )
        self.github_scan_button.pack(anchor="w", pady=(14, 0))

        self.github_results_container = tk.Frame(self.content, bg=BG)
        self.github_results_container.pack(
            fill="both", expand=True, padx=38, pady=12
        )

        canvas = tk.Canvas(
            self.github_results_container,
            bg=BG,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            self.github_results_container,
            orient="vertical",
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.github_results = tk.Frame(canvas, bg=BG)
        window = canvas.create_window(
            (0, 0), window=self.github_results, anchor="nw"
        )

        self.github_results.bind(
            "<Configure>",
            lambda event: canvas.configure(
                scrollregion=canvas.bbox("all")
            ),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                window, width=event.width
            ),
        )

        canvas.bind(
            "<Button-4>",
            lambda event: canvas.yview_scroll(-3, "units"),
        )
        canvas.bind(
            "<Button-5>",
            lambda event: canvas.yview_scroll(3, "units"),
        )
        canvas.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(
                -int(event.delta / 120), "units"
            ),
        )

        if self.github_task_busy:
            self.github_scan_button.configure(
                state="disabled", text="Working..."
            )
        if self.github_pending_preview:
            self._render_github_install_preview(
                self.github_pending_preview
            )

    def scan_github(self):
        if self.github_task_busy:
            return
        url = self.github_url.get().strip()
        if not url:
            messagebox.showwarning(
                "GitHub Import",
                "Enter a public GitHub repository URL first.",
            )
            return

        self.github_stage_path = None
        self.github_pending_preview = None
        self.github_scan_button.configure(
            state="disabled",
            text="Scanning...",
        )

        for widget in self.github_results.winfo_children():
            widget.destroy()

        self._show_github_progress("Scanning repository...")

        self._github_scan_thread = threading.Thread(
            target=self._scan_github_worker,
            args=(url,),
            daemon=True,
        )
        self._github_scan_thread.start()
        self.root.after(100, self._poll_github_scan)

    def _scan_github_worker(self, url):
        try:
            report = scan_github_repository(
                url,
                progress_callback=lambda phase, current, total:
                    self.github_progress_queue.put(
                        ("scan", phase, current, total)
                    ),
            )
            self.github_scan_queue.put(("success", report))
        except Exception as exc:
            self.github_scan_queue.put(("error", str(exc)))

    def _poll_github_scan(self):
        self._poll_github_progress()
        try:
            result_type, result = self.github_scan_queue.get_nowait()
        except queue.Empty:
            if self._github_scan_thread.is_alive():
                self.root.after(100, self._poll_github_scan)
            else:
                self._github_scan_failed(
                    "The scan worker stopped without returning a result."
                )
            return

        if result_type == "error":
            self._github_scan_failed(result)
        else:
            try:
                self._render_github_report(result)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                self._github_scan_failed(f"Report rendering failed: {exc}")

    def _github_scan_failed(self, error):
        self.github_scan_button.configure(
            state="normal",
            text="Scan Repository",
        )
        for widget in self.github_results.winfo_children():
            widget.destroy()
        messagebox.showerror("GitHub Scan Failed", error)

    def _render_github_report(self, report):
        self.github_scan_button.configure(
            state="normal",
            text="Scan Repository",
        )

        for widget in self.github_results.winfo_children():
            widget.destroy()

        repository = report["repository"]
        summary = report["summary"]
        compatibility = report["compatibility"]
        status = compatibility["status"]

        status_color = {
            "compatible": GREEN,
            "partial": "#fab387",
            "unsupported": "#f38ba8",
        }.get(status, MUTED)

        self.card(
            self.github_results,
            f"{repository['name']}  •  {status.upper()}",
            f"Branch: {repository['branch']}\n"
            f"{compatibility['reason']}\n"
            f"Files scanned: {summary['files_scanned']}\n"
            f"Components detected: {summary['components_detected']}",
            status_color,
        ).pack(fill="x", pady=6)

        quickshell_configs = report.get("configurations") or []
        if quickshell_configs:
            for index, config in enumerate(quickshell_configs, 1):
                source = config.get("source_root") or "(repository root)"
                status_text = config.get("compatibility", "partial").upper()
                frame = self.card(
                    self.github_results,
                    f"Quickshell Configuration {index} • {status_text}",
                    f"Source: {source}\\n"
                    f"Files: {config['file_count']}\\n"
                    f"Entrypoint: {config['entrypoint'] or 'Not detected'}",
                    GREEN if status_text == "COMPATIBLE" else "#fab387",
                )
                frame.pack(fill="x", pady=5)
                if config.get("compatibility") == "compatible":
                    self.make_button(
                        frame,
                        "Prepare This Configuration",
                        lambda target=config.get("source_root", ""):
                            self.prepare_github_install(target),
                        primary=True,
                    ).pack(anchor="w", pady=(10, 0))
        else:
            for component in report["components"]:
                self.card(
                    self.github_results,
                    component["name"],
                    f"Source: {component['source_root']}\\n"
                    f"Destination: {component['destination']}\\n"
                    f"Files: {component['file_count']}\\n"
                    f"Dependency: {component['dependency']}\\n"
                    f"Entrypoint: {component['entrypoint'] or 'Not detected'}",
                    BLUE,
                ).pack(fill="x", pady=5)

        warnings = (
            f"Scripts flagged: {summary['scripts_flagged']}\n"
            f"Unsafe entries: {summary['unsafe_entries']}\n"
            f"Oversized entries: {summary['oversized_entries']}\n"
            f"Unclassified files: {report['unclassified_files']}"
        )
        self.card(
            self.github_results,
            "Scan Safety Report",
            warnings,
            GREEN if not any((
                summary["scripts_flagged"],
                summary["unsafe_entries"],
                summary["oversized_entries"],
            )) else "#f38ba8",
        ).pack(fill="x", pady=6)

        if status != "compatible":
            tk.Label(
                self.github_results,
                text=compatibility["reason"],
                bg=BG,
                fg="#f38ba8",
                font=("Sans", 9, "bold"),
            ).pack(anchor="w", pady=10)

        tk.Label(
            self.github_results,
            text="READ-ONLY SCAN • NOTHING INSTALLED OR EXECUTED",
            bg=BG,
            fg=GREEN,
            font=("Sans", 9, "bold"),
        ).pack(anchor="w", pady=10)

    def _start_github_task(self, task, value):
        if self.github_task_busy:
            return
        self.github_task_busy = True
        self.github_task_thread = threading.Thread(
            target=self._github_task_worker,
            args=(task, value),
            daemon=True,
        )
        self.github_task_thread.start()
        self.root.after(100, self._poll_github_task)

    def _github_task_worker(self, task, value):
        progress = lambda phase, current, total: self.github_progress_queue.put(
            (task, phase, current, total)
        )
        try:
            if task == "prepare":
                url, source_root = value
                staged = prepare_github_shell(
                    url,
                    source_root=source_root,
                    progress_callback=progress,
                )
                result = preview_github_install(staged["staging_path"])
            elif task == "install":
                result = install_github_shell(
                    value, confirm=True, progress_callback=progress
                )
            else:
                raise ValueError("Unknown GitHub task.")
            self.github_task_queue.put((task, "success", result))
        except Exception as exc:
            self.github_task_queue.put((task, "error", str(exc)))

    def _poll_github_task(self):
        self._poll_github_progress()
        try:
            task, status, result = self.github_task_queue.get_nowait()
        except queue.Empty:
            if self.github_task_thread and self.github_task_thread.is_alive():
                self.root.after(100, self._poll_github_task)
                return
            self.github_task_busy = False
            self._set_github_scan_enabled(True)
            messagebox.showerror(
                "GitHub Import",
                "Background task stopped without returning a result.",
            )
            return

        self.github_task_busy = False
        self._set_github_scan_enabled(True)

        if status == "error":
            if task == "install" and self.active_page == "GitHub Import":
                if self.github_pending_preview:
                    self._render_github_install_preview(
                        self.github_pending_preview
                    )
            messagebox.showerror(
                "Installation Failed" if task == "install"
                else "Installation Preview Failed",
                result,
            )
            return

        if task == "prepare":
            self.github_stage_path = result["source"]
            self.github_pending_preview = result
            if self.active_page == "GitHub Import":
                self._render_github_install_preview(result)

        elif task == "install":
            self.github_stage_path = None
            self.github_pending_preview = None
            messagebox.showinfo(
                "Installation Complete",
                f"{result['repository']['name']} was installed and registered.\n\n"
                f"Location: {result['destination']}\n\n"
                "The shell has not been launched. Open Shells to preview "
                "or switch to it when ready.",
            )
            if self.active_page == "GitHub Import":
                self.show_shells()

    def _set_github_scan_enabled(self, enabled):
        button = getattr(self, "github_scan_button", None)
        if button is not None and button.winfo_exists():
            button.configure(state="normal" if enabled else "disabled")

    def prepare_github_install(self, source_root=None):
        if self.github_task_busy:
            return
        url = self.github_url.get().strip()
        if not url:
            return

        self.github_stage_path = None
        self.github_pending_preview = None
        self._set_github_scan_enabled(False)

        for widget in self.github_results.winfo_children():
            widget.destroy()

        self._show_github_progress("Preparing configuration...")
        self._start_github_task("prepare", (url, source_root))

    def _show_github_progress(self, message):
        self.github_progress_label = tk.Label(
            self.github_results, text=message, bg=BG, fg=BLUE,
            font=("Sans", 10, "bold"),
        )
        self.github_progress_label.pack(anchor="w", pady=(8, 3))
        self.github_progress_bar = ttk.Progressbar(
            self.github_results, mode="indeterminate", length=420,
        )
        self.github_progress_bar.pack(anchor="w", fill="x", pady=(0, 10))
        self.github_progress_bar.start(10)

    def _poll_github_progress(self):
        latest = None
        while True:
            try:
                latest = self.github_progress_queue.get_nowait()
            except queue.Empty:
                break
        if latest is None:
            return
        task, phase, current, total = latest
        label = getattr(self, "github_progress_label", None)
        bar = getattr(self, "github_progress_bar", None)
        if label is None or not label.winfo_exists():
            return
        if phase in ("download", "submodule-download"):
            description = (
                "Downloading submodule"
                if phase == "submodule-download"
                else "Downloading repository"
            )
            if total:
                percent = min(100, current * 100 // total)
                label.configure(
                    text=f"{description}: {current:,} / {total:,} bytes ({percent}%)"
                )
                if bar and bar.winfo_exists():
                    bar.stop()
                    bar.configure(mode="determinate", maximum=total, value=current)
            else:
                label.configure(text=f"{description}: {current:,} bytes")
        elif phase == "extract":
            label.configure(text=f"Extracting configuration: {current:,} / {total:,} files")
            if bar and bar.winfo_exists():
                bar.stop()
                bar.configure(mode="determinate", maximum=max(1, total), value=current)
        elif phase == "install":
            label.configure(text=f"Installing files: {current:,} / {total:,} bytes")
            if bar and bar.winfo_exists():
                bar.stop()
                bar.configure(mode="determinate", maximum=max(1, total), value=current)

    def _render_github_install_preview(self, preview):
        for widget in self.github_results.winfo_children():
            widget.destroy()

        repository = preview["repository"]
        file_lines = [
            f"{item['path']}  ({item['size']} bytes)"
            for item in preview["files"][:100]
        ]
        if len(preview["files"]) > 100:
            file_lines.append(
                f"... and {len(preview['files']) - 100} more files"
            )

        self.card(
            self.github_results,
            "Installation Preview",
            f"Repository: {repository['name']}\n"
            f"Branch: {repository['branch']}\n"
            f"Files: {preview['file_count']}\n"
            f"Total size: {preview['total_bytes']} bytes\n"
            f"Flagged scripts: {preview['scripts_flagged']}\n"
            f"Destination: {preview['destination']}",
            GREEN,
        ).pack(fill="x", pady=6)

        self.card(
            self.github_results,
            "Files to Install",
            "\n".join(file_lines) or "No files found.",
            BLUE,
        ).pack(fill="x", pady=6)

        self.card(
            self.github_results,
            "Security Warning",
            "Repository scripts will NOT be executed during installation.\n"
            "Quickshell configurations can execute commands when launched.\n"
            "Only install repositories you trust.",
            "#f38ba8",
        ).pack(fill="x", pady=6)

        self.make_button(
            self.github_results,
            "Confirm and Install Shell",
            self.confirm_github_install,
            primary=True,
        ).pack(anchor="w", pady=12)

        tk.Label(
            self.github_results,
            text="PREVIEW ONLY • NO CONFIGURATION FILES INSTALLED YET",
            bg=BG, fg=GREEN, font=("Sans", 9, "bold"),
        ).pack(anchor="w", pady=8)

    def confirm_github_install(self):
        if self.github_task_busy:
            return
        if not self.github_stage_path:
            messagebox.showwarning(
                "GitHub Import",
                "Prepare an installation preview first.",
            )
            return

        confirmed = messagebox.askyesno(
            "Confirm Shell Installation",
            "Install this Quickshell configuration?\n\n"
            "Files will be copied to your Quickshell configuration directory "
            "and the shell will be registered in Rice Manager.\n\n"
            "No shell will be launched automatically. Only install "
            "repositories you trust.",
        )
        if not confirmed:
            return

        stage_path = self.github_stage_path
        self._set_github_scan_enabled(False)

        for widget in self.github_results.winfo_children():
            widget.destroy()

        self._show_github_progress("Installing shell...")
        self._start_github_task("install", stage_path)

    def show_backups(self):
        self.clear()
        self.heading(
            "Backups",
            "Protect and restore your configurations.",
            "Backups",
        )
        self.card(
            self.content,
            "Backup Manager",
            "Backup and restore operations are available through "
            "the existing CLI backend.\n\n"
            "Dedicated desktop controls are a separate next step.",
            GREEN,
        ).pack(fill="x", padx=38)

    def show_settings(self):
        self.clear()
        self.heading(
            "Settings",
            "Application information and preferences.",
            "Settings",
        )
        self.card(
            self.content,
            "Application",
            "Rice Manager 0.19.1\n"
            "Desktop interface: Tkinter\n"
            "Theme: Caelestia-inspired Catppuccin Mocha",
            ACCENT,
        ).pack(fill="x", padx=38)


def main():
    root = tk.Tk()
    RiceManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
