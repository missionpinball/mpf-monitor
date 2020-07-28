import logging
import time
import os

# will change these to specific imports once code is more final
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import uic

from enum import Enum


class DeviceNode(object):

    def __init__(self):
        self._callback = None
        self._name = ""
        self._data = {}
        self._type = ""

        self.q_name = QStandardItem()
        self.q_state = QStandardItem()
        self.sub_properties = {}
        self.sub_properties_appended = False

        self.q_time_added = QStandardItem()
        self.q_time_added.setData(time.perf_counter(), Qt.DisplayRole)

    def setName(self, name):
        self._name = name

    def setData(self, data):
        if self._callback:
            self._callback()
        self._data = data
        self.get_row()


    def setType(self, type):
        self._type = type

    def get_row(self):
        self.q_name.setData(str(self._name), Qt.DisplayRole)

        self.q_state.setData("", Qt.DisplayRole)

        self.q_name.setDragEnabled(True)

        if isinstance(self._data, dict):
            state_str = str(list(self._data.values())[0])
            if len(self._data) > 1:
                state_str = state_str + " {…}"
            self.q_state.setData(state_str, Qt.DisplayRole)

            for row in self._data:
                if not self.sub_properties_appended:
                    property = QStandardItem()
                    value = QStandardItem()

                    self.sub_properties.update({row: [property, value]})

                    self.q_name.appendRow(self.sub_properties.get(row))

                self.sub_properties.get(row)[0].setData(str(row), Qt.DisplayRole)
                self.sub_properties.get(row)[1].setData(str(self._data.get(row)), Qt.DisplayRole)

            self.sub_properties_appended = True

        self.row_data = [self.q_name, self.q_state, self.q_time_added]

        return self.row_data

    def data(self):
        self.q_state.emitDataChanged()
        return self._data

    def type(self):
        return self._type

    def set_change_callback(self, callback):
        if self._callback:
            # raise AssertionError("Can only have one callback")
            old_callback = self._callback
            self._callback = callback
            return old_callback
        else:
            self._callback = callback
            self.row_data[1].emitDataChanged()




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

        # src_index = index.model().mapToSource(index)
        # src_index_model = src_index.model()
        # print(index.data())
        # print(src_index_model.data())
        data = []
        try:
            data = index.model().itemFromIndex(index).data()
            # src_index = index.model().mapToSource(index)
            # data = index.model().data(src_index)
        except:
            pass


        num_circles = 1
        # return

        if index.column() == 0:
            return

        try:
            if 'color' in data:
                color = data['color']
                found = True
        except TypeError:
            return

        try:
            if 'brightness' in data:
                color = [data['brightness']]*3
                found = True
        except TypeError:
            return

        try:
            if 'state' in data:
                text = str(data['state'])
                found = True
        except TypeError:
            return

        try:
            if 'complete' in data:
                state = not data['complete']
                found = True
        except TypeError:
            return

        try:
            if 'enabled' in data:
                state = data['enabled']
                found = True
        except TypeError:
            return

        try:
            if 'balls' in data:
                balls = data['balls']
                found = True
        except TypeError:
            return

        try:
            if 'balls_locked' in data:
                balls = data['balls_locked']
                found = True
        except TypeError:
            return

        try:
            if 'num_balls_requested' in data:
                text += 'Requested: {} '.format(
                    data['num_balls_requested'])
                found = True
        except TypeError:
            return

        try:
            if 'unexpected_balls' in data:
                text += 'Unexpected: {} '.format(
                    data['unexpected_balls'])
                found = True
        except TypeError:
            return

        if not found:
            return

        text += " " + str(data)

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
        self.ui.filterLineEdit.textChanged.connect(self.filter_text)
        self.ui.sortComboBox.currentIndexChanged.connect(self.change_sort)

    def attach_model(self):
        assert (self.ui is not None)
        self.treeview = self.ui.treeView

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Device", "Data"])

        self.treeview.setDragDropMode(QAbstractItemView.DragOnly)
        # self.treeview.setItemDelegateForColumn(1, DeviceDelegate())
        self.treeview.header().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.filtered_model = QSortFilterProxyModel(self)
        self.filtered_model.setSourceModel(self.model)
        self.filtered_model.setRecursiveFilteringEnabled(True)
        self.filtered_model.setFilterCaseSensitivity(False)

        self.treeview.setModel(self.filtered_model)

    def resize_columns_to_content(self):
        self.ui.treeView.resizeColumnToContents(0)
        self.ui.treeView.resizeColumnToContents(1)

    def process_device_update(self, name, state, changes, type):
        self.log.debug("Device Update: {}.{}: {}".format(type, name, state))

        if type not in self.device_states:
            self.device_states[type] = dict()

            item = QStandardItem(type)
            self.device_type_widgets[type] = item

            self.model.appendRow([item, QStandardItem(), QStandardItem(str(time.perf_counter()))])

        if name not in self.device_states[type]:
            node = DeviceNode()
            node.setName(name)
            node.setData(state)
            node.setType(type)

            self.device_states[type][name] = node
            self.device_type_widgets[type].appendRow(node.get_row())

            self.mpfmon.pf.create_widget_from_config(node, type, name)

        self.device_states[type][name].setData(state)
        self.ui.treeView.setColumnHidden(2, True)

    def filter_text(self, string):
        wc_string = "*" + str(string) + "*"
        self.filtered_model.setFilterWildcard(wc_string)
        self.ui.treeView.resizeColumnToContents(0)
        self.ui.treeView.resizeColumnToContents(1)

    def change_sort(self, index=1):
        self.model.layoutAboutToBeChanged.emit()
        self.filtered_model.beginResetModel()

        # This is a bit sloppy and probably should be reworked.
        if index == 1:  # Received up
            self.filtered_model.sort(2, Qt.AscendingOrder)
        elif index == 2:  # Received down
            self.filtered_model.sort(2, Qt.DescendingOrder)
        elif index == 3:  # Name up
            self.filtered_model.sort(0, Qt.AscendingOrder)
        elif index == 4:  # Name down
            self.filtered_model.sort(0, Qt.DescendingOrder)

        self.filtered_model.endResetModel()
        self.model.layoutChanged.emit()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.mpfmon.write_local_settings()
        event.accept()
        self.mpfmon.check_if_quit()

