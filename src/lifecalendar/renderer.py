"""Wallpaper image renderer using Pillow."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from typing import Any, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .layout import GridLayout

logger = logging.getLogger("WallpaperEngine")

MAX_GRID_UNITS = 50_000
MAX_SAFE_PIXELS = 7680 * 4320


class WallpaperRenderer:
    """Handles all drawing operations."""

    FONT_PATHS = {
        'Windows': [
            r'C:\Windows\Fonts\arial.ttf',
            r'C:\Windows\Fonts\SegoeUI.ttf',
            r'C:\Windows\Fonts\segoeui.ttf',
            r'C:\Windows\Fonts\tahoma.ttf',
        ],
        'Linux': [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/TTF/DejaVuSans.ttf',
            '/usr/local/share/fonts/DejaVuSans.ttf',
            '~/.fonts/DejaVuSans.ttf',
        ],
        'Darwin': [
            '/System/Library/Fonts/Helvetica.ttc',
            '/System/Library/Fonts/Supplemental/Arial.ttf',
            '/Library/Fonts/Arial.ttf',
            '~/Library/Fonts/Arial.ttf',
        ]
    }

    _font_cache: dict[str, dict[str, Any]] = {}

    def __init__(self, width: int, height: int, config: Optional[dict[str, Any]] = None):
        self.width = width
        self.height = height
        self.config = config or {}

        if width * height > MAX_SAFE_PIXELS:
            logger.warning(
                "Large canvas requested (%sx%s = %s px) exceeds guard threshold %s px; proceeding.",
                width, height, width * height, MAX_SAFE_PIXELS,
            )

        self.img = Image.new('RGB', (width, height), color='#050505')
        self.draw = ImageDraw.Draw(self.img)

        palette = self.config.get("palette", {})
        self.title_color = palette.get("title", "#f2f2f2")
        self.stats_color = palette.get("stats", "#9a9a9a")
        self.subtitle_color = palette.get("subtitle", "#8a8a8a")
        self.legend_color = palette.get("legend", "#d6d6d6")
        self.passed_color = palette.get("lived", "#cfcfcf")
        self.current_color = palette.get("current", "#ffffff")
        self.future_color = palette.get("future", "#3a3a3a")
        self.highlight_color = palette.get("current_progress", "#ffdd00")

        self._load_fonts()

    def _load_fonts(self) -> None:
        """Load fonts with proper OS detection and robust fall-backs (uses cache)."""
        if sys.platform == "win32":
            system = "Windows"
        elif sys.platform == "darwin":
            system = "Darwin"
        else:
            system = "Linux"

        def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
            if font_path.lower().endswith(".ttc"):
                return ImageFont.truetype(font_path, size, index=0)
            return ImageFont.truetype(font_path, size)

        cache_key = f"{system}_fonts"
        if cache_key in WallpaperRenderer._font_cache:
            fonts = WallpaperRenderer._font_cache[cache_key]
            self.title_font = fonts['title']
            self.headline_font = fonts['headline']
            self.stats_font = fonts['stats']
            self.subtitle_font = fonts['subtitle']
            self.legend_font = fonts['legend']
            return

        font_paths = self.FONT_PATHS.get(system, self.FONT_PATHS['Linux'])

        loaded = False
        for font_path in font_paths:
            try:
                expanded_path = os.path.expanduser(font_path)
                if os.path.exists(expanded_path):
                    title_font = _load_font(expanded_path, 40)
                    headline_font = _load_font(expanded_path, 26)
                    stats_font = _load_font(expanded_path, 18)
                    subtitle_font = _load_font(expanded_path, 16)
                    legend_font = _load_font(expanded_path, 16)

                    WallpaperRenderer._font_cache[cache_key] = {
                        'title': title_font,
                        'headline': headline_font,
                        'stats': stats_font,
                        'subtitle': subtitle_font,
                        'legend': legend_font
                    }

                    self.title_font = title_font
                    self.headline_font = headline_font
                    self.stats_font = stats_font
                    self.subtitle_font = subtitle_font
                    self.legend_font = legend_font

                    loaded = True
                    logger.info(f"Loaded fonts from {expanded_path}")
                    break
            except (IOError, OSError) as e:
                logger.debug(f"Could not load font {expanded_path}: {e}")
                continue

        if not loaded:
            logger.warning("Custom fonts not available – falling back to Pillow's default")
            default_font = ImageFont.load_default()
            self.title_font = default_font
            self.headline_font = default_font
            self.stats_font = default_font
            self.subtitle_font = default_font
            self.legend_font = default_font

    def draw_title(self, text: str, y_position: float) -> None:
        """Draw centered title."""
        bbox = self.draw.textbbox((0, 0), text, font=self.title_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill=self.title_color, font=self.title_font)

    def draw_stats(self, text: str, y_position: float) -> None:
        """Draw centered stats text."""
        bbox = self.draw.textbbox((0, 0), text, font=self.stats_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill=self.stats_color, font=self.stats_font)

    def draw_subtitle(self, text: str, y_position: float) -> None:
        """Draw centered subtitle text."""
        bbox = self.draw.textbbox((0, 0), text, font=self.subtitle_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill=self.subtitle_color, font=self.subtitle_font)

    def draw_headline_stat(self, text: str, y_position: float) -> None:
        """Draw the primary stat line with stronger emphasis."""
        bbox = self.draw.textbbox((0, 0), text, font=self.headline_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill=self.title_color, font=self.headline_font)

    def draw_grid(
        self,
        layout: GridLayout,
        total_units: int,
        filled_units: int,
        current_progress: Optional[float] = None,
    ) -> None:
        """Draw the calendar grid using colors from config palette."""
        if total_units > MAX_GRID_UNITS:
            logger.warning(
                "Skipping grid render because total_units=%s exceeds MAX_GRID_UNITS=%s",
                total_units, MAX_GRID_UNITS,
            )
            return

        for i in range(total_units):
            x, y = layout.get_cell_position(i)

            if i < filled_units:
                color = self.passed_color
            elif filled_units < total_units and i == filled_units:
                color = self.current_color
            else:
                color = self.future_color

            self.draw.rectangle(
                [x, y, x + layout.cell_size, y + layout.cell_size],
                fill=color
            )

            if filled_units < total_units and i == filled_units:
                self.draw.rectangle(
                    [x, y, x + layout.cell_size, y + layout.cell_size],
                    outline=self.highlight_color,
                    width=2,
                )
                if current_progress is not None:
                    progress_width = max(2, int(layout.cell_size * max(0.0, min(1.0, current_progress))))
                    bar_top = y + layout.cell_size - max(3, layout.cell_size // 4)
                    self.draw.rectangle(
                        [x + 1, bar_top, x + progress_width, y + layout.cell_size],
                        fill=self.highlight_color,
                    )

    def draw_legend(self, legend_items: List[Tuple[str, str]], y_position: float) -> None:
        """Draw legend."""
        item_width = 140
        total_width = len(legend_items) * item_width
        start_x = (self.width - total_width) / 2

        for idx, (color, label) in enumerate(legend_items):
            x = start_x + idx * item_width
            self.draw.rectangle([x, y_position, x + 15, y_position + 15], fill=color)
            self.draw.text((x + 25, y_position), label, fill=self.legend_color, font=self.legend_font)

    def save(self, path: str) -> None:
        """Save the image with atomic write to prevent corruption."""
        temp_path = path + ".tmp"
        try:
            self.img.save(temp_path, 'PNG', optimize=True)
            try:
                os.replace(temp_path, path)
            except OSError as exc:
                logger.debug(f"os.replace failed ({exc}); falling back to shutil.move")
                shutil.move(temp_path, path)

            if not os.path.exists(path):
                raise RuntimeError("Wallpaper file not created")
        except Exception:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass
            raise
