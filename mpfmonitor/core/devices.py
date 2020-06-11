import logging

# will change these to specific imports once code is more final
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

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
        self.treeView.setAlternatingRowColors(True)

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