
"""Rice Manager desktop application."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .shell_switch import ShellSwitchError, switch_shell, _running_shells


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

        for shell_id, name, description in [
            (
                "cartoon-shell",
                "Cartoon Shell",
                "Your custom Quickshell desktop environment.",
            ),
            (
                "caelestia",
                "Caelestia",
                "The Caelestia shell environment.",
            ),
        ]:
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

    def switch(self, target, apply):
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
