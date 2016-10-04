import logging
import queue
import sys

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from mpfmonitor.core.bcp_client import BCPClient


class MainWindow(QMainWindow):
    def __init__(self, thread_stopper, parent=None):
        super().__init__(parent)

        self.resize(1024, 768)
        self.setWindowTitle("MPF Monitor")

        self.log = logging.getLogger('Core')

        sys.excepthook = self.except_hook

        self.bcp_client_connected = False
        self.receive_queue = queue.Queue()
        self.sending_queue = queue.Queue()
        self.crash_queue = queue.Queue()
        self.thread_stopper = thread_stopper

        self.pf_device_size = .05

        self.device_states = dict()
        self.device_type_widgets = dict()

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, 'localhost', 5051)

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(20)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start()

        self.hbox = QHBoxLayout()

        self.playfield_frame = Playfield(self)

        self.playfield_image = QPixmap('monitor/playfield.jpg')
        self.playfield = QLabel(self.playfield_frame)
        self.playfield.setPixmap(self.playfield_image)
        self.playfield.setMinimumSize(1, 1)
        self.playfield.setAlignment(Qt.AlignCenter)
        self.playfield.installEventFilter(self)

        self.scene = QGraphicsScene()

        pf = PfPixmapItem(QPixmap('monitor/playfield.jpg'), self)

        self.scene.addItem(pf)

        self.view = PfView(self.scene, pf)
        self.view.show()


        self.hbox.addWidget(self.playfield)

        main_widget = self.playfield_frame
        main_widget.setLayout(self.hbox)

        self.setCentralWidget(main_widget)

        # self.createActions()
        self.createMenus()
        self.createToolBars()
        self.createStatusBar()
        self.createDockWindows()

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

            # self.device_type_widgets['{}.{}'.format(type, name)] = _state

        self.device_states[type][name].setData(state)

    def createDockWindows(self):

        # Devices window

        dock = QDockWidget("Devices", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.treeview = QTreeView(dock)

        self.model = QStandardItemModel()
        self.rootNode = self.model.invisibleRootItem()

        self.treeview.setSortingEnabled(True)
        self.treeview.setItemDelegate(DeviceDelegate())
        self.treeview.setDragDropMode(QAbstractItemView.DragOnly)

        self.treeview.setModel(self.model)
        self.treeview.setColumnWidth(0, 150)

        dock.setWidget(self.treeview)

        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.viewMenu.addAction(dock.toggleViewAction())

        # Event window

        dock = QDockWidget("MPF Event History", self)
        self.event_list = QListWidget(dock)
        #
        dock.setWidget(self.event_list)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.viewMenu.addAction(dock.toggleViewAction())

        # self.customerList.currentTextChanged.connect(self.insertCustomer)
        # self.event_list.currentTextChanged.connect(self.addParagraph)

    def add_event(self, event):
        self.event_list.addItem(event)

    def createToolBars(self):

        # todo, snapshot, buttons to show/hide docks

        self.fileToolBar = self.addToolBar("File")
        # self.fileToolBar.addAction(self.newLetterAct)
        # self.fileToolBar.addAction(self.saveAct)
        # self.fileToolBar.addAction(self.printAct)

        self.editToolBar = self.addToolBar("Edit")
        # self.editToolBar.addAction(self.undoAct)

        # snapshot button
        # pause events

    def createMenus(self):
        self.fileMenu = self.menuBar().addMenu("&File")
        # self.fileMenu.addAction(self.newLetterAct)
        # self.fileMenu.addAction(self.saveAct)
        # self.fileMenu.addAction(self.printAct)
        # self.fileMenu.addSeparator()
        # self.fileMenu.addAction(self.quitAct)

        # self.editMenu = self.menuBar().addMenu("&Edit")
        # self.editMenu.addAction(self.undoAct)
        #
        self.viewMenu = self.menuBar().addMenu("&View")
        #
        # self.menuBar().addSeparator()

        # self.helpMenu = self.menuBar().addMenu("&Help")
        # self.helpMenu.addAction(self.aboutAct)
        # self.helpMenu.addAction(self.aboutQtAct)

    def createStatusBar(self):
        self.statusBar().showMessage("Ready")

    def about(self):
        QMessageBox.about(self, "About MPF Monitor",
                "This is the MPF Monitor")


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
            painter.drawEllipse(
                view.rect.x() + x_offset, view.rect.y(), 14, 14)

            x_offset += 20

        if text:
            painter.drawText(view.rect.x() + x_offset, view.rect.y() + 12,
                             text)

        painter.restore()


class Playfield(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        # print(event)
        event.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):

        device = event.source().selectedIndexes()[0]
        device_name = device.data()
        device_type = device.parent().data()

        drop_x = event.posF().x()
        drop_y = event.posF().y()

        pf_frame_height = self.parent().playfield.height()
        pf_image_height = self.parent().playfield_image.height()

        pf_frame_width = self.parent().playfield.width()
        pf_image_width = self.parent().playfield_image.width()

        ratio = (min(pf_frame_height / pf_image_height,
                     pf_frame_width / pf_image_width))

        current_pf_height = pf_image_height * ratio
        current_pf_width = pf_image_width * ratio

        left = ((self.width() - current_pf_width) / 2)
        right = left + current_pf_width

        top = ((self.height() - current_pf_height) / 2)
        bottom = top + current_pf_height

        drop_x_percent = ((drop_x - left) / (right - left))
        drop_y_percent = ((drop_y - top) / (bottom - top))

        # print('----------------------------------')
        # print('dropped widget {}.{}'.format(device_type, device_name))
        # print('x:', drop_x_percent)
        # print('y:', drop_y_percent)

        self.create_pf_widget('{}.{}'.format(device_type, device_name),
                              drop_x, drop_y)

    # def mousePressEvent(self, event):
    #     print(event)

    def create_pf_widget(self, name, x, y):
        pass


class PfView(QGraphicsView):

    def __init__(self, parent, pf):
        self.pf = pf
        super().__init__(parent)

    def resizeEvent(self, event):
        # print(self.pf, event)
        self.fitInView(self.pf, Qt.KeepAspectRatio)

class PfPixmapItem(QGraphicsPixmapItem):

    def __init__(self, image, mpfmon, parent=None):
        super().__init__(image, parent)

        self.mpfmon = mpfmon
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        # print(event)
        event.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):

        # print(event.scenePos().x())
        # print(event.scenePos().y())
        #
        #
        # print(self.boundingRect().height())
        # print(self.boundingRect().width())

        device = event.source().selectedIndexes()[0]
        device_name = device.data()
        device_type = device.parent().data()
        widget = self.mpfmon.device_states[device_type][device_name]
        wdata = widget.data()

        drop_x = event.scenePos().x()
        drop_y = event.scenePos().y()

        # pf_frame_height = self.parent().playfield.height()
        # pf_image_height = self.parent().playfield_image.height()
        #
        # pf_frame_width = self.parent().playfield.width()
        # pf_image_width = self.parent().playfield_image.width()
        #
        # ratio = (min(pf_frame_height / pf_image_height,
        #              pf_frame_width / pf_image_width))

        current_pf_height = self.boundingRect().height()
        current_pf_width = self.boundingRect().width()

        # left = ((self.width() - current_pf_width) / 2)
        # right = left + current_pf_width
        #
        # top = ((self.height() - current_pf_height) / 2)
        # bottom = top + current_pf_height
        #
        # drop_x_percent = ((drop_x - left) / (right - left))
        # drop_y_percent = ((drop_y - top) / (bottom - top))

        drop_x_percent = drop_x / current_pf_width
        drop_y_percent = drop_y / current_pf_height

        # print('----------------------------------')
        # print('dropped widget {}.{}'.format(device_type, device_name))
        # print('widget', widget)
        # print('wdata', wdata)
        # print('x:', drop_x_percent)
        # print('y:', drop_y_percent)

        self.create_pf_widget(widget, drop_x, drop_y, drop_x_percent,
                              drop_y_percent)

    # def mousePressEvent(self, event):
    #     print(event)

    def create_pf_widget(self, widget, drop_x, drop_y, drop_x_percent,
                              drop_y_percent):
        w = PfWidget(self.mpfmon, widget, drop_x, drop_y, drop_x_percent,
                              drop_y_percent)
        w.setPos(drop_x, drop_y)
        self.mpfmon.scene.addItem(w)


class PfWidget(QGraphicsItem):

    def __init__(self, mpfmon, widget, rel_x, rel_y, x, y):
        super().__init__()

        widget.model().itemChanged.connect(self.notify, Qt.QueuedConnection)

        self.widget = widget
        self.mpfmon = mpfmon
        self.device_size = self.mpfmon.scene.width() * \
                           self.mpfmon.pf_device_size

    def boundingRect(self):
        return QRectF(0, 0, self.device_size, self.device_size)

    def paint(self, painter, option, widget):

        # print("paint", self, painter, option, widget, self.widget.data())

        if '_color' in self.widget.data():
            color = self.widget.data()['_color']

            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(Qt.gray, 1, Qt.SolidLine))
            painter.setBrush(QBrush(QColor(*color),Qt.SolidPattern))
            painter.drawEllipse(0, 0, self.device_size, self.device_size)

    def notify(self, source):
        if source == self.widget:
            self.update()



def run(thread_stopper):

    app = QApplication(sys.argv)
    w = MainWindow(thread_stopper)
    w.show()
    app.exec_()
