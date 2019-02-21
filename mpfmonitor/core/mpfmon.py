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


class DeviceNode(object):
    def __init__(self, name, state, description, parent=None):

        self.name = name
        self.state = state
        self.description = description

        self.parent = parent
        self.children = []
        self._callback = None

        self.setParent(parent)
        self._data = {}

    def setData(self, data):
        if self._callback:
            self._callback()
        self._data = data

    def data(self):
        return self._data

    def sortChildren(self):
        self.children.sort(key=lambda x: x.name)

    def set_change_callback(self, callback):
        if self._callback:
            raise AssertionError("Can only have one callback")
        self._callback = callback

    def setParent(self, parent):
        if parent != None:
            self.parent = parent
            self.parent.appendChild(self)
        else:
            self.parent = None

    def appendChild(self, child):
        self.children.append(child)

    def appendRow(self, child):
        self.children.append(child)

    def childAtRow(self, row):
        #if row not in self.children:
        #    return None
        return self.children[row]

    def rowOfChild(self, child):
        for i, item in enumerate(self.children):
            if item == child:
                return i
        return -1

    def removeChild(self, row):
        value = self.children[row]
        self.children.remove(value)

        return True

    def __len__(self):
        return len(self.children)


class DeviceTreeModel(QAbstractItemModel):

    """A device tree."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.treeView = parent
        self.headers = ['Item', 'State', 'Description']

        self.columns = 2

        # Create items
        self.root = DeviceNode('root', 'on', 'this is root', None)

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def flags(self, index):
        defaultFlags = QAbstractItemModel.flags(self, index)

        if index.isValid():
            return Qt.ItemIsEditable | Qt.ItemIsDragEnabled | \
                   Qt.ItemIsDropEnabled | defaultFlags

        else:
            return Qt.ItemIsDropEnabled | defaultFlags

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.headers[section])
        return QVariant()

    def insertRow(self, row, parent):
        return self.insertRows(row, 1, parent)

    def insertRows(self, row, count, parent):
        self.beginInsertRows(parent, row, (row + (count - 1)))
        self.endInsertRows()
        return True

    def removeRow(self, row, parentIndex):
        return self.removeRows(row, 1, parentIndex)

    def removeRows(self, row, count, parentIndex):
        self.beginRemoveRows(parentIndex, row, row)
        node = self.nodeFromIndex(parentIndex)
        node.removeChild(row)
        self.endRemoveRows()
        return True

    def index(self, row, column, parent):
        node = self.nodeFromIndex(parent)
        return self.createIndex(row, column, node.childAtRow(row))

    def data(self, index, role):
        if role == Qt.DecorationRole:
            return QVariant()

        if role == Qt.TextAlignmentRole:
            return QVariant(int(Qt.AlignTop | Qt.AlignLeft))

        if role != Qt.DisplayRole:
            return QVariant()

        node = self.nodeFromIndex(index)

        if index.column() == 0:
            return QVariant(node.name)

        elif index.column() == 1:
            return QVariant(node.state)

        elif index.column() == 2:
            return QVariant(node.description)
        else:
            return QVariant()

    def columnCount(self, parent):
        return self.columns

    def rowCount(self, parent):
        node = self.nodeFromIndex(parent)
        if node is None:
            return 0
        return len(node)

    def parent(self, child):
        if not child.isValid():
            return QModelIndex()

        node = self.nodeFromIndex(child)

        if node is None:
            return QModelIndex()

        parent = node.parent

        if parent is None:
            return QModelIndex()

        grandparent = parent.parent
        if grandparent is None:
            return QModelIndex()
        row = grandparent.rowOfChild(parent)

        assert row != - 1
        return self.createIndex(row, 0, parent)

    def nodeFromIndex(self, index):
        return index.internalPointer() if index.isValid() else self.root

    def itemFromIndex(self, index):
        return index.internalPointer() if index.isValid() else self.root

    def refreshData(self):
        """Updates the data on all nodes, but without having to perform a full reset.

        A full reset on a tree makes us lose selection and expansion states. When all we ant to do
        is to refresh the data on the nodes without adding or removing a node, a call on
        dataChanged() is better. But of course, Qt makes our life complicated by asking us topLeft
        and bottomRight indexes. This is a convenience method refreshing the whole tree.
        """
        columnCount = self.columnCount(self.root)
        rowCount = len(self.root.children)
        if not rowCount:
            return
        topLeft = self.index(0, 0, QModelIndex())
        bottomRight = self.index(rowCount - 1, columnCount - 1, QModelIndex())
        self.dataChanged.emit(topLeft, bottomRight, [])


class MainWindow(QTreeView):
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
        self.playfield_image_file = os.path.join(self.machine_path,
                                        "monitor", "playfield.jpg")

        self.local_settings = QSettings("Mission Pinball", "mpf-monitor")

        self.load_config()

        self.move(self.local_settings.value('windows/devices/pos',
                                            QPoint(200, 200)))
        self.resize(self.local_settings.value('windows/devices/size',
                                            QSize(300, 600)))

        self.setWindowTitle("Devices")

        self.pf_device_size = self.config.get("device_size", .02)

        self.device_states = dict()
        self.device_type_widgets = dict()

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, 'localhost', 5051)

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(20)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start()

        self.toggle_pf_window_action = QAction('&Playfield', self,
                                        statusTip='Show the playfield window',
                                        triggered=self.toggle_pf_window)
        self.toggle_pf_window_action.setCheckable(True)

        self.toggle_device_window_action = QAction('&Devices', self,
                                        statusTip='Show the device window',
                                        triggered=self.toggle_device_window)
        self.toggle_device_window_action.setCheckable(True)

        self.toggle_event_window_action = QAction('&Events', self,
                                        statusTip='Show the events window',
                                        triggered=self.toggle_event_window)
        self.toggle_event_window_action.setCheckable(True)

        self.scene = QGraphicsScene()

        self.pf = PfPixmapItem(QPixmap(self.playfield_image_file), self)
        self.scene.addItem(self.pf)

        self.view = PfView(self.scene, self)

        self.view.move(self.local_settings.value('windows/pf/pos',
                                                 QPoint(800, 200)))
        self.view.resize(self.local_settings.value('windows/pf/size',
                                                   QSize(300, 600)))
        if 1 or self.local_settings.value('windows/pf/visible', True):
            self.toggle_pf_window()

        self.treeview = self
        self.model = DeviceTreeModel(self)
        self.rootNode = self.model.root
        self.treeview.setDragDropMode(QAbstractItemView.DragOnly)
        self.treeview.setItemDelegate(DeviceDelegate())
        self.treeview.setModel(self.model)

        self.event_window = EventWindow(self)

        if 1 or self.local_settings.value('windows/events/visible', True):
            self.toggle_event_window()

        self.mode_window = ModeWindow(self)
        self.mode_window.show()

        self.menu_bar = QMenuBar()
        self.view_menu = self.menu_bar.addMenu("&View")
        self.view_menu.addAction(self.toggle_pf_window_action)
        self.view_menu.addAction(self.toggle_device_window_action)
        self.view_menu.addAction(self.toggle_event_window_action)

        if 1 or self.local_settings.value('windows/devices/visible', True):
            self.toggle_device_window()

    def toggle_pf_window(self):
        if self.view.isVisible():
            self.view.hide()
            self.toggle_pf_window_action.setChecked(False)
        else:
            self.view.show()
            self.toggle_pf_window_action.setChecked(True)

    def toggle_device_window(self):
        if self.treeview.isVisible():
            self.treeview.hide()
            self.toggle_device_window_action.setChecked(False)
        else:
            self.treeview.show()
            self.toggle_device_window_action.setChecked(True)

    def toggle_event_window(self):
        if self.event_window.isVisible():
            self.event_window.hide()
            self.toggle_event_window_action.setChecked(False)
        else:
            self.event_window.show()
            self.toggle_event_window_action.setChecked(True)

    def except_hook(self, cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)
        self.app.exit()

    def reset_connection(self):
        self.start_time = 0
        self.event_window.model.clear()
        self.mode_window.model.clear()

    def eventFilter(self, source, event):
        try:
            if source is self.playfield and event.type() == QEvent.Resize:
                self.playfield.setPixmap(self.playfield_image.scaled(
                    self.playfield.size(), Qt.KeepAspectRatio,
                    Qt.SmoothTransformation))
        except AttributeError:
            pass

        return super().eventFilter(source, event)

    def tick(self):
        device_update = False
        while not self.receive_queue.empty():
            cmd, kwargs = self.receive_queue.get_nowait()
            if cmd == 'device':
                self.process_device_update(**kwargs)
                device_update = True
            elif cmd == 'monitored_event':
                self.process_event_update(**kwargs)
            elif cmd in ('mode_start', 'mode_stop', 'mode_list'):
                self.process_mode_update(kwargs['running_modes'])
            elif cmd == 'reset':
                self.reset_connection()
                self.bcp.send("reset_complete")
        if device_update:
            self.model.refreshData()

    def process_mode_update(self, running_modes):
        """Update mode list."""
        self.mode_window.model.clear()
        for mode in running_modes:
            mode_name = QStandardItem(mode[0])
            mode_prio = QStandardItem(str(mode[1]))
            self.mode_window.model.appendRow([mode_name, mode_prio])

    def process_device_update(self, name, state, changes, type):
        self.log.debug("Device Update: {}.{}: {}".format(type, name, state))

        if type not in self.device_states:
            self.device_states[type] = dict()
            node = DeviceNode(type, "", "", self.rootNode)
            self.device_type_widgets[type] = node
            self.model.insertRow(0, QModelIndex())
            self.rootNode.sortChildren()

        if name not in self.device_states[type]:

            node = DeviceNode(name, "", "", self.device_type_widgets[type])
            self.device_states[type][name] = node
            self.device_type_widgets[type].sortChildren()

            self.pf.create_widget_from_config(node, type, name)

        self.device_states[type][name].setData(state)
        self.model.setData(self.model.index(0, 0, QModelIndex()), None)

    def process_event_update(self, event_name, event_type, event_callback,
                             event_kwargs, registered_handlers):

        from_bcp = event_kwargs.pop('_from_bcp', False)

        name = QStandardItem(event_name)
        kwargs = QStandardItem(str(event_kwargs))
        # ev_time = QStandardItem(time.time())
        self.event_window.model.insertRow(0, [name, kwargs])

        # for rh in registered_handlers:
        #     rh_name = QStandardItem(rh[0])
        #     rh_kwargs = QStandardItem(rh[1])
        #     self.event_window.model.index(0, 0).appendRow([rh_name, rh_kwargs])

    def about(self):
        QMessageBox.about(self, "About MPF Monitor",
                "This is the MPF Monitor")

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
                self.config = dict()

    def save_config(self):
        self.log.debug("Saving config to disk")
        with open(self.config_file, 'w') as f:
            f.write(yaml.dump(self.config, default_flow_style=False))

    def closeEvent(self, event):
        self.write_local_settings()
        event.accept()

    def write_local_settings(self):
        self.local_settings.setValue('windows/devices/pos', self.pos())
        self.local_settings.setValue('windows/devices/size', self.size())
        self.local_settings.setValue('windows/devices/visible', self.isVisible())

        self.local_settings.setValue('windows/pf/pos', self.view.pos())
        self.local_settings.setValue('windows/pf/size', self.view.size())
        self.local_settings.setValue('windows/pf/visible', self.view.isVisible())

        self.local_settings.setValue('windows/events/pos',
                                     self.event_window.pos())
        self.local_settings.setValue('windows/events/size',
                                     self.event_window.size())
        self.local_settings.setValue('windows/event/visible',
                                     self.event_window.isVisible())


class DeviceDelegate(QStyledItemDelegate):

    def paint(self, painter, view, index):
        super().paint(painter, view, index)
        color = None
        state = None
        balls = None
        found = False
        text = ''

        num_circles = 1

        if index.column() == 0:
            return

        try:
            if 'color' in index.model().itemFromIndex(index).data():
                color = index.model().itemFromIndex(index).data()['color']
                found = True
        except TypeError:
            return

        try:
            if 'brightness' in index.model().itemFromIndex(index).data():
                color = [index.model().itemFromIndex(index).data()['brightness']]*3
                found = True
        except TypeError:
            return

        try:
            if 'state' in index.model().itemFromIndex(index).data():
                text = str(index.model().itemFromIndex(index).data()['state'])
                found = True
        except TypeError:
            return

        try:
            if 'complete' in index.model().itemFromIndex(index).data():
                state = not index.model().itemFromIndex(index).data()[
                    'complete']
                found = True
        except TypeError:
            return

        try:
            if 'enabled' in index.model().itemFromIndex(index).data():
                state = index.model().itemFromIndex(index).data()[
                    'enabled']
                found = True
        except TypeError:
            return

        try:
            if 'balls' in index.model().itemFromIndex(index).data():
                balls = index.model().itemFromIndex(index).data()['balls']
                found = True
        except TypeError:
            return

        try:
            if 'balls_locked' in index.model().itemFromIndex(index).data():
                balls = index.model().itemFromIndex(index).data()['balls_locked']
                found = True
        except TypeError:
            return

        try:
            if 'num_balls_requested' in index.model().itemFromIndex(
                    index).data():
                text += 'Requested: {} '.format(
                    index.model().itemFromIndex(index).data()['num_balls_requested'])
                found = True
        except TypeError:
            return

        try:
            if 'unexpected_balls' in index.model().itemFromIndex(
                    index).data():
                text += 'Unexpected: {} '.format(
                    index.model().itemFromIndex(index).data()['unexpected_balls'])
                found = True
        except TypeError:
            return

        if not found:
            return

        text += " " + str(index.model().itemFromIndex(index).data())

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
                             str(text))

        painter.restore()


class PfView(QGraphicsView):

    def __init__(self, parent, mpfmon):
        self.mpfmon = mpfmon
        super().__init__(parent)

        self.setWindowTitle("Playfield")

    def resizeEvent(self, event):
        self.fitInView(self.mpfmon.pf, Qt.KeepAspectRatio)


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

        widget.set_change_callback(self.notify)

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

    def paint(self, painter, option, widget=None):
        if self.device_type == 'light':
            color = self.widget.data()['color']

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

    def notify(self):
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
        x = self.pos().x() / self.mpfmon.scene.width() if self.mpfmon.scene.width() > 0 else self.pos().x()
        y = self.pos().y() / self.mpfmon.scene.height() if self.mpfmon.scene.height() > 0 else self.pos().y()

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

        self.move(self.mpfmon.local_settings.value('windows/events/pos',
                                                   QPoint(500, 200)))
        self.resize(self.mpfmon.local_settings.value('windows/events/size',
                                                     QSize(300, 600)))

class ModeWindow(QTreeView):

    def __init__(self, mpfmon):
        self.mpfmon = mpfmon
        super().__init__()

        self.setWindowTitle('Running Modes')
        self.model = QStandardItemModel()
        self.setModel(self.model)
        self.rootNode = self.model.invisibleRootItem()
        self.setSortingEnabled(True)

        self.move(self.mpfmon.local_settings.value('windows/modes/pos',
                                                   QPoint(1100, 200)))
        self.resize(self.mpfmon.local_settings.value('windows/modes/size',
                                                     QSize(300, 600)))


def run(machine_path, thread_stopper):

    app = QApplication(sys.argv)
    MainWindow(app, machine_path, thread_stopper)
    app.exec_()
