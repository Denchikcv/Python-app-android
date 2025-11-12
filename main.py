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
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.utils import platform

def rgba_color(r: float, g: float, b: float, a: float = 1.0) -> tuple[float, float, float, float]:
    """Convert 0-255 rgba values into the 0-1 range Kivy expects."""
    return (r / 255.0, g / 255.0, b / 255.0, a)

A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
POINT_DIAMETER_MM = 8  # 5.56
POINT_RADIUS_MM = POINT_DIAMETER_MM / 2.0
POINT_LABEL_FONT_SIZE = dp(11)
POINT_LABEL_OUTLINE_WIDTH = dp(0.8)
SELECTED_POINT_COLOR = rgba_color(204, 0, 0)   # vivid magenta stays visible even on bright backgrounds
DEFAULT_POINT_COLOR = rgba_color(0, 0, 0)     # saturated orange that remains visible on white
POINT_TEXT_COLOR = rgba_color(255, 255, 255)     # white digits for maximum readability on dark fills
KV_FILE = "main.kv"



if platform in ("win", "linux", "macosx"):
    Window.size = (600, 1000)  # будь-який тестовий розмір

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
            radius_px = self._mm_to_pixels(point.get("radius_mm", POINT_RADIUS_MM))
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
    controller = ObjectProperty(allownone=True)


class HistoryScreen(Screen):
    controller = ObjectProperty(allownone=True)

    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        self._history_rv = self.ids.history_rv
        self._bind_to_controller()

    def on_controller(self, *_):
        self._bind_to_controller()

    def _bind_to_controller(self):
        if not hasattr(self, "_history_rv") or not self.controller or getattr(self, "_controller_bound", False):
            return

        self.controller.bind(points=self._update_history, selected_point_id=self._update_history)
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._next_point_id = 1
        self._screen_manager = None

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

    def generate_point(self) -> None:
        point = {
            "id": self._next_point_id,
            "x": round(random.uniform(-A4_WIDTH_MM / 2.0, A4_WIDTH_MM / 2.0), 1),
            "y": round(random.uniform(-A4_HEIGHT_MM / 2.0, A4_HEIGHT_MM / 2.0), 1),
            "radius_mm": POINT_RADIUS_MM,
        }
        self._next_point_id += 1

        self.points = self.points + [point]
        self.latest_point = point
        self.selected_point_id = point["id"]

    def select_point(self, point_id: int) -> None:
        for item in self.points:
            if item.get("id") == point_id:
                self.selected_point_id = point_id
                break

    def get_history_entries(self) -> list[dict]:
        entries = []
        for point in reversed(self.points):
            label = f"#{point['id']:03d}   X: {point['x']} мм | Y: {point['y']} мм"
            entries.append(
                {
                    "text": label,
                    "point_id": point["id"],
                    "selected": point["id"] == self.selected_point_id,
                }
            )
        return entries


class CoordinateApp(App):
    def build(self):
        self.title = "Координати A4"
        return Builder.load_file(KV_FILE)


if __name__ == "__main__":
    CoordinateApp().run()
