"""OOPSIE-style reusable widget kit. All colors from styles.colors tokens."""
import customtkinter as ctk
from styles import colors as C


def _font(spec):
    weight = spec[2] if len(spec) > 2 else "normal"
    return {"family": spec[0], "size": spec[1], "weight": weight}


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", C.ACCENT)
        kw.setdefault("hover_color", C.ACCENT_HOVER)
        kw.setdefault("text_color", C.ACCENT_TEXT)
        kw.setdefault("corner_radius", C.BTN_RADIUS)
        kw.setdefault("height", C.BTN_H)
        kw.setdefault("font", ctk.CTkFont(**_font(C.FONT_H3)))
        super().__init__(master, **kw)


class GhostButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("hover_color", C.SURFACE2)
        kw.setdefault("text_color", C.TEXT_BODY)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", C.LINE)
        kw.setdefault("corner_radius", C.BTN_RADIUS)
        kw.setdefault("height", C.BTN_H)
        kw.setdefault("font", ctk.CTkFont(**_font(C.FONT_H3)))
        super().__init__(master, **kw)


class DangerButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", C.DANGER)
        kw.setdefault("hover_color", C.darken(C.DANGER))
        kw.setdefault("text_color", ("#ffffff", "#ffffff"))
        kw.setdefault("corner_radius", C.BTN_RADIUS)
        kw.setdefault("height", C.BTN_H)
        kw.setdefault("font", ctk.CTkFont(**_font(C.FONT_H3)))
        super().__init__(master, **kw)


class PageHeader(ctk.CTkFrame):
    def __init__(self, master, kicker, title, description="", action=None, **kw):
        kw.setdefault("fg_color", "transparent")
        super().__init__(master, **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=kicker.upper(), anchor="w",
                     font=ctk.CTkFont(**_font(C.FONT_KICKER)),
                     text_color=C.TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(self, text=title, anchor="w",
                     font=ctk.CTkFont(**_font(C.FONT_TITLE)),
                     text_color=C.TEXT_H1).grid(row=1, column=0, sticky="w", pady=(2, 0))
        if description:
            ctk.CTkLabel(self, text=description, anchor="w", justify="left",
                         font=ctk.CTkFont(**_font(C.FONT_DESC)),
                         text_color=C.TEXT_BODY).grid(row=2, column=0, sticky="w", pady=(6, 0))
        if action:
            GhostButton(self, text=action[0], command=action[1], height=34
                        ).grid(row=0, column=1, rowspan=2, sticky="e")


class Card(ctk.CTkFrame):
    def __init__(self, master, title=None, **kw):
        kw.setdefault("fg_color", C.SURFACE)
        kw.setdefault("corner_radius", C.CARD_RADIUS)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", C.LINE)
        super().__init__(master, **kw)
        self.grid_columnconfigure(0, weight=1)
        r = 0
        if title:
            ctk.CTkLabel(self, text=title, anchor="w",
                         font=ctk.CTkFont(**_font(C.FONT_H2)),
                         text_color=C.TEXT_H1).grid(row=0, column=0, sticky="ew",
                                                    padx=20, pady=(18, 0))
            r = 1
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=r, column=0, sticky="nsew", padx=20, pady=18)
        self.body.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(r, weight=1)
