import logging

# For drag and drop vs click separation
import time

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


class PfView(QGraphicsView):

    def __init__(self, parent, mpfmon):
        self.mpfmon = mpfmon
        super().__init__(parent)

        self.setWindowTitle("Playfield")
        self.set_inspector_mode_title(inspect=False)

    def resizeEvent(self, event=None):
        self.fitInView(self.mpfmon.pf, Qt.AspectRatioMode.KeepAspectRatio)

    def set_inspector_mode_title(self, inspect=False):
        if inspect:
            self.setWindowTitle('Inspector Enabled - Playfield')
        else:
            self.setWindowTitle("Playfield")

    def closeEvent(self, event):
        self.mpfmon.write_local_settings()
        event.accept()
        self.mpfmon.check_if_quit()


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
            x = self.mpfmon.config[device_type][device_name]['x']
            y = self.mpfmon.config[device_type][device_name]['y']
            default_size = self.mpfmon.pf_device_size
            shape_str = self.mpfmon.config[device_type][device_name].get('shape', 'DEFAULT')
            shape = Shape[shape_str]
            rotation = self.mpfmon.config[device_type][device_name].get('rotation', 0)
            size = self.mpfmon.config[device_type][device_name].get('size', default_size)

        except KeyError:
            return

        x *= self.width
        y *= self.height

        self.create_pf_widget(widget, device_type, device_name, x, y,
                              size=size, rotation=rotation, shape=shape, save=False)

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
                         drop_y, size=None, rotation=0, shape=Shape.DEFAULT, save=True):
        w = PfWidget(self.mpfmon, widget, device_type, device_name, drop_x,
                     drop_y, size=size, rotation=rotation, shape_type=shape, save=save)

        self.mpfmon.scene.addItem(w)


class PfWidget(QGraphicsItem):

    def __init__(self, mpfmon, widget, device_type, device_name, x, y,
                 size=None, rotation=0, shape_type=Shape.DEFAULT, save=True):
        super().__init__()

        self.widget = widget    # type: DeviceNode
        self.mpfmon = mpfmon
        self.name = device_name
        self.move_in_progress = True
        self.device_type = device_type
        self.set_size(size=size)
        self.shape_type = shape_type
        self.angle = rotation

        self.setToolTip('{}: {}'.format(self.device_type, self.name))
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setPos(x, y)
        self.update_pos(save)
        self.click_start = 0
        self.release_switch = False
        self.pen = QPen(Qt.GlobalColor.white, 3, Qt.PenStyle.SolidLine)

        self.log = logging.getLogger('Core')

        old_widget_exists = widget.set_change_callback(self.notify)

        if old_widget_exists:
            self.log.debug("Previous widget exists.")
            old_widget_exists(destroy=True)


    def boundingRect(self):
        known_points = self.points_for_draw_shape()
        if known_points != None:
            x_options = [sub_list[0] for sub_list in known_points]
            x_min = min(x_options)
            width = max(x_options) - x_min
            y_options = [sub_list[1] for sub_list in known_points]
            y_min = min(y_options)
            height = max(y_options) - y_min
            return QRectF(int(x_min * self.device_size), int(y_min * self.device_size), int(width * self.device_size), int(height * self.device_size))

        else:
            return QRectF(int(self.device_size / -2), int(self.device_size / -2),
                          int(self.device_size), int(self.device_size))

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

    def draw_shape(self):
        shape_result = self.shape_type

        # Preserve legacy and regular use
        if shape_result == Shape.DEFAULT:
            if self.device_type == 'light':
                shape_result = Shape.CIRCLE

            elif self.device_type == 'switch':
                shape_result = Shape.SQUARE

            elif self.device_type == 'diverter':
                shape_result = Shape.TRIANGLE

            else:  # Draw any other devices as square by default
                shape_result = Shape.SQUARE

        return shape_result


    def paint(self, painter, option, widget=None):
        """Paint this widget to the playfield."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(self.pen)
        painter.rotate(self.angle)

        painter.setBrush(self.widget.get_colored_brush())

        draw_shape = self.draw_shape()
        if draw_shape == Shape.CIRCLE:
            painter.drawEllipse(int(self.device_size / -2), int(self.device_size / -2),
                                int(self.device_size), int(self.device_size))
        else:
            shape_points = self.points_for_draw_shape()
            if shape_points != None:
                scaled_points = map(lambda pair: QPoint(int(pair[0] * self.device_size), int(pair[1] * self.device_size)), shape_points)
                painter.drawPolygon(QPolygon(scaled_points))

    def points_for_draw_shape(self):
        draw_shape = self.draw_shape()
        if draw_shape == Shape.CIRCLE:
            return None # Handle circles with drawEllipse instead

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

    def square_points(self):
        return [[-.5, -.5], [.5, -.5], [.5, .5], [-.5, .5]]

    def rectangle_points(self):
        return [[-.2, -.5], [.2, -.5], [.2, .5], [-.2, .5]]

    def wide_triangle_points(self):
        return [[0, -.6], [-.6, .3], [.6, .3]]

    def arrow_points(self):
        return [[0, -.7], [-.4, 0], [-.2, 0], [-.2, .4], [.2, .4], [.2, 0], [.4, 0]]

    def tall_triangle_points(self):
        return [[0, -.3], [-.3, .7], [.3, .7]]

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
        conf_angle = self.mpfmon.config[self.device_type][self.name].get('angle', -1)

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

        if self.size is not conf_size \
                and self.size is not self.mpfmon.pf_device_size:
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
