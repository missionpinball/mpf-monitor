import logging
import time
import os

# will change these to specific imports once code is more final
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6 import uic

BRUSH_WHITE = QBrush(QColor(255, 255, 255), Qt.BrushStyle.SolidPattern)
BRUSH_GREEN = QBrush(QColor(0, 255, 0), Qt.BrushStyle.SolidPattern)
BRUSH_BLACK = QBrush(QColor(0, 0, 0), Qt.BrushStyle.SolidPattern)
BRUSH_DARK_PURPLE = QBrush(QColor(128, 0, 255), Qt.BrushStyle.SolidPattern)


class DeviceNode:

    __slots__ = ["_callback", "_name", "_data", "_type", "_brush", "q_name", "q_state", "sub_properties",
                 "sub_properties_appended", "q_time_added", "log"]

    def __init__(self):
        self._callback = None
        self._name = ""
        self._data = {}
        self._type = ""
        self._brush = BRUSH_BLACK

        self.q_name = QStandardItem()
        self.q_state = QStandardItem()
        self.sub_properties = {}
        self.sub_properties_appended = False

        self.q_time_added = QStandardItem()
        self.q_time_added.setData(time.perf_counter(), Qt.ItemDataRole.DisplayRole)

        self.q_name.setDragEnabled(True)
        self.q_state.setData("", Qt.ItemDataRole.DisplayRole)

        self.log = logging.getLogger('Device')

    def setName(self, name):
        self._name = name
        self.q_name.setData(str(self._name), Qt.ItemDataRole.DisplayRole)
        self.log = logging.getLogger('Device {}'.format(self._name))
        self.q_state.emitDataChanged()

    def setData(self, data):
        """Set data of device."""
        if data == self._data:
            # do nothing if data did not change
            return

        if not isinstance(data, dict):
            data = {}

        if self._callback:
            self._callback()

        self._data = data

        state_str = str(list(self._data.values())[0])
        if len(self._data) > 1:
            state_str = state_str + " {…}"
        self.q_state.setData(state_str, Qt.ItemDataRole.DisplayRole)

        for row in self._data:
            if not self.sub_properties_appended:
                q_property = QStandardItem()
                q_value = QStandardItem()
                self.sub_properties.update({row: [q_property, q_value]})
                self.q_name.appendRow(self.sub_properties.get(row))

            self.sub_properties.get(row)[0].setData(str(row), Qt.ItemDataRole.DisplayRole)
            self.sub_properties.get(row)[1].setData(str(self._data.get(row)), Qt.ItemDataRole.DisplayRole)

        self.sub_properties_appended = True
        self.q_state.emitDataChanged()
        self._brush = self._calculate_colored_brush()

    def setType(self, type):
        self._type = type
        self._brush = self._calculate_colored_brush()
        self.q_state.emitDataChanged()

    def get_row(self):
        return [self.q_name, self.q_state, self.q_time_added]

    def data(self):
        return self._data

    def type(self):
        return self._type

    def get_colored_brush(self) -> QBrush:
        """Return colored brush for device."""
        return self._brush

    def _calculate_color_gamma_correction(self, color):
        """Perform gamma correction.

        Feel free to fiddle with these constants until it feels right
        With gamma = 0.5 and constant a = 18, the top 54 values are lost,
        but the bottom 25% feels much more normal.
        """
        gamma = 0.5
        a = 18
        corrected = []

        for value in color:
            if value < 0 or value > 255:
                self.log.warning("Got value %s for brightness which outside the expected range", value)
                value = 0

            value = int(pow(value, gamma) * a)
            if value > 255:
                value = 255
            corrected.append(value)

        return corrected

    def _calculate_colored_brush(self):
        if self._type == 'light':
            color = self.data()['color']
            if color == [0, 0, 0]:
                # shortcut for black
                return BRUSH_BLACK
            color = self._calculate_color_gamma_correction(color)

        elif self._type == 'switch':
            state = self.data()['state']

            if state:
                return BRUSH_GREEN
            else:
                return BRUSH_BLACK

        elif self._type == 'diverter':
            state = self.data()['active']

            if state:
                return BRUSH_DARK_PURPLE
            else:
                return BRUSH_BLACK
        else:
            # Get first parameter and draw as white if it evaluates True
            state = bool(list(self.data().values())[0])
            if state:
                return BRUSH_WHITE
            else:
                return BRUSH_BLACK

        return QBrush(QColor(*color), Qt.BrushStyle.SolidPattern)

    def set_change_callback(self, callback):
        if self._callback:
            # raise AssertionError("Can only have one callback")
            old_callback = self._callback
            self._callback = callback
            return old_callback
        else:
            self._callback = callback
            self.q_state.emitDataChanged()


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

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(100, 100, 100), 1, Qt.PenStyle.SolidLine))

        if color:
            painter.setBrush(QBrush(QColor(*color), Qt.BrushStyle.SolidPattern))
        elif state is True:
            painter.setBrush(QBrush(QColor(0, 255, 0), Qt.BrushStyle.SolidPattern))
        elif state is False:
            painter.setBrush(QBrush(QColor(255, 255, 255), Qt.BrushStyle.SolidPattern))
        elif isinstance(balls, int):
            painter.setBrush(QBrush(QColor(0, 255, 0), Qt.BrushStyle.SolidPattern))
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

    __slots__ = ["mpfmn", "ui", "model", "log", "already_hidden", "added_index", "device_states",
                 "device_type_widgets", "_debug_enabled"]

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
        self._debug_enabled = self.log.isEnabledFor(logging.DEBUG)

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

        self.treeview.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        # self.treeview.setItemDelegateForColumn(1, DeviceDelegate())

        # Resizing to contents causes huge performance losses. Only resize when rows expanded or collapsed.
        # self.treeview.header().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.filtered_model = QSortFilterProxyModel(self)
        self.filtered_model.setSourceModel(self.model)
        self.filtered_model.setRecursiveFilteringEnabled(True)
        self.filtered_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.treeview.setModel(self.filtered_model)

    def resize_columns_to_content(self):
        self.ui.treeView.resizeColumnToContents(0)
        self.ui.treeView.resizeColumnToContents(1)

    def process_device_update(self, name, state, changes, type):
        del changes
        if self._debug_enabled:
            self.log.debug("Device Update: %s.%s: %s", type, name, state)

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
        else:
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
            self.filtered_model.sort(2, Qt.SortOrder.AscendingOrder)
        elif index == 2:  # Received down
            self.filtered_model.sort(2, Qt.SortOrder.DescendingOrder)
        elif index == 3:  # Name up
            self.filtered_model.sort(0, Qt.SortOrder.AscendingOrder)
        elif index == 4:  # Name down
            self.filtered_model.sort(0, Qt.SortOrder.DescendingOrder)

        self.filtered_model.endResetModel()
        self.model.layoutChanged.emit()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.mpfmon.write_local_settings()
        event.accept()
        self.mpfmon.check_if_quit()
