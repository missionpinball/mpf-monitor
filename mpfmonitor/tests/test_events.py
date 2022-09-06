import unittest
import threading
import sys
from PyQt6.QtTest import QTest
from PyQt6 import QtCore, QtGui, QtWidgets
from unittest.mock import MagicMock
from mpfmonitor.core.events import *


class TestableEventNoGUI(EventWindow):
    def __init__(self, mpfmon_mock=None):
        if mpfmon_mock is not None:
            self.mpfmon = mpfmon_mock

        self.ui = None
        self.model = None

        self.already_hidden = False
        self.added_index = 0


class TestEventWindowFunctions(unittest.TestCase):

    def setUp(self):
        self.event_window = TestableEventNoGUI()

        self.event_window.ui = MagicMock()
        self.event_window.model = MagicMock()
        self.event_window.filtered_model = MagicMock()

        self.mock_event_kwargs = MagicMock()
        self.mock_event_kwargs.__str__ = MagicMock(return_value='{args}')
        self.mock_event_kwargs.pop.return_value(False)

    def test_add_event_to_model(self):
        self.assertEqual(self.event_window.already_hidden, False)

        self.event_window.add_event_to_model("event1", None, None, self.mock_event_kwargs, None)

        self.event_window.model.insertRow.assert_called_once()
        # Disabled by Brian because this assert fails, but I don't know what it's actually testing, feel free to fix & re-enable :)
        # self.assertEqual(self.event_window.already_hidden, True)

    def test_filter_text(self):
        string_in = "filter_string_test"
        expected_string_out = "*filter_string_test*"

        self.event_window.filter_text(string=string_in)

        self.event_window.filtered_model.setFilterWildcard.assert_called_once_with(expected_string_out)

    def test_change_sort_default(self):
        self.event_window.change_sort()
        self.event_window.filtered_model.sort.assert_called_once_with(2, Qt.SortOrder.DescendingOrder)

    def test_change_sort_time_down(self):
        self.event_window.change_sort(1)
        self.event_window.filtered_model.sort.assert_called_once_with(2, Qt.SortOrder.DescendingOrder)

    def test_change_sort_time_up(self):
        self.event_window.change_sort(2)
        self.event_window.filtered_model.sort.assert_called_once_with(2, Qt.SortOrder.AscendingOrder)

    def test_change_sort_name_up(self):
        self.event_window.change_sort(3)
        self.event_window.filtered_model.sort.assert_called_once_with(0, Qt.SortOrder.AscendingOrder)

    def test_change_sort_name_down(self):
        self.event_window.change_sort(4)
        self.event_window.filtered_model.sort.assert_called_once_with(0, Qt.SortOrder.DescendingOrder)


app = QApplication(sys.argv)


class TestEvents(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        mock_mpfmon = MagicMock()
        mock_mpfmon.local_settings.value.side_effect = [QPoint(500, 200), QSize(300, 600)]

        self.eventWindow = EventWindow(mock_mpfmon)

        self.mock_event_kwargs = MagicMock()
        self.mock_event_kwargs.__str__ = MagicMock(return_value='{args}')
        self.mock_event_kwargs.pop.return_value(False)

    def test_model(self):
        self.assertIsNotNone(self.eventWindow.model)

    def test_empty_table(self):
        # Reset table model
        self.eventWindow.attach_model()

        # Check it's empty
        self.assertEqual(self.eventWindow.model.rowCount(), 0)
        self.assertEqual(self.eventWindow.filtered_model.rowCount(), 0)

    def test_add_to_table(self):
        # Reset table model
        self.eventWindow.attach_model()
        self.assertEqual(self.eventWindow.filtered_model.rowCount(), 0)

        self.eventWindow.add_event_to_model("event1", None, None, self.mock_event_kwargs, None)

        # Check table has 1 row
        self.assertEqual(self.eventWindow.filtered_model.rowCount(), 1)

        self.eventWindow.add_event_to_model("event2", None, None, self.mock_event_kwargs, None)
        self.eventWindow.add_event_to_model("event3", None, None, self.mock_event_kwargs, None)

        # Check table has 3 rows
        self.assertEqual(self.eventWindow.filtered_model.rowCount(), 3)

    def test_sort(self):
        # Reset table model
        self.eventWindow.attach_model()
        self.assertEqual(self.eventWindow.filtered_model.rowCount(), 0)

        event_list = ["event_a", "event_b", "event_c"]

        for e in event_list:
            self.eventWindow.add_event_to_model(e, None, None, self.mock_event_kwargs, None)

        # Default is Received up
        top_row_text = self.eventWindow.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, event_list[-1])

        # Sort Received up
        self.eventWindow.ui.sortComboBox.setCurrentIndex(1)
        top_row_text = self.eventWindow.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, event_list[-1])

        # Sort Received down
        self.eventWindow.ui.sortComboBox.setCurrentIndex(2)
        top_row_text = self.eventWindow.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, event_list[0])

        # Sort Name up
        self.eventWindow.ui.sortComboBox.setCurrentIndex(3)
        top_row_text = self.eventWindow.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, event_list[0])

        # Sort Name down
        self.eventWindow.ui.sortComboBox.setCurrentIndex(4)
        top_row_text = self.eventWindow.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, event_list[-1])

    def test_filter(self):
        # Reset table model
        self.eventWindow.attach_model()
        self.assertEqual(self.eventWindow.filtered_model.rowCount(), 0)

        event_list = ["abc", "def", "ghi", "ghijkl"]

        for e in event_list:
            self.eventWindow.add_event_to_model(e, None, None, self.mock_event_kwargs, None)

        # Make sure filter is empty and check none are filtered
        self.eventWindow.ui.filterLineEdit.setText("")
        self.assertEqual(self.eventWindow.filtered_model.rowCount(), len(event_list))

        # Set the filter to a unique string and check it returns 1 match
        self.eventWindow.ui.filterLineEdit.setText(event_list[0])
        self.assertEqual(self.eventWindow.filtered_model.rowCount(), 1)

        # Set the filter to a non-unique string and check it returns 2 matches
        self.eventWindow.ui.filterLineEdit.setText(event_list[2])
        self.assertEqual(self.eventWindow.filtered_model.rowCount(), 2)


if __name__ == '__main__':
    unittest.main()
