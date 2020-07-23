import logging
import time
import os

# will change these to specific imports once code is more final
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import uic

from enum import Enum


class DeviceSort(Enum):
    DEFAULT = 0
    TIME_ASCENDING = 1
    TIME_DESCENDING = 2
    NAME_ASCENDING = 3
    NAME_DESCENDING = 4


class DeviceNode(object):
    def __init__(self, name, state, description, parent=None):

        self.name = name
        self.state = state
        self.description = description
        self.time_added = time.perf_counter()

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

    def sortChildren(self, sort=DeviceSort.DEFAULT):
        if sort == DeviceSort.TIME_DESCENDING:
            self.children.sort(key=lambda x: x.time_added, reverse=True)
        elif sort == DeviceSort.NAME_ASCENDING:
            self.children.sort(key=lambda x: x.name)
        elif sort == DeviceSort.NAME_DESCENDING:
            self.children.sort(key=lambda x: x.name, reverse=True)

        # Handle DEFAULT, TIME_ASCENDING (default), or incorrect sort parameter
        else:
            self.children.sort(key=lambda x: x.time_added)

    def set_change_callback(self, callback):
        if self._callback:
            # raise AssertionError("Can only have one callback")
            old_callback = self._callback
            self._callback = callback
            return old_callback
        else:
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
        # self.treeView.setAlternatingRowColors(True)

        # try:
        #     self.root.header().resizeSection(0, 200)
        # except Exception as e:
        #     print(e)

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

    def closeEvent(self, event):
        self.mpfmon.write_local_settings()
        event.accept()
        self.mpfmon.check_if_quit()






class DeviceDelegate(QStyledItemDelegate):
    def __init__(self):
        self.size = None
        super().__init__()

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
            self.size = QSize(len(text) * 10, 20)

        painter.restore()

    def sizeHint(self, QStyleOptionViewItem, QModelIndex):
        if self.size:
            return self.size
        else:
            # Calling super() here seems to result in a segfault on close sometimes.
            # return super().sizeHint(QStyleOptionViewItem, QModelIndex)
            return QSize(80, 20)


class DeviceWindow(QWidget):

    def __init__(self, mpfmon):
        self.mpfmon = mpfmon
        super().__init__()
        self.ui = None
        self.model = None
        self.draw_ui()
        self.attach_model()
        self.attach_signals()

        self.log = logging.getLogger('Core')

        self.already_hidden = False
        self.added_index = 0

        self.device_states = dict()
        self.device_type_widgets = dict()

        self.sort_devices_by = DeviceSort.DEFAULT

    def draw_ui(self):
        # Load ui file from ./ui/
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "searchable_tree.ui")
        self.ui = uic.loadUi(ui_path, self)

        self.ui.setWindowTitle('Devices')

        self.ui.move(self.mpfmon.local_settings.value('windows/devices/pos',
                                            QPoint(200, 200)))
        self.ui.resize(self.mpfmon.local_settings.value('windows/devices/size',
                                              QSize(300, 600)))

        # Disable option "Sort", select first item.
        # TODO: Store and load selected sort index to local_settings
        self.ui.sortComboBox.model().item(0).setEnabled(False)
        self.ui.sortComboBox.setCurrentIndex(1)
        self.ui.treeView.setAlternatingRowColors(True)

    def attach_signals(self):
        assert (self.ui is not None)
        self.ui.treeView.expanded.connect(self.resize_columns_to_content)
        self.ui.treeView.collapsed.connect(self.resize_columns_to_content)
        # self.ui.filterLineEdit.textChanged.connect(self.filter_text)
        self.ui.sortComboBox.currentIndexChanged.connect(self.change_sort)

    def attach_model(self):
        assert (self.ui is not None)
        self.treeview = self.ui.treeView
        self.model = DeviceTreeModel(self)
        self.rootNode = self.model.root
        self.treeview.setDragDropMode(QAbstractItemView.DragOnly)
        self.treeview.setItemDelegateForColumn(1, DeviceDelegate())
        self.treeview.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.treeview.header().setStretchLastSection(False)
        self.treeview.setModel(self.model)

    def resize_columns_to_content(self):
        self.ui.treeView.resizeColumnToContents(0)
        self.ui.treeView.resizeColumnToContents(1)

    def process_device_update(self, name, state, changes, type):
        self.log.debug("Device Update: {}.{}: {}".format(type, name, state))

        if type not in self.device_states:
            self.device_states[type] = dict()
            node = DeviceNode(type, "", "", self.rootNode)
            self.device_type_widgets[type] = node
            self.model.insertRow(0, QModelIndex())
            self.rootNode.sortChildren(sort=self.sort_devices_by)

        if name not in self.device_states[type]:

            node = DeviceNode(name, "", "", self.device_type_widgets[type])
            self.device_states[type][name] = node
            self.device_type_widgets[type].sortChildren(sort=self.sort_devices_by)

            self.mpfmon.pf.create_widget_from_config(node, type, name)

        self.device_states[type][name].setData(state)
        self.model.setData(self.model.index(0, 0, QModelIndex()), None)

    def filter_text(self, string):
        wc_string = "*" + str(string) + "*"
        self.filtered_model.setFilterWildcard(wc_string)
        self.ui.treeView.resizeColumnToContents(0)
        self.ui.treeView.resizeColumnToContents(1)

    def change_sort(self, index=1):
        self.model.layoutAboutToBeChanged.emit()

        self.sort_devices_by = DeviceSort(index)
        self.rootNode.sortChildren(sort=self.sort_devices_by)
        for type in self.device_type_widgets:
            self.device_type_widgets[type].sortChildren(sort=self.sort_devices_by)

        self.model.layoutChanged.emit()
        self.model.refreshData()

    def closeEvent(self, event):
        super().closeEvent()
        self.mpfmon.write_local_settings()
        event.accept()
        self.mpfmon.check_if_quit()

