import unittest
import threading
import os
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from mpfmonitor.core.mpfmon import *


"""class InitMPFMon(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        app = QApplication(sys.argv)
        machine_path = os.path.join(os.getcwd(), "machine_files")
        self.mpfmon_sut = MainWindow(app, machine_path, None, testing=True)
        QTest.qWait(5000)

    def test_case(self):
        self.assertEqual(True, True)

"""

if __name__ == '__main__':
    unittest.main()
