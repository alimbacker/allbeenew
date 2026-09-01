"""Qt stylesheet matching the web dashboard.

Same warm graphite and honey as the browser UI, so the uploader looks like
part of the same product rather than a utility bolted on.
"""

INK = "#14120E"
INK_RAISED = "#1E1B16"
INK_SUNKEN = "#0E0C09"
LINE = "#332E25"
HONEY = "#F0A500"
HONEY_BRIGHT = "#FFD23F"
CHALK = "#F5F1E8"
CHALK_SOFT = "#A39A8A"
GO = "#46A758"
ALERT = "#E5484D"

STYLESHEET = f"""
QWidget {{
    background: {INK};
    color: {CHALK};
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 13px;
}}
QLabel#Title {{ font-size: 19px; font-weight: 700; }}
QLabel#Caption {{ color: {CHALK_SOFT}; }}
QLabel#Value {{ font-size: 22px; font-weight: 700; }}
QLabel#ValueHoney {{ font-size: 22px; font-weight: 700; color: {HONEY}; }}
QLabel#ValueAlert {{ font-size: 22px; font-weight: 700; color: {ALERT}; }}

QFrame#Panel {{
    background: {INK_RAISED};
    border: 1px solid {LINE};
    border-radius: 10px;
}}

QLineEdit, QComboBox {{
    background: {INK_SUNKEN};
    border: 1px solid {LINE};
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: {HONEY};
    selection-color: {INK};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {HONEY}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {INK_RAISED};
    border: 1px solid {LINE};
    selection-background-color: {HONEY};
    selection-color: {INK};
}}

QPushButton {{
    background: {INK_RAISED};
    border: 1px solid {LINE};
    border-radius: 6px;
    padding: 8px 16px;
}}
QPushButton:hover {{ border-color: {HONEY}; }}
QPushButton:disabled {{ color: {CHALK_SOFT}; border-color: {LINE}; }}
QPushButton#Primary {{
    background: {HONEY};
    color: {INK};
    border: none;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {HONEY_BRIGHT}; }}
QPushButton#Primary:disabled {{ background: {LINE}; color: {CHALK_SOFT}; }}

QProgressBar {{
    background: {INK_SUNKEN};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {HONEY}; border-radius: 5px; }}

QPlainTextEdit {{
    background: {INK_SUNKEN};
    border: 1px solid {LINE};
    border-radius: 8px;
    font-family: Consolas, "SF Mono", monospace;
    font-size: 12px;
    color: {CHALK_SOFT};
}}
"""
