"""
OpenPipeFlow — Dark industrial control-room QSS stylesheet.
"""

DARK_THEME_QSS = """
/* ─── Global ─────────────────────────────────────────────────────────────── */
QWidget {
    background-color: #0e1117;
    color: #e8edf2;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #0e1117;
}

/* ─── Menu bar ───────────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #141b24;
    color: #e8edf2;
    border-bottom: 1px solid #1e2d3d;
    padding: 2px;
}
QMenuBar::item:selected {
    background-color: #1e2d3d;
    border-radius: 3px;
}
QMenu {
    background-color: #141b24;
    border: 1px solid #1e2d3d;
    padding: 4px 0;
}
QMenu::item {
    padding: 5px 24px 5px 12px;
}
QMenu::item:selected {
    background-color: #00d4aa22;
    color: #00d4aa;
}
QMenu::separator {
    height: 1px;
    background-color: #1e2d3d;
    margin: 4px 8px;
}

/* ─── Toolbar ────────────────────────────────────────────────────────────── */
QToolBar {
    background-color: #141b24;
    border-bottom: 1px solid #1e2d3d;
    spacing: 4px;
    padding: 4px;
}
QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e8edf2;
    min-width: 48px;
}
QToolButton:hover {
    background-color: #1e2d3d;
    border-color: #00d4aa44;
}
QToolButton:checked, QToolButton:pressed {
    background-color: #00d4aa22;
    border-color: #00d4aa;
    color: #00d4aa;
}
QToolBar::separator {
    width: 1px;
    background-color: #1e2d3d;
    margin: 4px 4px;
}

/* ─── Status bar ─────────────────────────────────────────────────────────── */
QStatusBar {
    background-color: #141b24;
    border-top: 1px solid #1e2d3d;
    color: #aab3be;
    font-size: 12px;
}
QStatusBar::item { border: none; }

/* ─── Dock widgets ───────────────────────────────────────────────────────── */
QDockWidget {
    titlebar-close-icon: none;
    border: 1px solid #1e2d3d;
}
QDockWidget::title {
    background-color: #141b24;
    text-align: left;
    padding: 6px 8px;
    border-bottom: 1px solid #1e2d3d;
    color: #00d4aa;
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
QDockWidget::close-button, QDockWidget::float-button {
    background: transparent;
    padding: 2px;
}

/* ─── Splitter ───────────────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #1e2d3d;
}

/* ─── Scroll bars ────────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #0e1117;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #1e2d3d;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background-color: #2a3d52; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background-color: #0e1117;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #1e2d3d;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background-color: #2a3d52; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ─── Tab widget ─────────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #1e2d3d;
    background-color: #1a2332;
}
QTabBar::tab {
    background-color: #141b24;
    border: 1px solid #1e2d3d;
    border-bottom: none;
    padding: 5px 14px;
    color: #aab3be;
}
QTabBar::tab:selected {
    background-color: #1a2332;
    color: #00d4aa;
    border-top: 2px solid #00d4aa;
}
QTabBar::tab:hover { color: #e8edf2; }

/* ─── Tree / Table views ─────────────────────────────────────────────────── */
QTreeView, QTableView {
    background-color: #1a2332;
    alternate-background-color: #1e2940;
    border: 1px solid #1e2d3d;
    gridline-color: #1e2d3d;
    selection-background-color: #00d4aa33;
    selection-color: #e8edf2;
}
QHeaderView::section {
    background-color: #141b24;
    color: #aab3be;
    padding: 4px 8px;
    border: none;
    border-right: 1px solid #1e2d3d;
    border-bottom: 1px solid #1e2d3d;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QTreeView::item:hover, QTableView::item:hover {
    background-color: #1e2d3d;
}

/* ─── Input widgets ──────────────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {
    background-color: #1a2332;
    border: 1px solid #2a3d52;
    border-radius: 3px;
    padding: 4px 8px;
    color: #e8edf2;
    selection-background-color: #00d4aa44;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QTextEdit:focus {
    border-color: #00d4aa;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #1a2332;
    border: 1px solid #2a3d52;
    selection-background-color: #00d4aa33;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #1e2d3d;
    border: none;
    width: 16px;
}

/* ─── Buttons ────────────────────────────────────────────────────────────── */
QPushButton {
    background-color: #1e2d3d;
    border: 1px solid #2a3d52;
    border-radius: 4px;
    padding: 5px 14px;
    color: #e8edf2;
    min-width: 70px;
}
QPushButton:hover {
    background-color: #2a3d52;
    border-color: #00d4aa44;
}
QPushButton:pressed {
    background-color: #00d4aa22;
    border-color: #00d4aa;
}
QPushButton:disabled {
    color: #445566;
    border-color: #1e2d3d;
}

/* ─── Group box ──────────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #1e2d3d;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    color: #aab3be;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #00d4aa;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ─── Labels ─────────────────────────────────────────────────────────────── */
QLabel#value_label {
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
    color: #00d4aa;
}
QLabel#alarm_label {
    color: #e74c3c;
    font-weight: bold;
}

/* ─── Checkboxes ─────────────────────────────────────────────────────────── */
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #2a3d52;
    border-radius: 2px;
    background-color: #1a2332;
}
QCheckBox::indicator:checked {
    background-color: #00d4aa;
    border-color: #00d4aa;
}

/* ─── Slider ─────────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 4px;
    background-color: #1e2d3d;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    background-color: #00d4aa;
    border-radius: 7px;
    margin: -5px 0;
}
QSlider::sub-page:horizontal {
    background-color: #00d4aa;
    border-radius: 2px;
}

/* ─── Progress bar ───────────────────────────────────────────────────────── */
QProgressBar {
    background-color: #1a2332;
    border: 1px solid #1e2d3d;
    border-radius: 3px;
    text-align: center;
    color: #e8edf2;
}
QProgressBar::chunk {
    background-color: #00d4aa;
    border-radius: 2px;
}

/* ─── Dialog ─────────────────────────────────────────────────────────────── */
QDialog {
    background-color: #141b24;
    border: 1px solid #1e2d3d;
}
QDialogButtonBox QPushButton { min-width: 80px; }
"""

# Colour constants used in Python code (must match the QSS above)
COLOR = {
    "background":       "#0e1117",
    "canvas_bg":        "#131920",
    "panel_bg":         "#1a2332",
    "header_bg":        "#141b24",
    "border":           "#1e2d3d",
    "accent":           "#00d4aa",
    "warning":          "#f5a623",
    "alarm":            "#e74c3c",
    "text":             "#e8edf2",
    "text_dim":         "#aab3be",
    "grid":             "#1e2d3d",
    # Pipe velocity colouring
    "pipe_static":      "#555566",
    "pipe_slow":        "#0066ff",
    "pipe_medium":      "#ffaa00",
    "pipe_fast":        "#ff2200",
    # Node types
    "node_junction":    "#00d4aa",
    "node_source":      "#2ecc71",
    "node_sink":        "#e74c3c",
    "node_measurement": "#f5a623",
}
