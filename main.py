import math
import os
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.utils import platform

def rgba_color(r: float, g: float, b: float, a: float = 1.0) -> tuple[float, float, float, float]:
    """Convert 0-255 rgba values into the 0-1 range Kivy expects."""
    return (r / 255.0, g / 255.0, b / 255.0, a)

A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
POINT_LABEL_FONT_SIZE = dp(10)
POINT_LABEL_OUTLINE_WIDTH = dp(0.5)
SELECTED_POINT_COLOR = rgba_color(204, 0, 0)   # vivid magenta stays visible even on bright backgrounds
DEFAULT_POINT_COLOR = rgba_color(0, 0, 0)     # saturated orange that remains visible on white
POINT_TEXT_COLOR = rgba_color(255, 255, 255)     # white digits for maximum readability on dark fills
MM_IN_METER = 1000.0
MOA_IN_RADIANS = math.radians(1 / 60.0)
MOA_MIN_STEP = 0.25
TRAINING_CALIBERS = [
    ".22 LR",
    ".223 Rem",
    "5.45x39",
    "5.56x45 NATO",
    "7.62x39",
    "5.8x42",
    "6.5 Grendel",
    "6.8 SPC",
    "7.92x33 Kurz",
    ".300 AAC Blackout",
    "7.62x40 WT",
    "9x39",
    ".308 Win",
    "7.62x54R",
    ".30-06 Sprg",
    "6.5 Creedmoor",
    "6.5x55 Swedish",
    ".260 Rem",
    ".300 Win-Norma Mag",
    ".338 Lapua Mag",
    ".338 Norma Mag",
    ".375 CheyTac",
    ".408 CheyTac",
    ".50 BMG",
]

CALIBER_RADIUS_MM = {
    ".22 LR": 4,  #2.80
    ".223 Rem": 4,  #2.85
    "5.45x39": 4,  #2.80
    "5.56x45 NATO": 4,  #2.85
    "7.62x39": 3.96,
    "5.8x42": 4, #3.00
    "6.5 Grendel": 4, #3.35
    "6.8 SPC": 4, #3.50
    "7.92x33 Kurz": 4.11,
    ".300 AAC Blackout": 3.90,
    "7.62x40 WT": 3.91,
    "9x39": 4.62,
    ".308 Win": 3.91,
    "7.62x54R": 3.96,
    ".30-06 Sprg": 3.91,
    "6.5 Creedmoor": 4, # 3.35
    "6.5x55 Swedish": 4, # 3.35
    ".260 Rem": 4, # 3.35
    ".300 Win-Norma Mag": 3.92,
    ".338 Lapua Mag": 4.30,
    ".338 Norma Mag": 4.30,
    ".375 CheyTac": 4.76,
    ".408 CheyTac": 5.18,
    ".50 BMG": 6.49,
}

KV_FILE = "main.kv"



if platform in ("win", "linux", "macosx"):
    Window.size = (1080, 2400)  # будь-який тестовий розмір

class PointBoard(Widget):
    """Widget that renders the background image and overlays generated points."""

    image_source = StringProperty("Image.jpg")
    points = ListProperty([])
    selected_point_id = NumericProperty(-1)
    display_all = BooleanProperty(True)
    show_until_selection = BooleanProperty(False)
    controller = ObjectProperty(allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before: # type: ignore
            self._bg_color = Color(1, 1, 1, 1)
            self._background = Rectangle(source=self._resolve_image_path(), pos=self.pos, size=self.size)

        self._point_instructions = []
        self._bound_controller = None
        self._image_ratio = 1.0
        self._draw_area = (self.x, self.y, self.width, self.height)
        self._load_image_meta()

        self.bind( # type: ignore
            pos=self._update_background,
            size=self._update_background,
            image_source=self._update_background,
        )
        self.bind(points=self._refresh_points, selected_point_id=self._refresh_points) # type: ignore
        self.bind(controller=self._on_controller_changed) # type: ignore
        self.bind(image_source=lambda *_: self._load_image_meta()) # type: ignore
        self._update_background()

    def _on_controller_changed(self, *_):
        if self._bound_controller:
            self._bound_controller.unbind(
                points=self._on_controller_points,
                selected_point_id=self._on_controller_selection,
            )
        self._bound_controller = self.controller
        if self.controller:
            self.controller.bind(
                points=self._on_controller_points,
                selected_point_id=self._on_controller_selection,
            )
            self._on_controller_points(self.controller, self.controller.points)
            self._on_controller_selection(self.controller, self.controller.selected_point_id)

    def _on_controller_points(self, _instance, value):
        self.points = value or []

    def _on_controller_selection(self, _instance, value):
        self.selected_point_id = value

    def _resolve_image_path(self) -> str:
        if os.path.exists(self.image_source):
            return self.image_source
        return ""

    def _load_image_meta(self) -> None:
        path = self._resolve_image_path()
        if not path:
            self._image_ratio = 1.0
            return
        try:
            texture = CoreImage(path).texture
            width, height = texture.size # type: ignore
            if width > 0 and height > 0:
                self._image_ratio = width / float(height)
        except Exception:
            self._image_ratio = 1.0

    def _update_background(self, *args) -> None:
        self._background.source = self._resolve_image_path()
        draw_x, draw_y, draw_w, draw_h = self._calculate_draw_area()
        self._draw_area = (draw_x, draw_y, draw_w, draw_h)
        self._background.pos = (draw_x, draw_y)
        self._background.size = (draw_w, draw_h)
        self._refresh_points()

    def _calculate_draw_area(self) -> tuple[float, float, float, float]:
        width = max(self.width, 0)
        height = max(self.height, 0)
        ratio = self._image_ratio or 1.0

        if width == 0 or height == 0:
            return self.x, self.y, width, height

        container_ratio = width / height if height else ratio
        if container_ratio > ratio:
            draw_height = height
            draw_width = draw_height * ratio
        else:
            draw_width = width
            draw_height = draw_width / ratio

        draw_x = self.x + (width - draw_width) / 2.0
        draw_y = self.y + (height - draw_height) / 2.0
        return draw_x, draw_y, draw_width, draw_height

    def _refresh_points(self, *args) -> None:
        if self._point_instructions:
            for instr in self._point_instructions:
                try:
                    self.canvas.after.remove(instr) # type: ignore
                except ValueError:
                    continue
            self._point_instructions.clear()

        if not self.points or self.width == 0 or self.height == 0:
            return

        points_to_draw = self.points if self.display_all else self.points[-1:]
        if self.show_until_selection and self.selected_point_id != -1 and self.points:
            partial = []
            for item in self.points:
                partial.append(item)
                if item.get("id") == self.selected_point_id:
                    break
            points_to_draw = partial

        for point in points_to_draw:
            if not point:
                continue

            px, py = self._mm_to_widget_position(point["x"], point["y"])
            radius_mm = point.get("radius_mm", 3.0)
            radius_px = self._mm_to_pixels(radius_mm)
            is_selected = point.get("id") == self.selected_point_id
            circle_color = SELECTED_POINT_COLOR if is_selected else DEFAULT_POINT_COLOR
            text_color = POINT_TEXT_COLOR

            color_instr = Color(*circle_color)
            ellipse_instr = Ellipse(pos=(px - radius_px, py - radius_px), size=(radius_px * 2, radius_px * 2))

            self.canvas.after.add(color_instr) # type: ignore
            self.canvas.after.add(ellipse_instr) # type: ignore
            self._point_instructions.extend([color_instr, ellipse_instr])

            label_text = str(point.get("id", ""))
            if label_text:
                label = CoreLabel(
                    text=label_text,
                    font_size=POINT_LABEL_FONT_SIZE,
                    bold=True,
                    color=text_color,
                    outline_color=text_color,
                    outline_width=POINT_LABEL_OUTLINE_WIDTH,
                )
                label.refresh()
                texture = label.texture
                if texture:
                    label_instr_color = Color(*text_color)
                    label_instr = Rectangle(
                        texture=texture,
                        size=texture.size,
                        pos=(px - texture.size[0] / 2, py - texture.size[1] / 2),
                    )
                    self.canvas.after.add(label_instr_color) # type: ignore # type: ignore
                    self.canvas.after.add(label_instr) # type: ignore
                    self._point_instructions.extend([label_instr_color, label_instr])

    def _mm_to_widget_position(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        draw_x, draw_y, draw_w, draw_h = self._draw_area
        if draw_w == 0 or draw_h == 0:
            draw_x, draw_y, draw_w, draw_h = self.x, self.y, self.width, self.height

        x_ratio = (x_mm + (A4_WIDTH_MM / 2.0)) / A4_WIDTH_MM
        y_ratio = (y_mm + (A4_HEIGHT_MM / 2.0)) / A4_HEIGHT_MM

        px = draw_x + x_ratio * draw_w
        py = draw_y + y_ratio * draw_h
        return px, py

    def _mm_to_pixels(self, value_mm: float) -> float:
        if value_mm == 0:
            return 0
        draw_w = self._draw_area[2] or self.width
        draw_h = self._draw_area[3] or self.height
        scale_x = draw_w / A4_WIDTH_MM if A4_WIDTH_MM else 0
        scale_y = draw_h / A4_HEIGHT_MM if A4_HEIGHT_MM else 0
        return value_mm * min(scale_x, scale_y)


class PrimaryButton(Button):
    """Button that ignores right/middle clicks and scroll-wheel events."""

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            button_name = getattr(touch, "button", None)
            if button_name and button_name not in ("left",):
                return False
        return super().on_touch_down(touch)


class LimitedSpinnerDropDown(DropDown):
    def __init__(self, **kwargs):
        kwargs.setdefault("max_height", dp(180))
        super().__init__(**kwargs)


class LimitedSpinner(Spinner):
    dropdown_cls = LimitedSpinnerDropDown


class LockableSpinner(LimitedSpinner):
    locked = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.disabled = bool(self.locked)

    def on_locked(self, *_):
        self.disabled = bool(self.locked)
        if self.locked:
            dropdown = getattr(self, "_dropdown", None)
            if dropdown:
                dropdown.dismiss()
            self.is_open = False

    def on_touch_down(self, touch):
        if self.locked:
            return False
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.locked:
            return False
        return super().on_touch_up(touch)


class HistoryButton(RecycleDataViewBehavior, Button):
    point_id = NumericProperty(-1)
    selected = BooleanProperty(False)

    def refresh_view_attrs(self, rv, index, data):
        self.point_id = data.get("point_id", -1)
        self.selected = data.get("selected", False)
        self.text = data.get("text", "")
        return super().refresh_view_attrs(rv, index, data)

    def on_release(self):
        app = App.get_running_app()
        if app and app.root:
            app.root.select_point(self.point_id)


class MainScreen(Screen):
    controller = ObjectProperty(allownone=True, rebind=True)


class HistoryScreen(Screen):
    controller = ObjectProperty(allownone=True, rebind=True)

    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        self._history_rv = self.ids.history_rv
        self._bind_to_controller()

    def on_controller(self, *_):
        self._bind_to_controller()

    def _bind_to_controller(self):
        if not hasattr(self, "_history_rv") or not self.controller or getattr(self, "_controller_bound", False):
            return

        self.controller.bind(
            points=self._update_history,
            selected_point_id=self._update_history,
            selected_distance_m=self._update_history,
        )
        self._controller_bound = True
        Clock.schedule_once(lambda *_: self._update_history(), 0)

    def _update_history(self, *args):
        if not self.controller or not hasattr(self, "_history_rv"):
            return
        self._history_rv.data = self.controller.get_history_entries()


class RootWidget(BoxLayout):
    points = ListProperty([])
    latest_point = ObjectProperty(allownone=True)
    selected_point_id = NumericProperty(-1)
    distance_options = ListProperty([25, 100, 200, 300])
    distance_labels = ListProperty([])
    selected_distance_m = NumericProperty(25)
    selected_distance_label = StringProperty("")
    caliber_options = ListProperty([])
    selected_caliber = StringProperty("")
    controls_locked = BooleanProperty(False)
    calibration_text = StringProperty("—")
    calibration_distance_text = StringProperty("25 м")
    caliber_display_text = StringProperty("—")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._next_point_id = 1
        self._screen_manager = None
        self.distance_labels = [self._format_distance(value) for value in self.distance_options]
        self.selected_distance_label = self._format_distance(self.selected_distance_m)
        self.caliber_options = TRAINING_CALIBERS
        if self.caliber_options:
            self.selected_caliber = self.caliber_options[0]
        self._update_caliber_display()
        self._initialize_lock_state()
        self._refresh_calibration_texts()

    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        self._screen_manager = self.ids.get("screen_manager")
        self._attach_controller_to_screens()

    def _attach_controller_to_screens(self):
        if not self._screen_manager:
            return
        for screen in self._screen_manager.screens:
            if hasattr(screen, "controller"):
                screen.controller = self

    def switch_to(self, screen_name: str) -> None:
        manager = self._screen_manager or self.ids.get("screen_manager")
        if manager and screen_name in manager.screen_names:
            manager.current = screen_name

    def on_points(self, *_):
        self._update_controls_lock_state()
        self._refresh_calibration_texts()

    def on_latest_point(self, *_):
        self._refresh_calibration_texts()

    def generate_point(self) -> None:
        point = {
            "id": self._next_point_id,
            "x": round(random.uniform(-A4_WIDTH_MM / 2.0, A4_WIDTH_MM / 2.0), 1),
            "y": round(random.uniform(-A4_HEIGHT_MM / 2.0, A4_HEIGHT_MM / 2.0), 1),
            "radius_mm": self._current_radius_mm(),
        }
        self._next_point_id += 1

        self.points = self.points + [point]
        self.latest_point = point
        self.selected_point_id = point["id"]
        self._refresh_calibration_texts()
        self._update_controls_lock_state()

    def select_point(self, point_id: int) -> None:
        for item in self.points:
            if item.get("id") == point_id:
                self.selected_point_id = point_id
                self.latest_point = item
                self._refresh_calibration_texts()
                break

    def get_history_entries(self) -> list[dict]:
        entries = []
        for point in reversed(self.points):
            adjustment = self._format_adjustment_text(point, self.selected_distance_m)
            distance_label = f"{self._format_distance(self.selected_distance_m)}"
            label = (
                f"#{point['id']:03d}  {adjustment}  {distance_label}  "
                f"X: {point['x']} мм | Y: {point['y']} мм"
            )
            entries.append(
                {
                    "text": label,
                    "point_id": point["id"],
                    "selected": point["id"] == self.selected_point_id,
                }
            )
        return entries

    def set_distance(self, distance_m: float) -> None:
        if self.controls_locked:
            return
        if distance_m <= 0 or abs(self.selected_distance_m - distance_m) < 0.001:
            return
        self.selected_distance_m = distance_m
        self.selected_distance_label = self._format_distance(distance_m)
        self._refresh_calibration_texts()

    def on_selected_distance_m(self, *_):
        self.selected_distance_label = self._format_distance(self.selected_distance_m)
        self._refresh_calibration_texts()

    def get_calibration_label(self) -> str:
        if not self.latest_point:
            return "—"
        return self._format_adjustment_text(self.latest_point, self.selected_distance_m)

    def get_calibration_distance_label(self) -> str:
        if not self.latest_point:
            return f"{self._format_distance(self.selected_distance_m)}"
        return f"{self._format_distance(self.selected_distance_m)}"

    def get_calibration_axis_label(self, axis: str) -> str:
        if not self.latest_point:
            axis_name = axis.upper() if axis else "X"
            return f"{axis_name}: —"
        if axis.lower() == "x":
            direction, value = self._format_axis_adjustment(
                self.latest_point.get("x", 0.0),
                self.selected_distance_m,
                "R",
                "L",
            )
            return f"X: {direction} {value}"
        if axis.lower() == "y":
            direction, value = self._format_axis_adjustment(
                self.latest_point.get("y", 0.0),
                self.selected_distance_m,
                "U",
                "D",
            )
            return f"Y: {direction} {value}"
        return ""

    def handle_distance_selection(self, display_label: str) -> None:
        if not display_label or self.controls_locked:
            return
        for value, label in zip(self.distance_options, self.distance_labels):
            if label == display_label:
                self.set_distance(float(value))
                return

    def set_caliber(self, caliber: str) -> None:
        if self.controls_locked:
            return
        if caliber and caliber in self.caliber_options:
            self.selected_caliber = caliber
            self._update_caliber_display()

    def finish_session(self) -> None:
        self.points = []
        self.latest_point = None
        self.selected_point_id = -1
        self._next_point_id = 1
        self.controls_locked = False
        self._refresh_calibration_texts()

    def _format_distance(self, distance_m: float) -> str:
        value = float(distance_m)
        return f"{int(value)} м" if value.is_integer() else f"{value:.1f} м"

    def _format_adjustment_text(self, point: dict, distance_m: float) -> str:
        if not point:
            return "—"
        vertical = self._mm_to_moa(point.get("y", 0.0), distance_m)
        horizontal = self._mm_to_moa(point.get("x", 0.0), distance_m)
        vert_dir = "U" if vertical >= 0 else "D"
        horiz_dir = "R" if horizontal >= 0 else "L"
        v_value = self._format_moa_value(vertical)
        h_value = self._format_moa_value(horizontal)
        return f"{vert_dir} {v_value}     {horiz_dir} {h_value}"

    def _mm_to_moa(self, mm_value: float, distance_m: float) -> float:
        mm_per_moa = math.tan(MOA_IN_RADIANS) * distance_m * MM_IN_METER
        if mm_per_moa == 0:
            return 0.0
        return mm_value / mm_per_moa

    def _format_moa_value(self, value: float) -> str:
        magnitude = abs(value)
        if magnitude < 1e-6:
            return "0"
        step_count = math.ceil(magnitude / MOA_MIN_STEP)
        quantized = step_count * MOA_MIN_STEP
        text = f"{quantized:.2f}".rstrip("0").rstrip(".")
        return text or "0"

    def _current_radius_mm(self) -> float:
        return CALIBER_RADIUS_MM.get(self.selected_caliber, 3.0)

    def _initialize_lock_state(self) -> None:
        self.controls_locked = len(self.points) >= 1

    def _update_controls_lock_state(self) -> None:
        should_lock = len(self.points) >= 1
        if getattr(self, "controls_locked", False) != should_lock:
            self.controls_locked = should_lock
        self._refresh_calibration_texts()

    def _format_axis_adjustment(
        self,
        value_mm: float,
        distance_m: float,
        positive_label: str,
        negative_label: str,
    ) -> tuple[str, str]:
        moa_value = self._mm_to_moa(value_mm, distance_m)
        direction = positive_label if moa_value >= 0 else negative_label
        formatted = self._format_moa_value(moa_value)
        return direction, formatted

    def _refresh_calibration_texts(self) -> None:
        distance_label = f"{self._format_distance(self.selected_distance_m)}"
        self.calibration_distance_text = distance_label
        if not self.latest_point:
            self.calibration_text = "—"
            return

        self.calibration_text = self._format_adjustment_text(self.latest_point, self.selected_distance_m)

    def _update_caliber_display(self) -> None:
        self.caliber_display_text = self.selected_caliber or "—"


class CoordinateApp(App):
    def build(self):
        self.title = "Координати A4"
        return Builder.load_file(KV_FILE)


if __name__ == "__main__":
    CoordinateApp().run()
