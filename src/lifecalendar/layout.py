"""Grid layout calculator for calendar wallpaper rendering."""

from __future__ import annotations

from typing import Any, Optional, Tuple


class GridLayout:
    """Calculates grid dimensions and positioning."""

    def __init__(
        self,
        mode: str,
        total_units: int,
        canvas_width: int,
        canvas_height: int,
        config: Optional[dict[str, Any]] = None,
    ):
        self.mode = mode
        self.total_units = max(1, total_units)
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height

        self.max_cell_size = 20
        if config and isinstance(config.get("grid_cell_size"), int):
            self.max_cell_size = max(2, min(100, config["grid_cell_size"]))

        self.columns = self._get_columns()
        self.rows = (self.total_units + self.columns - 1) // self.columns

        self._calculate_dimensions()

    def _get_columns(self) -> int:
        """Determine optimal column count per mode, landscape-aware."""
        if self.mode == 'life':
            aspect = self.canvas_width / self.canvas_height if self.canvas_height > 0 else 1
            if aspect >= 1.3:
                return 104
            return 52
        elif self.mode == 'year':
            return 31
        elif self.mode == 'goal':
            if self.total_units <= 365:
                return min(52, self.total_units)
            else:
                return 60
        return 52

    def _calculate_dimensions(self) -> None:
        """Calculate cell size and grid position - landscape-aware."""
        available_width = self.canvas_width * 0.9
        available_height = self.canvas_height * 0.75

        cell_from_width = (available_width - (self.columns - 1) * 2) / self.columns
        cell_from_height = (available_height - (self.rows - 1) * 2) / self.rows

        self.cell_size = int(min(cell_from_width, cell_from_height, self.max_cell_size))
        self.cell_size = max(self.cell_size, 2)
        self.gap = int(max(2, self.cell_size * 0.15))

        self.grid_width = int(self.columns * self.cell_size + (self.columns - 1) * self.gap)
        self.grid_height = int(self.rows * self.cell_size + (self.rows - 1) * self.gap)

        self.start_x = int((self.canvas_width - self.grid_width) / 2)
        self.start_y = int((self.canvas_height - self.grid_height) / 2 + 60)

    def get_cell_position(self, index: int) -> Tuple[float, float]:
        """Get (x, y) position for cell at index."""
        row = index // self.columns
        col = index % self.columns

        x = self.start_x + col * (self.cell_size + self.gap)
        y = self.start_y + row * (self.cell_size + self.gap)

        return x, y
