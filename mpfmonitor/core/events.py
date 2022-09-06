from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6 import uic

import os


class EventWindow(QWidget):

    def __init__(self, mpfmon):
        self.mpfmon = mpfmon
        self.filtered_model = None
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

        self.ui.setWindowTitle('Events')

        self.ui.move(self.mpfmon.local_settings.value('windows/events/pos',
                                                   QPoint(500, 200)))
        self.ui.resize(self.mpfmon.local_settings.value('windows/events/size',
                                                     QSize(300, 600)))

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

        self.model.setHeaderData(0, Qt.Orientation.Horizontal, "Event")
        self.model.setHeaderData(1, Qt.Orientation.Horizontal, "Data")
        # self.model.setHeaderData(2, Qt.Orientation.Horizontal, "Time")

        self.filtered_model = QSortFilterProxyModel(self)
        self.filtered_model.setSourceModel(self.model)
        self.filtered_model.setFilterKeyColumn(0)
        self.filtered_model.setDynamicSortFilter(True)

        self.change_sort()  # Default sort

        self.ui.tableView.setModel(self.filtered_model)
        self.ui.tableView.setColumnHidden(2, True)
        self.rootNode = self.model.invisibleRootItem()

    def add_event_to_model(self, event_name, event_type, event_callback,
                             event_kwargs, registered_handlers):
        """Add an event."""
        assert(self.model is not None)
        # remove _from_bcp arg
        event_kwargs.pop('_from_bcp', False)

        name = QStandardItem(event_name)
        kwargs = QStandardItem(str(event_kwargs))
        time_added = QStandardItem(str(self.added_index).zfill(10))
        self.added_index += 1
        self.model.insertRow(0, [name, kwargs, time_added])

    def update_events(self):
        """Update view."""
        self.ui.tableView.resizeColumnToContents(0)
        self.ui.tableView.resizeColumnToContents(1)

        if not self.already_hidden:
            self.ui.tableView.setColumnHidden(2, True)
            self.already_hidden = True

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
