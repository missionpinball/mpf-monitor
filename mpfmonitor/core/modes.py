from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6 import uic

import os
import time

class ModeWindow(QWidget):

    def __init__(self, mpfmon):
        self.mpfmon = mpfmon
        super().__init__()
        self.ui = None
        self.model = None
        self.draw_ui()
        self.attach_model()
        self.attach_signals()

        self.already_hidden = False
        self.added_index = 0

    def draw_ui(self):
        # Load ui file from ./ui/
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "searchable_table.ui")
        self.ui = uic.loadUi(ui_path, self)

        self.ui.setWindowTitle('Running Modes')

        self.ui.move(self.mpfmon.local_settings.value('windows/modes/pos',
                                                   QPoint(1100, 200)))
        self.ui.resize(self.mpfmon.local_settings.value('windows/modes/size',
                                                     QSize(300, 240)))

        # Fix sort combobox verbiage
        self.ui.sortComboBox.setItemText(1, "Priority ▴")
        self.ui.sortComboBox.setItemText(2, "Priority ▾")


        # Disable option "Sort", select first item.
        # TODO: Store and load selected sort index to local_settings
        self.ui.sortComboBox.model().item(0).setEnabled(False)
        self.ui.sortComboBox.setCurrentIndex(1)

    def attach_signals(self):
        assert (self.ui is not None)
        self.ui.filterLineEdit.textChanged.connect(self.filter_text)
        self.ui.sortComboBox.currentIndexChanged.connect(self.change_sort)

    def attach_model(self):
        self.model = QStandardItemModel(0, 2)

        self.model.setHeaderData(0, Qt.Orientation.Horizontal, "Mode")
        self.model.setHeaderData(1, Qt.Orientation.Horizontal, "Priority")
        # self.model.setHeaderData(2, Qt.Orientation.Horizontal, "Time")

        self.filtered_model = QSortFilterProxyModel(self)
        self.filtered_model.setSourceModel(self.model)
        self.filtered_model.setFilterKeyColumn(0)
        self.filtered_model.setDynamicSortFilter(True)

        self.change_sort()  # Default sort

        self.ui.tableView.setModel(self.filtered_model)
        self.ui.tableView.setColumnHidden(2, True)
        self.rootNode = self.model.invisibleRootItem()

    def process_mode_update(self, running_modes):
        """Update mode list."""
        self.model.clear()

        for mode in running_modes:
            mode_name = QStandardItem(mode[0])
            mode_priority = QStandardItem(str(mode[1]))
            mode_priority_padded = QStandardItem(str(mode[1]).zfill(10))
            self.model.insertRow(0, [mode_name, mode_priority, mode_priority_padded])

        # Reset the headers for the tree. For some reason clear() wipes these too.
        self.model.setHeaderData(0, Qt.Orientation.Horizontal, "Mode")
        self.model.setHeaderData(1, Qt.Orientation.Horizontal, "Priority")

        self.ui.tableView.setColumnHidden(2, True)

    def filter_text(self, string):
        wc_string = "*" + str(string) + "*"
        self.filtered_model.setFilterWildcard(wc_string)
        self.ui.tableView.resizeColumnToContents(0)
        self.ui.tableView.resizeColumnToContents(1)

    def change_sort(self, index=1):
        # This is a bit sloppy and probably should be reworked.
        if index == 1:  # Received up
            self.filtered_model.sort(2, Qt.SortOrder.DescendingOrder)
        elif index == 2:  # Received down
            self.filtered_model.sort(2, Qt.SortOrder.AscendingOrder)
        elif index == 3:  # Name up
            self.filtered_model.sort(0, Qt.SortOrder.AscendingOrder)
        elif index == 4:  # Name down
            self.filtered_model.sort(0, Qt.SortOrder.DescendingOrder)

    def closeEvent(self, event):
        self.mpfmon.write_local_settings()
        event.accept()
        self.mpfmon.check_if_quit()
