import logging
import queue
import sys
import os
import time

# will change these to specific imports once code is more final
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import ruamel.yaml as yaml

from mpfmonitor.core.bcp_client import BCPClient


class MainWindow(QMainWindow):
    def __init__(self, app, machine_path, thread_stopper, parent=None):

        super().__init__(parent)

        self.log = logging.getLogger('Core')

        sys.excepthook = self.except_hook

        self.bcp_client_connected = False
        self.receive_queue = queue.Queue()
        self.sending_queue = queue.Queue()
        self.crash_queue = queue.Queue()
        self.thread_stopper = thread_stopper
        self.machine_path = machine_path
        self.app = app
        self.config = None
        self.layout = None
        self.config_file = os.path.join(self.machine_path, "monitor",
                                        "monitor.yaml")
        self.layout_file = os.path.join(self.machine_path, "monitor",
                                        "layout.yaml")

        self.load_config()
        self.load_layout()

        try:
            self.move(self.layout['windows']['devices']['x'],
                      self.layout['windows']['devices']['y'])
            self.resize(self.layout['windows']['devices']['width'],
                        self.layout['windows']['devices']['height'])
        except KeyError:
            self.layout['windows'] = dict()
            self.layout['windows']['devices'] = dict()
            self.resize(400, 800)

        self.setWindowTitle("Devices")

        self.save_timer = QTimer()

        self.pf_device_size = .05

        self.device_states = dict()
        self.device_type_widgets = dict()

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, 'localhost', 5051)

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(20)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start()

        self.toggle_pf_window_action = QAction('&Playfield',
                                        statusTip='Show the playfield window',
                                        triggered=self.toggle_pf_window)
        self.toggle_pf_window_action.setCheckable(True)

        self.toggle_device_window_action = QAction('&Devices',
                                        statusTip='Show the device window',
                                        triggered=self.toggle_device_window)
        self.toggle_device_window_action.setCheckable(True)

        self.toggle_event_window_action = QAction('&Events',
                                        statusTip='Show the events window',
                                        triggered=self.toggle_event_window)
        self.toggle_event_window_action.setCheckable(True)

        self.scene = QGraphicsScene()

        self.pf = PfPixmapItem(QPixmap('monitor/playfield.jpg'), self)
        self.scene.addItem(self.pf)

        self.view = PfView(self.scene, self)

        try:
            self.view.move(self.layout['windows']['playfield']['x'],
                           self.layout['windows']['playfield']['y'])
            self.view.resize(self.layout['windows']['playfield']['width'],
                             self.layout['windows']['playfield']['height'])
        except KeyError:
            self.layout['windows']['playfield'] = dict()

        if self.layout['windows']['playfield'].get('visible', True):
            self.toggle_pf_window(False)

        self.treeview = QTreeView(self)
        model = QStandardItemModel()
        self.rootNode = model.invisibleRootItem()
        self.treeview.setSortingEnabled(True)
        self.treeview.setDragDropMode(QAbstractItemView.DragOnly)
        self.treeview.setItemDelegate(DeviceDelegate())
        self.treeview.setModel(model)

        self.event_window = EventWindow(self)
        # self.event_model = QStandardItemModel()
        # self.event_window.setModel(self.event_model)
        if self.layout['windows']['events'].get('visible', True):
            self.toggle_event_window(False)

        self.view_menu = self.menuBar().addMenu("&View")
        self.view_menu.addAction(self.toggle_pf_window_action)
        self.view_menu.addAction(self.toggle_device_window_action)
        self.view_menu.addAction(self.toggle_event_window_action)

        if self.layout['windows']['devices'].get('visible', True):
            self.setCentralWidget(self.treeview)
            self.toggle_device_window_action.setChecked(True)

    def toggle_pf_window(self, save=True):
        if self.view.isVisible():
            self.view.hide()
            self.toggle_pf_window_action.setChecked(False)
            self.layout['windows']['playfield']['visible'] = False
        else:
            self.view.show()
            self.toggle_pf_window_action.setChecked(True)
            self.layout['windows']['playfield']['visible'] = True

        if save:
            self.save_layout()

    def toggle_device_window(self, save=True):
        if self.treeview.isVisible():
            self.treeview.hide()
            self.toggle_device_window_action.setChecked(False)
            self.layout['windows']['devices']['visible'] = False
        else:
            self.treeview.show()
            self.toggle_device_window_action.setChecked(True)
            self.layout['windows']['devices']['visible'] = True

        if save:
            self.save_layout()

    def toggle_event_window(self, save=True):
        if self.event_window.isVisible():
            self.event_window.hide()
            self.toggle_event_window_action.setChecked(False)
            self.layout['windows']['events']['visible'] = False
        else:
            self.event_window.show()
            self.toggle_event_window_action.setChecked(True)
            self.layout['windows']['events']['visible'] = True

        if save:
            self.save_layout()

    def except_hook(self, cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)
        self.app.exit()

    def reset_connection(self):
        self.start_time = 0
        self.event_window.model.clear()

    def eventFilter(self, source, event):
        if source is self.playfield and event.type() == QEvent.Resize:
            self.playfield.setPixmap(self.playfield_image.scaled(
                self.playfield.size(), Qt.KeepAspectRatio,
                Qt.SmoothTransformation))

        return super().eventFilter(source, event)

    def resizeEvent(self, event):
        self.layout['windows']['devices']['width'] = self.size().width()
        self.layout['windows']['devices']['height'] = self.size().height()
        self.save_layout()

    def moveEvent(self, event):
        self.layout['windows']['devices']['x'] = self.pos().x()
        self.layout['windows']['devices']['y'] = self.pos().y()
        self.save_layout()

    def tick(self):
        while not self.receive_queue.empty():
            cmd, kwargs = self.receive_queue.get_nowait()
            if cmd == 'device':
                self.process_device_update(**kwargs)
            elif cmd == 'monitored_event':
                self.process_event_update(**kwargs)

    def process_device_update(self, name, state, changes, type):
        self.log.debug("Device Update: {}.{}: {}".format(type, name, state))

        if type not in self.device_states:
            self.device_states[type] = dict()
            node = QStandardItem(type)
            self.device_type_widgets[type] = node
            self.rootNode.appendRow([node, None])
            self.rootNode.sortChildren(0)

        if name not in self.device_states[type]:

            node = QStandardItem(name)
            _state = QStandardItem()
            self.device_states[type][name] = _state

            self.device_type_widgets[type].appendRow([node, _state])
            self.device_type_widgets[type].sortChildren(0)

            self.pf.create_widget_from_config(_state, type, name)

        self.device_states[type][name].setData(state)

    def process_event_update(self, event_name, event_type, event_callback,
                             event_kwargs, registered_handlers):

        from_bcp = event_kwargs.pop('_from_bcp', False)

        name = QStandardItem(event_name)
        kwargs = QStandardItem(str(event_kwargs))
        # ev_time = QStandardItem(time.time())
        self.event_window.model.insertRow(0, [name, kwargs])

        # if registered_handlers:
        #     handlers = QStandardItem(registered_handlers)
        #     name.appendRow(handlers)

    def about(self):
        QMessageBox.about(self, "About MPF Monitor",
                "This is the MPF Monitor")

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                self.config = yaml.load(f)
        except FileNotFoundError:
                self.config = dict()

    def load_layout(self):
        try:
            with open(self.layout_file, 'r') as f:
                self.layout = yaml.load(f)
        except FileNotFoundError:
                self.layout = dict()

    def save_config(self):
        print("Saving config to disk")
        with open(self.config_file, 'w') as f:
            f.write(yaml.dump(self.config, default_flow_style=False))

    def save_layout(self):
        print("Saving layout to disk")
        with open(self.layout_file, 'w') as f:
            f.write(yaml.dump(self.layout, default_flow_style=False))


class DeviceDelegate(QStyledItemDelegate):

    def paint(self, painter, view, index):
        super().paint(painter, view, index)
        color = None
        state = None
        balls = None
        found = False
        text = ''

        num_circles = 1

        try:
            if '_color' in index.model().itemFromIndex(index).data():
                # print(index.model().itemData(index))['_color']
                color = index.model().itemFromIndex(index).data()['_color']
                found = True
        except TypeError:
            return

        try:
            if '_brightness' in index.model().itemFromIndex(index).data():
                # print(index.model().itemData(index))['_color']
                color = [index.model().itemFromIndex(index).data()['_brightness']]*3
                found = True
        except TypeError:
            return

        try:
            if 'state' in index.model().itemFromIndex(index).data():
                # print(index.model().itemData(index))['_color']
                state = True == index.model().itemFromIndex(index).data()[
                    'state']
                found = True
        except TypeError:
            return

        try:
            if 'complete' in index.model().itemFromIndex(index).data():
                # print(index.model().itemData(index))['_color']
                state = not index.model().itemFromIndex(index).data()[
                    'complete']
                found = True
        except TypeError:
            return

        try:
            if '_enabled' in index.model().itemFromIndex(index).data():
                # print(index.model().itemData(index))['_color']
                state = index.model().itemFromIndex(index).data()[
                    '_enabled']
                found = True
        except TypeError:
            return

        try:
            if 'balls' in index.model().itemFromIndex(index).data():
                # print(index.model().itemData(index))['_color']
                balls = index.model().itemFromIndex(index).data()['balls']
                found = True
        except TypeError:
            return

        try:
            if 'balls_locked' in index.model().itemFromIndex(index).data():
                # print(index.model().itemData(index))['_color']
                balls = index.model().itemFromIndex(index).data()['balls_locked']
                found = True
        except TypeError:
            return

        try:
            if '_state' in index.model().itemFromIndex(index).data():
                # print(index.model().itemData(index))['_color']
                text = index.model().itemFromIndex(index).data()['_state']
                found = True
        except TypeError:
            return

        try:
            if 'num_balls_requested' in index.model().itemFromIndex(
                    index).data():
                # print(index.model().itemData(index))['_color']
                text += 'Requested: {} '.format(
                    index.model().itemFromIndex(index).data()['num_balls_requested'])
                found = True
        except TypeError:
            return

        try:
            if 'unexpected_balls' in index.model().itemFromIndex(
                    index).data():
                # print(index.model().itemData(index))['_color']
                text += 'Unexpected: {} '.format(
                    index.model().itemFromIndex(index).data()['unexpected_balls'])
                found = True
        except TypeError:
            return

        if not found:
            return

        if index.column() == 0:
            super().paint(painter, view, index)
            return

        painter.save()

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor(100, 100, 100), 1, Qt.SolidLine))

        if color:
            painter.setBrush(QBrush(QColor(*color), Qt.SolidPattern))
        elif state is True:
            painter.setBrush(QBrush(QColor(0, 255, 0), Qt.SolidPattern))
        elif state is False:
            painter.setBrush(QBrush(QColor(255, 255, 255), Qt.SolidPattern))
        elif isinstance(balls, int):
            painter.setBrush(QBrush(QColor(0, 255, 0), Qt.SolidPattern))
            num_circles = balls

        x_offset = 0
        for _ in range(num_circles):
            painter.drawEllipse(
                view.rect.x() + x_offset, view.rect.y(), 14, 14)

            x_offset += 20

        if text:
            painter.drawText(view.rect.x() + x_offset, view.rect.y() + 12,
                             text)

        painter.restore()


class PfView(QGraphicsView):

    def __init__(self, parent, mpfmon):
        self.mpfmon = mpfmon
        super().__init__(parent)

        self.setWindowTitle("Playfield")

    def resizeEvent(self, event):
        self.fitInView(self.mpfmon.pf, Qt.KeepAspectRatio)

        self.mpfmon.layout['windows']['playfield']['width'] = self.size().width()
        self.mpfmon.layout['windows']['playfield']['height'] = self.size().height()

        self.mpfmon.save_layout()

    def moveEvent(self, event):
        self.mpfmon.layout['windows']['playfield']['x'] = self.pos().x()
        self.mpfmon.layout['windows']['playfield']['y'] = self.pos().y()

        self.mpfmon.save_layout()


class PfPixmapItem(QGraphicsPixmapItem):

    def __init__(self, image, mpfmon, parent=None):
        super().__init__(image, parent)

        self.mpfmon = mpfmon
        self.setAcceptDrops(True)

    def create_widget_from_config(self, widget, device_type, device_name):
        try:
            x = self.mpfmon.config[device_type][device_name]['x']
            y = self.mpfmon.config[device_type][device_name]['y']
        except KeyError:
            return

        x *= self.mpfmon.scene.width()
        y *= self.mpfmon.scene.height()

        self.create_pf_widget(widget, device_type, device_name, x, y, False)

    def dragEnterEvent(self, event):
        # print(event)
        event.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):
        device = event.source().selectedIndexes()[0]
        device_name = device.data()
        device_type = device.parent().data()
        widget = self.mpfmon.device_states[device_type][device_name]

        drop_x = event.scenePos().x()
        drop_y = event.scenePos().y()

        self.create_pf_widget(widget, device_type, device_name, drop_x,
                              drop_y)

    def create_pf_widget(self, widget, device_type, device_name, drop_x,
                         drop_y, save=True):
        w = PfWidget(self.mpfmon, widget, device_type, device_name, drop_x,
                     drop_y, save)
        self.mpfmon.scene.addItem(w)


class PfWidget(QGraphicsItem):

    def __init__(self, mpfmon, widget, device_type, device_name, x, y,
                 save=True):
        super().__init__()

        widget.model().itemChanged.connect(self.notify, Qt.QueuedConnection)

        self.widget = widget
        self.mpfmon = mpfmon
        self.name = device_name
        self.move_in_progress = True
        self.device_type = device_type
        self.device_size = self.mpfmon.scene.width() * \
                           self.mpfmon.pf_device_size

        self.setToolTip('{}: {}'.format(self.device_type, self.name))
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        self.setPos(x, y)
        self.update_pos(save)
        self.click_start = 0
        self.release_switch = False

    def boundingRect(self):
        return QRectF(self.device_size / -2, self.device_size / -2,
                      self.device_size, self.device_size)

    def paint(self, painter, option, widget):
        if self.device_type == 'led':
            color = self.widget.data()['_color']

            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(Qt.white, 3, Qt.SolidLine))
            painter.setBrush(QBrush(QColor(*color), Qt.SolidPattern))
            painter.drawEllipse(self.device_size / -2, self.device_size / -2,
                                self.device_size, self.device_size)

        elif self.device_type == 'switch':
            state = self.widget.data()['state']

            if state:
                color = [0, 255, 0]
            else:
                color = [0, 0, 0]

            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(Qt.white, 3, Qt.SolidLine))
            painter.setBrush(QBrush(QColor(*color), Qt.SolidPattern))
            painter.drawRect(self.device_size / -2, self.device_size / -2,
                             self.device_size, self.device_size)

        elif self.device_type == 'light':
            color = [self.widget.data()['_brightness']]*3

            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(Qt.white, 3, Qt.SolidLine))
            painter.setBrush(QBrush(QColor(*color), Qt.SolidPattern))
            painter.drawEllipse(self.device_size / -2, self.device_size / -2,
                                self.device_size, self.device_size)

    def notify(self, source):
        if source == self.widget:
            self.update()

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
            if event.buttons() & Qt.RightButton:
                self.mpfmon.bcp.send('switch', name=self.name, state=-1)
                self.release_switch = False
            elif event.buttons() & Qt.LeftButton:
                self.mpfmon.bcp.send('switch', name=self.name, state=-1)
                self.release_switch = True

    def mouseReleaseEvent(self, event):
        if self.move_in_progress and time.time() - self.click_start > .5:
            self.move_in_progress = False
            self.update_pos()

        elif self.release_switch:
            self.mpfmon.bcp.send('switch', name=self.name, state=-1)

        self.click_start = 0

    def update_pos(self, save=True):
        x = self.pos().x() / self.mpfmon.scene.width()
        y = self.pos().y() / self.mpfmon.scene.height()

        if self.device_type not in self.mpfmon.config:
            self.mpfmon.config[self.device_type] = dict()

        if self.name not in self.mpfmon.config[self.device_type]:
            self.mpfmon.config[self.device_type][self.name] = dict()

        self.mpfmon.config[self.device_type][self.name]['x'] = x
        self.mpfmon.config[self.device_type][self.name]['y'] = y

        if save:
            self.mpfmon.save_config()


class EventWindow(QTreeView):

    def __init__(self, mpfmon):
        self.mpfmon = mpfmon
        super().__init__()

        self.setWindowTitle('Events')
        self.model = QStandardItemModel()
        self.setModel(self.model)
        self.rootNode = self.model.invisibleRootItem()
        self.setSortingEnabled(True)

        try:
            self.move(self.mpfmon.layout['windows']['events']['x'],
                           self.mpfmon.layout['windows']['events']['y'])
            self.resize(self.mpfmon.layout['windows']['events']['width'],
                             self.mpfmon.layout['windows']['events']['height'])
        except KeyError:
            self.mpfmon.layout['windows']['events'] = dict()

    def resizeEvent(self, event):
        self.mpfmon.layout['windows']['events']['width'] = self.size().width()
        self.mpfmon.layout['windows']['events']['height'] = self.size().height()

        self.mpfmon.save_layout()

    def moveEvent(self, event):
        self.mpfmon.layout['windows']['events']['x'] = self.pos().x()
        self.mpfmon.layout['windows']['events']['y'] = self.pos().y()

        self.mpfmon.save_layout()


def run(machine_path, thread_stopper):

    app = QApplication(sys.argv)
    w = MainWindow(app, machine_path, thread_stopper)
    w.show()
    app.exec_()
