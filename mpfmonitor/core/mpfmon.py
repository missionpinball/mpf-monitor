import logging
import queue
import threading
import sys

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from mpfmonitor.core.bcp_client import BCPClient


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.resize(520,300)
        self.setWindowTitle("MPF Monitor")

        self.log = logging.getLogger('Core')

        self.bcp_client_connected = False
        self.receive_queue = queue.Queue()
        self.sending_queue = queue.Queue()
        self.crash_queue = queue.Queue()
        self.thread_stopper = threading.Event()

        self.device_states = dict()
        self.device_type_widgets = dict()

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, 'localhost', 5051)

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(20)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start()

        self.treeview = QTreeView(self)

        model = QStandardItemModel()
        self.rootNode = model.invisibleRootItem()

        # self.treeview.setHorizontalHeaderLabels(['Device', 'State'])
        self.treeview.setSortingEnabled(True)
        self.treeview.setItemDelegate(DeviceDelegate())

        self.treeview.setModel(model)
        self.treeview.setColumnWidth(0, 150)

        self.setCentralWidget(self.treeview)

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

            self.device_type_widgets['{}.{}'.format(type, name)] = _state

        self.device_states[type][name].setData(state)


class DeviceDelegate(QStyledItemDelegate):

    def paint(self, painter, view, index):
        super().paint(painter, view, index)
        color = None
        state = None
        balls = None
        bd_state = None
        # complete = bool
        # _enabled
        balls_locked = None
        found = False

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
            if 'balls' in index.model().itemFromIndex(index).data():
                # print(index.model().itemData(index))['_color']
                balls = index.model().itemFromIndex(index).data()['balls']
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
        # painter.setPen(Qt.NoPen)
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


        # painter.translate(rect.x() + 15, rect.y() + 10)

        x_offset = 0
        for _ in range(num_circles):
            if num_circles > 1:
                print("Number circles", num_circles, x_offset)

            painter.drawEllipse(
                view.rect.x() + x_offset, view.rect.y(), 14, 14)

            x_offset += 20

        painter.restore()


def run():

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec_()
