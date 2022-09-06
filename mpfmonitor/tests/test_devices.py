import unittest
import threading
import sys
from PyQt6.QtTest import QTest
from PyQt6 import QtCore, QtGui, QtWidgets
from unittest.mock import MagicMock, patch, NonCallableMock
from mpfmonitor.core.devices import *


class TestableDeviceWindowNoGUI(DeviceWindow):
    def __init__(self, mpfmon_mock=None, logger=False):
        if mpfmon_mock is not None:
            self.mpfmon = mpfmon_mock

        if logger:
            self.log = logging.getLogger('Core')

        self.ui = None
        self.model = None

        self.device_states = dict()
        self.device_type_widgets = dict()
        self._debug_enabled = False

class TestDeviceWindowFunctions(unittest.TestCase):
    def setUp(self):
        self.device_window = TestableDeviceWindowNoGUI()
        self.device_window.ui = MagicMock()
        self.device_window.model = MagicMock()
        self.device_window.filtered_model = MagicMock()

    @patch('mpfmonitor.core.devices.QStandardItemModel', autospec=True)
    @patch('mpfmonitor.core.devices.QSortFilterProxyModel', autospec=True)
    def test_attach_model(self, mock_standard_item, mock_proxy_item):
        self.device_window.attach_model()

        self.device_window.model.setHorizontalHeaderLabels.assert_called_once()
        self.device_window.filtered_model.setSourceModel.assert_called_once()
        self.device_window.ui.treeView.setModel.assert_called_once()

    @patch('mpfmonitor.core.devices.QStandardItemModel', autospec=True)
    @patch('mpfmonitor.core.devices.DeviceNode', autospec=True)
    def test_process_device_update(self, node, q_item):
        self.device_window.log = MagicMock()
        self.device_window.mpfmon = MagicMock()

        name = "switch1"
        state =  {'state': 0, 'recycle_jitter_count': 0}
        changes = False
        type = "switch"

        self.device_window.process_device_update(name, state, changes, type)

        self.assertTrue(isinstance(self.device_window.device_states[type], dict))

        self.device_window.model.appendRow.assert_called_once()

        node().setName.assert_called_once_with(name)
        node().setData.assert_called_with(state)
        node().setType.assert_called_once_with(type)

        # self.device_window.device_type_widgets[type].appendRow.assert_called_once_with(node.get_row())

        self.device_window.mpfmon.pf.create_widget_from_config.assert_called_once_with(node(), type, name)

        self.device_window.device_states[type][name].setData.assert_called_with(state)


    def test_filter_text(self):
        string_in = "filter_string_test"
        expected_string_out = "*filter_string_test*"

        self.device_window.filter_text(string=string_in)

        self.device_window.filtered_model.setFilterWildcard.assert_called_once_with(expected_string_out)

    def test_change_sort_default(self):
        self.device_window.change_sort()
        self.device_window.filtered_model.sort.assert_called_once_with(2, Qt.SortOrder.AscendingOrder)

    def test_change_sort_time_down(self):
        self.device_window.change_sort(1)
        self.device_window.filtered_model.sort.assert_called_once_with(2, Qt.SortOrder.AscendingOrder)

    def test_change_sort_time_up(self):
        self.device_window.change_sort(2)
        self.device_window.filtered_model.sort.assert_called_once_with(2, Qt.SortOrder.DescendingOrder)

    def test_change_sort_name_up(self):
        self.device_window.change_sort(3)
        self.device_window.filtered_model.sort.assert_called_once_with(0, Qt.SortOrder.AscendingOrder)

    def test_change_sort_name_down(self):
        self.device_window.change_sort(4)
        self.device_window.filtered_model.sort.assert_called_once_with(0, Qt.SortOrder.DescendingOrder)



if __name__ == '__main__':
    unittest.main()
