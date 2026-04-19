"""Design tokens and theming primitives for SuperApp.

Centralizes colors, spacing, typography, and symbols so every frame has
a consistent look and accent changes propagate with one setting.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

VERSION = "1.1"


# Spacing scale (4pt grid)
SPACE_XS = 4
SPACE_SM = 8
SPACE = 12
SPACE_MD = 16
SPACE_LG = 20
SPACE_XL = 28
SPACE_2XL = 40

# Corner radius
RADIUS_SM = 6
RADIUS = 10
RADIUS_LG = 16

# Typography scale
FONT_DISPLAY = 28
FONT_H1 = 22
FONT_H2 = 18
FONT_H3 = 15
FONT_BODY = 13
FONT_SMALL = 11
FONT_TINY = 10

# Window defaults
WINDOW_DEFAULT = (1440, 900)
WINDOW_MIN = (1080, 680)
SIDEBAR_WIDTH = 232
STATUS_BAR_HEIGHT = 36

# Accent palettes — (light, dark) hex pairs for CTk dual-tone widgets
ACCENT_PALETTES: Dict[str, Dict[str, Tuple[str, str]]] = {
    "Blue": {
        "primary": ("#2F7DD8", "#1F6AA5"),
        "primary_hover": ("#256AB8", "#185784"),
        "soft": ("#DCEBFB", "#1A2A3A"),
    },
    "Violet": {
        "primary": ("#7C3AED", "#6D28D9"),
        "primary_hover": ("#6D28D9", "#5B21B6"),
        "soft": ("#EAE0FB", "#2A1E3E"),
    },
    "Emerald": {
        "primary": ("#10B981", "#059669"),
        "primary_hover": ("#059669", "#047857"),
        "soft": ("#DCFCE9", "#10231C"),
    },
    "Rose": {
        "primary": ("#F43F5E", "#E11D48"),
        "primary_hover": ("#E11D48", "#BE123C"),
        "soft": ("#FEE2EA", "#2A141B"),
    },
    "Amber": {
        "primary": ("#F59E0B", "#D97706"),
        "primary_hover": ("#D97706", "#B45309"),
        "soft": ("#FDF2D6", "#2B1F0A"),
    },
    "Slate": {
        "primary": ("#475569", "#334155"),
        "primary_hover": ("#334155", "#1E293B"),
        "soft": ("#E2E8F0", "#1A2230"),
    },
}

# Semantic colors (dual-mode)
COLOR_SUCCESS = ("#059669", "#10B981")
COLOR_SUCCESS_HOVER = ("#047857", "#059669")
COLOR_DANGER = ("#DC2626", "#EF4444")
COLOR_DANGER_HOVER = ("#B91C1C", "#DC2626")
COLOR_WARNING = ("#D97706", "#F59E0B")
COLOR_INFO = ("#0284C7", "#0EA5E9")
COLOR_MUTED = ("#6B7280", "#9CA3AF")
COLOR_SUBTLE_BG = ("#F3F4F6", "#1E1E21")
COLOR_CARD_BG = ("#FFFFFF", "#242428")
COLOR_CARD_BORDER = ("#E5E7EB", "#323238")
COLOR_DIVIDER = ("#E5E7EB", "#2C2C31")

# Status mapping for task badges
STATUS_COLORS = {
    "Queued": COLOR_MUTED,
    "Running": COLOR_INFO,
    "Completed": COLOR_SUCCESS,
    "Failed": COLOR_DANGER,
    "Cancelled": COLOR_WARNING,
}

# Unicode glyphs used as lightweight iconography (not emoji).
# Each sidebar entry gets a geometric prefix so users can scan quickly.
GLYPH = {
    "dashboard": "◆",
    "cleaner": "✕",
    "renamer": "A",
    "scaler": "⬆",
    "organizer": "▣",
    "snapshot": "⟲",
    "recorder": "●",
    "image_studio": "◈",
    "tasks": "⚑",
    "settings": "⚙",
    "plugin": "◌",
    "search": "⌕",
    "arrow": "›",
    "check": "✓",
    "dot": "•",
    "warn": "!",
    "info": "i",
    "close": "✕",
    "add": "+",
    "refresh": "⟳",
    "play": "▶",
    "pause": "❚❚",
    "stop": "■",
    "up": "▲",
    "down": "▼",
    "folder": "▤",
    "file": "▭",
    "clock": "◷",
    "star": "★",
}


@dataclass
class ThemeContext:
    """Resolved theme values for the active accent."""

    accent: str = "Blue"

    @property
    def palette(self) -> Dict[str, Tuple[str, str]]:
        return ACCENT_PALETTES.get(self.accent, ACCENT_PALETTES["Blue"])

    @property
    def primary(self) -> Tuple[str, str]:
        return self.palette["primary"]

    @property
    def primary_hover(self) -> Tuple[str, str]:
        return self.palette["primary_hover"]

    @property
    def soft(self) -> Tuple[str, str]:
        return self.palette["soft"]


def available_accents():
    return list(ACCENT_PALETTES.keys())
