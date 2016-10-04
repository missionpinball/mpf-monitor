import logging
import queue
import sys
import os
import time

import ruamel.yaml as yaml

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from mpfmonitor.core.bcp_client import BCPClient


class MainWindow(QMainWindow):
    def __init__(self, machine_path, thread_stopper, parent=None):
        super().__init__(parent)

        self.resize(400, 800)
        self.setWindowTitle("MPF Devices")

        self.log = logging.getLogger('Core')

        sys.excepthook = self.except_hook

        self.bcp_client_connected = False
        self.receive_queue = queue.Queue()
        self.sending_queue = queue.Queue()
        self.crash_queue = queue.Queue()
        self.thread_stopper = thread_stopper
        self.machine_path = machine_path
        self.config = None
        self.config_file = os.path.join(self.machine_path, "monitor",
                                        "monitor.yaml")

        self.load_config()

        self.pf_device_size = .05

        self.device_states = dict()
        self.device_type_widgets = dict()

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, 'localhost', 5051)

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(20)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start()

        self.scene = QGraphicsScene()

        self.pf = PfPixmapItem(QPixmap('monitor/playfield.jpg'), self)

        self.scene.addItem(self.pf)

        self.view = PfView(self.scene, self.pf)
        self.view.show()

        self.treeview = QTreeView(self)
        model = QStandardItemModel()
        self.rootNode = model.invisibleRootItem()
        self.treeview.setSortingEnabled(True)
        self.treeview.setDragDropMode(QAbstractItemView.DragOnly)
        self.treeview.setItemDelegate(DeviceDelegate())
        self.treeview.setModel(model)

        self.setCentralWidget(self.treeview)

    def except_hook(self, exception, traceback):
        sys.__excepthook__(self, exception, traceback)

    def eventFilter(self, source, event):
        if source is self.playfield and event.type() == QEvent.Resize:
            self.playfield.setPixmap(self.playfield_image.scaled(
                self.playfield.size(), Qt.KeepAspectRatio,
                Qt.SmoothTransformation))

        return super().eventFilter(source, event)

    def tick(self):
        while not self.receive_queue.empty():
            cmd, kwargs = self.receive_queue.get_nowait()
            if cmd == 'device':
                self.process_device_update(**kwargs)

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

    def about(self):
        QMessageBox.about(self, "About MPF Monitor",
                "This is the MPF Monitor")

    def load_config(self):

        try:
            with open(self.config_file, 'r') as f:
                self.config = yaml.load(f)
        except FileNotFoundError:
                self.config = dict()

    def save_config(self):
        print("Saving monitor.yaml")
        with open(self.config_file, 'w') as f:
            f.write(yaml.dump(self.config, default_flow_style=False))


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
        painter.setPen(QPen(Qt.gray, 1, Qt.SolidLine))

        if color:
            painter.setBrush(QBrush(QColor(*color),Qt.SolidPattern))
        elif state is True:
            painter.setBrush(QBrush(QColor(0, 255, 0),Qt.SolidPattern))
        elif state is False:
            painter.setBrush(QBrush(QColor(255, 255, 255),Qt.SolidPattern))
        elif isinstance(balls, int):
            painter.setBrush(QBrush(QColor(0, 255, 0),Qt.SolidPattern))
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

    def __init__(self, parent, pf):
        self.pf = pf
        super().__init__(parent)

    def resizeEvent(self, event):
        self.fitInView(self.pf, Qt.KeepAspectRatio)


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

        current_pf_height = self.boundingRect().height()
        current_pf_width = self.boundingRect().width()

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
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setPos(x, y)
        self.update_pos(save)
        self.click_start = 0

    def boundingRect(self):
        return QRectF(self.device_size / -2, self.device_size / -2,
                      self.device_size, self.device_size)

    def paint(self, painter, option, widget):
        if self.device_type == 'led':
            color = self.widget.data()['_color']

            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(Qt.gray, 1, Qt.SolidLine))
            painter.setBrush(QBrush(QColor(*color),Qt.SolidPattern))
            painter.drawEllipse(self.device_size / -2, self.device_size / -2,
                                self.device_size, self.device_size)

        if self.device_type == 'switch':
            state = self.widget.data()['state']

            if state:
                color = [0, 255, 0]
            else:
                color = [0, 0, 0]

            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(Qt.gray, 1, Qt.SolidLine))
            painter.setBrush(QBrush(QColor(*color),Qt.SolidPattern))
            painter.drawRect(self.device_size / -2, self.device_size / -2,
                             self.device_size, self.device_size)

    def notify(self, source):
        if source == self.widget:
            self.update()

    def mouseMoveEvent(self, event):
        if (self.mpfmon.pf.boundingRect().width() > event.scenePos().x() >
                0) and (self.mpfmon.pf.boundingRect().height() >
                event.scenePos().y() > 0):
            # devices off the pf do weird things at the moment
            self.setPos(event.scenePos())
            self.move_in_progress = True

    def mousePressEvent(self, event):
        if self.device_type == 'switch':
            self.click_start = time.time()
            self.mpfmon.bcp.send('switch', name=self.name, state=-1)

    def mouseReleaseEvent(self, event):
        if self.move_in_progress and time.time() - self.click_start > .1:
            self.move_in_progress = False
            self.update_pos()

        elif self.device_type == 'switch' and self.click_start:
            if time.time() - self.click_start < .6:
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

def run(machine_path, thread_stopper):

    app = QApplication(sys.argv)
    w = MainWindow(machine_path, thread_stopper)
    w.show()
    app.exec_()
