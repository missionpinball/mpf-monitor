import logging

# For drag and drop vs click separation
import time
import math
import ast
import re

# will change these to specific imports once code is more final
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

from enum import Enum

from mpfmonitor.core.devices import DeviceNode


class Shape(Enum):
    DEFAULT = 0
    SQUARE = 1
    RECTANGLE = 2
    CIRCLE = 3
    TRIANGLE = 4
    ARROW = 5
    FLIPPER = 6
    PENTAGON = 7
    HEXAGON = 8
    OCTAGON = 9
    STAR = 10
    CUSTOM = 11


class PfPixmapItem(QGraphicsPixmapItem):

    def __init__(self, image, mpfmon, parent=None):
        super().__init__(image, parent)

        self.mpfmon = mpfmon
        self.setAcceptDrops(True)
        self._height = None
        self._width = None

    def invalidate_size(self):
        self._height = None
        self._width = None

    @property
    def height(self):
        """Return the height of the scene."""
        if self._height is None:
            self._height = self.mpfmon.scene.height()
        return self._height

    @property
    def width(self):
        """Return the width of the scene."""
        if self._width is None:
            self._width = self.mpfmon.scene.width()
        return self._width

    def create_widget_from_config(self, widget, device_type, device_name):
        try:
            config = self.mpfmon.config[device_type][device_name]
            x = config['x']
            y = config['y']
            default_size = self.mpfmon.pf_device_size
            default_alpha = self.mpfmon.pf_device_alpha
            default_outline = self.mpfmon.pf_device_outline

            alpha = config.get('alpha', default_alpha)
            shape_str = config.get('shape', 'DEFAULT')
            custom_shape_points = None
            if shape_str == 'CUSTOM':
                custom_shape_points = config['custom_shape_points']
            shape = Shape[shape_str]
            rotation = config.get('rotation', 0)
            size = config.get('size', default_size)

        except KeyError:
            return

        x *= self.width
        y *= self.height

        self.create_pf_widget(widget, device_type, device_name, x, y,
                              size=size, alpha=alpha, rotation=rotation,
                              shape=shape, save=False, outline=default_outline, custom_shape_points=custom_shape_points)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):
        device = event.source().selectedIndexes()[0]
        device_name = device.data()
        device_type = device.parent().data()

        drop_x = event.scenePos().x()
        drop_y = event.scenePos().y()

        try:
            widget = self.mpfmon.device_window.device_states[device_type][device_name]
            self.create_pf_widget(widget, device_type, device_name, drop_x,
                                  drop_y)
        except KeyError:
            self.mpfmon.log.warn("Invalid device dragged.")

    def create_pf_widget(self, widget, device_type, device_name, drop_x,
                         drop_y, size=None, alpha=255, rotation=0,
                         outline=3, shape=Shape.DEFAULT, save=True, custom_shape_points=None):
        w = PfWidget(self.mpfmon, widget, device_type, device_name, drop_x,
                     drop_y, size=size, alpha=alpha, rotation=rotation,
                     outline=outline, shape_type=shape, save=save, custom_shape_points=custom_shape_points)

        self.mpfmon.scene.addItem(w)


class PfWidget(QGraphicsItem):

    def __init__(self, mpfmon, widget, device_type, device_name, x, y,
                 size=None, alpha=255, rotation=0, outline=3,
                 shape_type=Shape.DEFAULT, save=True, custom_shape_points=None):
        super().__init__()

        self.widget = widget    # type: DeviceNode
        self.mpfmon = mpfmon
        self.name = device_name
        self.move_in_progress = True
        self.device_type = device_type
        self.set_size(size=size)
        self.shape_type = shape_type
        self.angle = rotation
        self.alpha = alpha
        self.outline = outline
        self.custom_shape_points = custom_shape_points

        self.setToolTip('{}: {}'.format(self.device_type, self.name))
        self.setAcceptHoverEvents(True)

        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setPos(x, y)
        self.update_pos(save)
        self.click_start = 0
        self.release_switch = False

        self.log = logging.getLogger('Core')

        old_widget_exists = widget.set_change_callback(self.notify)

        if old_widget_exists:
            self.log.debug("Previous widget exists.")
            old_widget_exists(destroy=True)

    def boundingRect(self):
        rotated_shape_points = self.rotated_shape_points()
        scale = self.device_size
        if rotated_shape_points != None:
            x_min = min(point[0] for point in rotated_shape_points) * scale
            x_max = max(point[0] for point in rotated_shape_points) * scale
            y_min = min(point[1] for point in rotated_shape_points) * scale
            y_max = max(point[1] for point in rotated_shape_points) * scale
            width = (x_max - x_min)
            height = (y_max - y_min)
            return QRectF(int(x_min), int(y_min), int(width), int(height))

        else:
            return QRectF(int(scale / -2), int(scale / -2), int(scale), int(scale))

    def set_shape_type(self, shape_type):
        if isinstance(shape_type, Shape):
            self.shape_type = shape_type
        else:
            self.shape_type = Shape.DEFAULT

    def set_rotation(self, angle=0):
        angle = angle % 360
        self.angle = angle

    def set_size(self, size=None):
        if size is None:
            self.size = self.mpfmon.pf_device_size
            self.device_size = self.mpfmon.scene.width() * \
                               self.mpfmon.pf_device_size
        else:
            self.size = size
            self.device_size = self.mpfmon.scene.width() * size

    def resize_to_default(self, force=False):
        device_config = self.mpfmon.config[self.device_type].get(self.name, None)

        if force:
            device_config.pop('size', None) # Delete saved size info, None is incase key doesn't exist (popped twice)

        device_size = device_config.get('size', None)

        if device_size is not None:
            # Do not change the size if it's already set
            pass
        elif device_config is not None:
            self.set_size()

        self.update_pos(save=False)  # Do not save at this point. Let it be saved elsewhere. This reduces writes.


    def pass_name_filter(self):
        filter_text = self.mpfmon.device_name_filter.strip()
        if filter_text:
            ignore_case = not any(char.isupper() for char in filter_text)

            if filter_text.startswith('/'):
                regex_pattern = filter_text.removeprefix('/').removesuffix('/')

                try:
                    if not re.search(regex_pattern, self.name, re.IGNORECASE if ignore_case else 0):
                        return False
                except (re.error, re.PatternError):
                    return True
            else:
                name = self.name.lower() if ignore_case else self.name

                if filter_text.startswith('^'):
                    prefix_filter = filter_text[1:]
                    if not name.startswith(prefix_filter):
                        return False
                else:
                    if filter_text not in name:
                        return False
        return True


    def allowed_by_filters(self):
        if self.mpfmon.device_name_filter:
            if not self.pass_name_filter():
                return False

        if self.device_type == 'light' and self.mpfmon.hide_layer_lights:
            return False

        if self.device_type == 'switch' and self.mpfmon.hide_layer_switches:
            return False

        if self.device_type != 'light' and self.device_type != 'switch' and self.mpfmon.hide_layer_others:
            return False

        return True

    def draw_shape(self):
        if not self.allowed_by_filters():
            return None

        shape_result = self.shape_type

        # Preserve legacy and regular use
        if shape_result == Shape.DEFAULT:
            if self.device_type == 'light':
                shape_result = Shape.CIRCLE

            elif self.device_type == 'switch':
                shape_result = Shape.SQUARE

            elif self.device_type == 'diverter':
                shape_result = Shape.TRIANGLE

            elif self.device_type in ['timer', 'spinner', 'ball_save', 'multiball']:
                shape_result = Shape.HEXAGON

            elif self.device_type in ['achievement', 'achievement_group']:
                shape_result = Shape.STAR

            elif self.device_type in ['timed_switch', 'combo_switch', 'magnet']:
                shape_result = Shape.OCTAGON

            elif self.device_type in ['drop_target', 'drop_target_bank', 'kickback']:
                shape_result = Shape.ARROW

            elif self.device_type in ['shot', 'shot_group']:
                shape_result = Shape.PENTAGON

            elif self.device_type in ['state_machine', 'counter', 'accrual']:
                shape_result = Shape.RECTANGLE

            else:  # Draw any other devices as square by default
                shape_result = Shape.SQUARE

        return shape_result

    def shape(self):
        rotated = self.rotated_shape_points()
        path = QPainterPath()
        size = self.device_size
        if rotated is None:
            half_size = int(size / 2)
            path.addEllipse(QRectF(-half_size, -half_size, size, size))
        else:
            path.addPolygon(QPolygonF([QPointF(x * size, y * size) for x, y in rotated]))

        return path

    def paint(self, painter, option, widget=None):
        """Paint this widget to the playfield."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(self.widget.get_colored_pen(self.outline))
        painter.setBrush(self.widget.get_colored_brush(self.alpha))

        draw_shape = self.draw_shape()
        if draw_shape == None:  # TODO or do we want an enum none member?
            return
        elif draw_shape == Shape.CIRCLE:
            painter.drawEllipse(int(self.device_size / -2), int(self.device_size / -2),
                                int(self.device_size), int(self.device_size))
        else:
            shape_points = self.rotated_shape_points()
            if shape_points is not None:
                scaled_points = map(lambda pair: QPoint(int(pair[0] * self.device_size), int(pair[1] * self.device_size)), shape_points)
                painter.drawPolygon(QPolygon(scaled_points))

    def rotated_shape_points(self):
        points = self.points_for_draw_shape()
        if points is None:
            return None
        theta = math.radians(self.angle)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        return [((x * cos_t - y * sin_t), (x * sin_t + y * cos_t)) for x, y in points]

    def points_for_draw_shape(self):
        draw_shape = self.draw_shape()
        if draw_shape == Shape.CIRCLE:
            return None # Handle circles with drawEllipse instead

        elif draw_shape == Shape.CUSTOM:
            return self.custom_points()

        elif draw_shape == Shape.SQUARE:
            return self.square_points()

        elif draw_shape == Shape.RECTANGLE:
            return self.rectangle_points()

        elif draw_shape == Shape.TRIANGLE:
            return self.wide_triangle_points()

        elif draw_shape == Shape.ARROW:
            return self.arrow_points()

        elif draw_shape == Shape.FLIPPER:
            return self.tall_triangle_points()

        elif draw_shape == Shape.PENTAGON:
            return self.pentagon_points()

        elif draw_shape == Shape.HEXAGON:
            return self.hexagon_points()

        elif draw_shape == Shape.OCTAGON:
            return self.octagon_points()

        elif draw_shape == Shape.STAR:
            return self.star_points()

        else:  # Square fallback
            return self.square_points()

    def square_points(self):
        return [[-.5, -.5], [.5, -.5], [.5, .5], [-.5, .5]]

    def pentagon_points(self):
        return [[0, .5], [-.48, .15], [-.29, -.4], [.29, -.4], [.48, .15]]

    def hexagon_points(self):
        return [[.5, 0], [.25, .43], [-.25, .43], [-.5, 0], [-.25, -.43], [.25, -.43]]

    def octagon_points(self):
        return [[.5, 0], [.35, .35], [0, .5], [-.35, .35], [-.5, 0], [-.35, -.35], [0, -.5], [.35, -.35]]

    def rectangle_points(self):
        return [[-.2, -.5], [.2, -.5], [.2, .5], [-.2, .5]]

    def wide_triangle_points(self):
        return [[0, -.6], [-.6, .3], [.6, .3]]

    def arrow_points(self):
        return [[0, -.7], [-.4, 0], [-.2, 0], [-.2, .4], [.2, .4], [.2, 0], [.4, 0]]

    def tall_triangle_points(self):
        return [[0, -.3], [-.3, .7], [.3, .7]]

    def star_points(self):
        return [[0, -.5], [-.11, -.15], [-.48, -.15], [-.18, .06], [-.29, .4], [0, .19], [.29, .4], [.18, .06], [.48, -.15], [.11, -.15]]

    def custom_points(self):
        '''Loads a custom vertex array from config, or falls back to an X if config is invalid or missing.'''
        if self.custom_shape_points:
            return self.custom_shape_points
        else:  # fallback X
            return [[.36, .36], [0, .19], [-.36, .36], [-.19, 0], [-.36, -.36], [0, -.19], [.36, -.36], [.19, 0]]

    def notify(self, destroy=False, resize=False):
        self.update()

        if destroy:
            self.destroy()

    def destroy(self):
        self.log.debug("Destroy device: %s", self.name)
        self.mpfmon.scene.removeItem(self)
        self.delete_from_config()

    def mouseMoveEvent(self, event):
        if (self.mpfmon.pf.boundingRect().width() > event.scenePos().x() >
                0) and (self.mpfmon.pf.boundingRect().height() >
                event.scenePos().y() > 0):
            # devices off the pf do weird things at the moment

            if time.time() - self.click_start > .3:
                self.setPos(event.scenePos())
                self.move_in_progress = True

    def mousePressEvent(self, event):
        self.click_start = time.time()

        if self.device_type == 'switch':
            if event.buttons() & Qt.MouseButton.RightButton:
                if not self.get_val_inspector_enabled():
                    self.mpfmon.bcp.send('switch', name=self.name, state=-1)
                    self.release_switch = False
                else:
                    self.send_to_inspector_window()
                    self.log.debug('Switch %s right clicked', self.name)
            elif event.buttons() & Qt.MouseButton.LeftButton:
                if not self.get_val_inspector_enabled():
                    self.mpfmon.bcp.send('switch', name=self.name, state=-1)
                    self.release_switch = True
                else:
                    self.send_to_inspector_window()
                    self.log.debug('Switch %s clicked', self.name)

        else:
            if event.buttons() & Qt.MouseButton.RightButton:
                if self.get_val_inspector_enabled():
                    self.send_to_inspector_window()
                    self.log.debug('%s %s right clicked', self.device_type, self.name)
            elif event.buttons() & Qt.MouseButton.LeftButton:
                if self.get_val_inspector_enabled():
                    self.send_to_inspector_window()
                    self.log.debug('%s %s clicked', self.device_type, self.name)

    def mouseReleaseEvent(self, event):
        if self.move_in_progress and time.time() - self.click_start > .5:
            self.move_in_progress = False
            self.update_pos()

        elif self.release_switch:
            self.mpfmon.bcp.send('switch', name=self.name, state=-1)

        self.click_start = 0

    def update_pos(self, save=True):
        x = self.pos().x() / self.mpfmon.scene.width() if self.mpfmon.scene.width() > 0 else self.pos().x()
        y = self.pos().y() / self.mpfmon.scene.height() if self.mpfmon.scene.height() > 0 else self.pos().y()

        if self.device_type not in self.mpfmon.config:
            self.mpfmon.config[self.device_type] = dict()

        if self.name not in self.mpfmon.config[self.device_type]:
            self.mpfmon.config[self.device_type][self.name] = dict()

        self.mpfmon.config[self.device_type][self.name]['x'] = x
        self.mpfmon.config[self.device_type][self.name]['y'] = y

        # Only save the shape if it is different than the  default
        conf_shape_str = self.mpfmon.config[self.device_type][self.name].get('shape', 'DEFAULT')
        conf_shape = Shape[str(conf_shape_str).upper()]

        if self.shape_type is not conf_shape:
            if self.shape_type is not Shape.DEFAULT:
                self.mpfmon.config[self.device_type][self.name]['shape'] = self.shape_type.name
            else:
                try:
                    self.mpfmon.config[self.device_type][self.name].pop('shape')
                except:
                    pass

        # Only save the rotation if it has been changed
        conf_angle = self.mpfmon.config[self.device_type][self.name].get('rotation', -1)

        if self.angle is not conf_angle:
            if self.angle != 0:
                self.mpfmon.config[self.device_type][self.name]['rotation'] = self.angle
            else:
                try:
                    self.mpfmon.config[self.device_type][self.name].pop('rotation')
                except:
                    pass

        # Only save the size if it is different than the top level default
        default_size = self.mpfmon.pf_device_size
        conf_size = self.mpfmon.config[self.device_type][self.name].get('size', default_size)

        if self.size is not conf_size and self.size is not self.mpfmon.pf_device_size:
            self.mpfmon.config[self.device_type][self.name]['size'] = self.size

        if save:
            self.mpfmon.save_config()

    def delete_from_config(self):
        self.mpfmon.config[self.device_type].pop(self.name)
        self.mpfmon.save_config()

    def get_val_inspector_enabled(self):
        return self.mpfmon.inspector_enabled

    def send_to_inspector_window(self):
        self.mpfmon.inspector_window_last_selected_cb(pf_widget=self)

    def hoverEnterEvent(self, event):
        tooltip_text = f"{self.device_type}: {self.name}"
        node_data = self.widget.data()

        if self.device_type == 'switch':
            sw_num = node_data.get('number', None)
            if sw_num is not None:
                tooltip_text += f" @ {sw_num}"

        elif self.device_type in ('accrual', 'counter'):
            val = node_data.get('value', None)
            if val is not None:
                tooltip_text += f" - {val}"

        elif self.device_type in ('achievement', 'state_machine'):
            state = node_data.get('state', None)
            if state is not None:
                tooltip_text += f" - {state}"

        elif self.device_type == 'shot':
            state_name = node_data.get('state_name', None)
            state_idx = node_data.get('state', None)
            tooltip_text += f" - {state_name} ({state_idx})"

        elif self.device_type == 'shot_group':
            common_state = node_data.get('common_state', None)
            tooltip_text += f" | Common: {common_state}"

        elif self.device_type == 'servo':
            pos = node_data.get('position', None)
            tooltip_text += f" | position: {pos}"

        elif self.device_type == 'playfield':
            balls = node_data.get('balls', 0)
            avail = node_data.get('available_balls', 0)
            req = node_data.get('balls_requested', 0)
            tooltip_text += f" | balls: {balls} (available: {avail}, requested: {req})"

        elif self.device_type == 'ball_device':
            balls = node_data.get('balls', 0)
            avail = node_data.get('available_balls', 0)
            tooltip_text += f" | balls: {balls} (available: {avail})"

        elif self.device_type == 'ball_hold':
            held = node_data.get('balls_held', 0)
            tooltip_text += f" | held: {held}"

        elif self.device_type == 'ball_save':
            remaining = node_data.get('saves_remaining', 0)
            tooltip_text += f" - Saves remaining: {remaining}"

        elif self.device_type == 'drop_target':
            complete = node_data.get('complete', None)
            tooltip_text += f" - Complete: {complete}"

        elif self.device_type == 'drop_target_bank':
            down = node_data.get('down', 0)
            up = node_data.get('up', 0)
            state = node_data.get('state', None)
            tooltip_text += f" - State: {state} | Up: {up}, Down: {down}"

        self.setToolTip(tooltip_text)
        super().hoverEnterEvent(event)
