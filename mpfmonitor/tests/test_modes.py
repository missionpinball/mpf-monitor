import unittest
from unittest import TestCase
import sys

from mpfmonitor.core.modes import *
from unittest.mock import MagicMock


class TestableModeNoGUI(ModeWindow):
    def __init__(self, mpfmon_mock=None):
        if mpfmon_mock is not None:
            self.mpfmon = mpfmon_mock

        self.ui = None
        self.model = None


class TestModeWindowFunctions(unittest.TestCase):

    def setUp(self):
        self.mode_window = TestableModeNoGUI()

        self.mode_window.ui = MagicMock()
        self.mode_window.model = MagicMock()
        self.mode_window.filtered_model = MagicMock()

    def test_process_mode_update(self):

        modes_in = [
            ["mode1", 100],
            ["mode2", 1000],
            ["mode3", 10000]
        ]

        self.mode_window.process_mode_update(running_modes=modes_in)

        self.mode_window.model.clear.assert_called_once()

        # for mode in modes_in:
        #     mode_name = QStandardItem(mode[0])
        #     mode_priority = QStandardItem(str(mode[1]))
        #     mode_priority_padded = QStandardItem(str(mode[1]).zfill(10))
        #
        #     self.mode_window.model.insertRow.assert_called_with(0, [mode_name, mode_priority, mode_priority_padded])

        # For now, just test it's called as many times as there are modes.
        self.assertEqual(self.mode_window.model.insertRow.call_count, len(modes_in))

    def test_filter_text(self):
        string_in = "filter_string_test"
        expected_string_out = "*filter_string_test*"

        self.mode_window.filter_text(string=string_in)

        self.mode_window.filtered_model.setFilterWildcard.assert_called_once_with(expected_string_out)

    def test_change_sort_default(self):
        self.mode_window.change_sort()
        self.mode_window.filtered_model.sort.assert_called_once_with(2, Qt.SortOrder.DescendingOrder)

    def test_change_sort_time_down(self):
        self.mode_window.change_sort(1)
        self.mode_window.filtered_model.sort.assert_called_once_with(2, Qt.SortOrder.DescendingOrder)

    def test_change_sort_time_up(self):
        self.mode_window.change_sort(2)
        self.mode_window.filtered_model.sort.assert_called_once_with(2, Qt.SortOrder.AscendingOrder)

    def test_change_sort_name_up(self):
        self.mode_window.change_sort(3)
        self.mode_window.filtered_model.sort.assert_called_once_with(0, Qt.SortOrder.AscendingOrder)

    def test_change_sort_name_down(self):
        self.mode_window.change_sort(4)
        self.mode_window.filtered_model.sort.assert_called_once_with(0, Qt.SortOrder.DescendingOrder)


app = QApplication(sys.argv)


class TestModeWindowGUI(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        mock_mpfmon = MagicMock()
        mock_mpfmon.local_settings.value.side_effect = [QPoint(1100, 200), QSize(300, 250)]

        self.mode_window = ModeWindow(mock_mpfmon)

        self.mock_event_kwargs = MagicMock()
        self.mock_event_kwargs.__str__ = MagicMock(return_value='{args}')
        self.mock_event_kwargs.pop.return_value(False)

    def test_model(self):
        self.assertIsNotNone(self.mode_window.model)

    def test_empty_table(self):
        # Reset table model
        self.mode_window.attach_model()

        # Check it's empty
        self.assertEqual(self.mode_window.model.rowCount(), 0)
        self.assertEqual(self.mode_window.filtered_model.rowCount(), 0)

    def test_add_to_table(self):
        # Reset table model
        self.mode_window.attach_model()
        self.assertEqual(self.mode_window.filtered_model.rowCount(), 0)

        modes_in = [
            ["mode1", 100],
            ["mode2", 1000],
            ["mode3", 10000]
        ]

        self.mode_window.process_mode_update(running_modes=modes_in)

        # Check table has 3 rows
        self.assertEqual(self.mode_window.filtered_model.rowCount(), 3)


    def test_sort(self):
        # Reset table model
        self.mode_window.attach_model()
        self.assertEqual(self.mode_window.filtered_model.rowCount(), 0)

        modes_in = [
            ["mode1", 100],
            ["mode2", 1000],
            ["mode3", 10000]
        ]

        self.mode_window.process_mode_update(running_modes=modes_in)

        # Default is Received up
        top_row_text = self.mode_window.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, modes_in[-1][0])

        # Sort Received up
        self.mode_window.ui.sortComboBox.setCurrentIndex(1)
        top_row_text = self.mode_window.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, modes_in[-1][0])

        # Sort Received down
        self.mode_window.ui.sortComboBox.setCurrentIndex(2)
        top_row_text = self.mode_window.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, modes_in[0][0])

        # Sort Name up
        self.mode_window.ui.sortComboBox.setCurrentIndex(3)
        top_row_text = self.mode_window.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, modes_in[0][0])

        # Sort Name down
        self.mode_window.ui.sortComboBox.setCurrentIndex(4)
        top_row_text = self.mode_window.filtered_model.index(0, 0).data()
        self.assertEqual(top_row_text, modes_in[-1][0])

    def test_filter(self):
        # Reset table model
        self.mode_window.attach_model()
        self.assertEqual(self.mode_window.filtered_model.rowCount(), 0)

        modes_in = [
            ["mode1", 100],
            ["mode32", 1000],
            ["mode3", 10000]
        ]

        self.mode_window.process_mode_update(running_modes=modes_in)

        # Make sure filter is empty and check none are filtered
        self.mode_window.ui.filterLineEdit.setText("")
        self.assertEqual(self.mode_window.filtered_model.rowCount(), len(modes_in))

        # Set the filter to a unique string and check it returns 1 match
        self.mode_window.ui.filterLineEdit.setText(modes_in[0][0])
        self.assertEqual(self.mode_window.filtered_model.rowCount(), 1)

        # Set the filter to a non-unique string and check it returns 2 matches
        self.mode_window.ui.filterLineEdit.setText(modes_in[2][0])
        self.assertEqual(self.mode_window.filtered_model.rowCount(), 2)


if __name__ == '__main__':
    unittest.main()
