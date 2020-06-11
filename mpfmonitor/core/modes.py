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

class ModeWindow(QTreeView):

    def __init__(self, mpfmon):
        self.mpfmon = mpfmon
        super().__init__()

        self.setWindowTitle('Running Modes')
        self.model = QStandardItemModel(0, 2)

        self.model.setHeaderData(0, Qt.Horizontal, "Mode")
        self.model.setHeaderData(1, Qt.Horizontal, "Priority")

        self.setAlternatingRowColors(True)

        self.setModel(self.model)
        self.rootNode = self.model.invisibleRootItem()
        self.setSortingEnabled(True)

        self.move(self.mpfmon.local_settings.value('windows/modes/pos',
                                                   QPoint(1100, 200)))
        self.resize(self.mpfmon.local_settings.value('windows/modes/size',
                                                     QSize(300, 250)))

    def closeEvent(self, event):
        self.mpfmon.write_local_settings()
        event.accept()
        self.mpfmon.check_if_quit()
