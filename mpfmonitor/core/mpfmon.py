import logging
import queue
import sys
import os
import time

# will change these to specific imports once code is more final
from collections import deque

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

import ruamel.yaml as yaml



from mpfmonitor.core.devices import *
from mpfmonitor.core.playfield import *
from mpfmonitor.core.bcp_client import BCPClient
from mpfmonitor.core.events import EventWindow
from mpfmonitor.core.modes import ModeWindow
from mpfmonitor.core.inspector import InspectorWindow
from mpfmonitor.core.variables import VariableWindow


class MPFMonitor():
    def __init__(self, app, machine_path, thread_stopper, config_file, parent=None, testing=False):

        # super().__init__(parent)

        self.log = logging.getLogger('Core')

        sys.excepthook = self.except_hook

        self.bcp_client_connected = False
        self.receive_queue = queue.Queue()
        self.sending_queue = queue.Queue()
        self.crash_queue = queue.Queue()
        self.thread_stopper = thread_stopper
        self.machine_path = machine_path
        self.app = app
        self.config = None
        self.layout = None
        self.config_file = os.path.join(self.machine_path, "monitor",
                                        config_file)
        self.playfield_image_file = os.path.join(self.machine_path,
                                                 "monitor", "playfield.jpg")

        self.local_settings = QSettings("mpf", "mpf-monitor")

        self.load_config()

        self.device_window = DeviceWindow(self)

        self.pf_device_size = self.config.get("device_size", .02)
        if not isinstance(self.pf_device_size, float):  # Protect against corrupted device size
            self.pf_device_size = .02

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, 'localhost', 5051,
                             simulate=testing, cache=False)

        self.tick_timer = QTimer(self.device_window)
        self.tick_timer.setInterval(20)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start()

        self.toggle_pf_window_action = QAction('&Playfield', self.device_window,
                                        statusTip='Show the playfield window',
                                        triggered=self.toggle_pf_window)
        self.toggle_pf_window_action.setCheckable(True)

        self.toggle_device_window_action = QAction('&Devices', self.device_window,
                                        statusTip='Show the device window',
                                        triggered=self.toggle_device_window)
        self.toggle_device_window_action.setCheckable(True)

        self.toggle_event_window_action = QAction('&Events', self.device_window,
                                        statusTip='Show the events window',
                                        triggered=self.toggle_event_window)
        self.toggle_event_window_action.setCheckable(True)

        self.toggle_mode_window_action = QAction('&Modes', self.device_window,
                                        statusTip='Show the mode window',
                                        triggered=self.toggle_mode_window)
        self.toggle_mode_window_action.setCheckable(True)

        self.scene = QGraphicsScene()

        self.pf = PfPixmapItem(QPixmap(self.playfield_image_file), self)
        self.scene.addItem(self.pf)

        self.view = PfView(self.scene, self)

        self.view.move(self.local_settings.value('windows/pf/pos',
                                                 QPoint(800, 200)))
        self.view.resize(self.local_settings.value('windows/pf/size',
                                                   QSize(300, 600)))

        self.event_window = EventWindow(self)

        self.variable_window = VariableWindow(self)
        self.variable_window.show()

        self.mode_window = ModeWindow(self)

        if self.get_local_settings_bool('windows/pf/visible'):
            self.toggle_pf_window()

        if self.get_local_settings_bool('windows/events/visible'):
            self.toggle_event_window()

        if self.get_local_settings_bool('windows/devices/visible'):
            self.toggle_device_window()

        if self.get_local_settings_bool('windows/modes/visible'):
            self.toggle_mode_window()

        self.exit_on_close = False

        if self.get_local_settings_bool('settings/exit-on-close'):
            self.toggle_exit_on_close()

        self.inspector_enabled = False

        self.inspector_window = InspectorWindow(self)
        self.inspector_window.show()
        self.inspector_window.register_last_selected_cb()

        self.inspector_window.register_set_inspector_val_cb(self.set_inspector_mode)

        self.menu_bar = QMenuBar()
        self.view_menu = self.menu_bar.addMenu("&View")
        self.view_menu.addAction(self.toggle_pf_window_action)
        self.view_menu.addAction(self.toggle_device_window_action)
        self.view_menu.addAction(self.toggle_event_window_action)

    def toggle_pf_window(self):
        if self.view.isVisible():
            self.view.hide()
            self.toggle_pf_window_action.setChecked(False)
        else:
            self.view.show()
            self.toggle_pf_window_action.setChecked(True)

    def toggle_device_window(self):
        if self.device_window.isVisible():
            self.device_window.hide()
            self.toggle_device_window_action.setChecked(False)
        else:
            self.device_window.show()
            self.toggle_device_window_action.setChecked(True)

    def toggle_event_window(self):
        if self.event_window.isVisible():
            self.event_window.hide()
            self.toggle_event_window_action.setChecked(False)
        else:
            self.event_window.show()
            self.toggle_event_window_action.setChecked(True)

    def toggle_mode_window(self):
        if self.mode_window.isVisible():
            self.mode_window.hide()
            self.toggle_mode_window_action.setChecked(False)
        else:
            self.mode_window.show()
            self.toggle_mode_window_action.setChecked(True)

    def toggle_exit_on_close(self):
        if self.exit_on_close:
            self.exit_on_close = False
        else:
            self.exit_on_close = True

    def toggle_sort_by_time(self):
        if self.sort_by_time:
            self.sort_by_time = False
        else:
            self.sort_by_time = True

    def except_hook(self, cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)
        self.app.exit()

    def reset_connection(self):
        self.start_time = 0
        self.event_window.model.clear()
        self.mode_window.model.clear()

    def eventFilter(self, source, event):
        try:
            if source is self.playfield and event.type() == QEvent.Resize:
                self.playfield.setPixmap(self.playfield_image.scaled(
                    self.playfield.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                self.pf.invalidate_size()
        except AttributeError:
            pass

        return super().eventFilter(source, event)

    def tick(self):
        """
        Called every 20 mSec
        Check the queue to see if BCP has any messages to process.
        If any devices have updated, refresh the model data.
        """
        # get the complete queue
        with self.receive_queue.mutex:
            local_queue = self.receive_queue.queue
            self.receive_queue.queue = deque()

        added_events = False
        for cmd, kwargs in local_queue:
            if cmd == 'device':
                self.device_window.process_device_update(**kwargs)
            elif cmd == 'monitored_event':
                self.event_window.add_event_to_model(**kwargs)
                added_events = True
            elif cmd in ('mode_start', 'mode_stop', 'mode_list'):
                if 'running_modes' not in kwargs:
                    # ignore mode_start/stop on newer MPF versions
                    continue
                self.mode_window.process_mode_update(kwargs['running_modes'])
            elif cmd == 'reset':
                self.reset_connection()
                self.bcp.send("reset_complete")
            elif cmd == 'player_variable':
                self.variable_window.update_variable("player", kwargs["name"], kwargs["value"])
            elif cmd == 'machine_variable':
                self.variable_window.update_variable("machine", kwargs["name"], kwargs["value"])

        if added_events:
            self.event_window.update_events()

    def about(self):
        QMessageBox.about(self, "About MPF Monitor",
                "This is the MPF Monitor")

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
                self.config = dict()

    def save_config(self):
        self.log.debug("Saving config to disk")
        with open(self.config_file, 'w') as f:
            f.write(yaml.dump(self.config, default_flow_style=False))

    def closeEvent(self, event):
        self.write_local_settings()
        event.accept()
        self.check_if_quit()

    def check_if_quit(self):
        if self.exit_on_close:
            self.log.info("Quitting due to quit on close")
            QCoreApplication.exit(0)

    def write_window_settings(self, window_name, window):
        settings = {
            'pos': window.pos(),
            'size': window.size(),
            'visible': window.isVisible()
        }
        for line in settings.keys():
            setting_name = 'windows/' + window_name + '/' + line
            self.local_settings.setValue(setting_name, settings.get(line))

    def get_local_settings_bool(self, setting):
        return "true" == str(self.local_settings.value(setting, False)).lower()

    def write_local_settings(self):

        monitor_windows = {
            'devices': self.device_window,
            'pf': self.view,
            'modes': self.mode_window,
            'events': self.event_window,
            'inspector': self.inspector_window
        }

        for window in monitor_windows.keys():
            self.write_window_settings(window, monitor_windows.get(window))

        self.local_settings.setValue('settings/exit-on-close', self.exit_on_close)

        self.local_settings.sync()

    def set_inspector_mode(self, enabled=False):
        self.inspector_enabled = enabled
        self.view.set_inspector_mode_title(inspect=enabled)





def run(machine_path, thread_stopper, config_file, testing=False):

    app = QApplication(sys.argv)
    MPFMonitor(app, machine_path, thread_stopper, config_file, testing=testing)
    app.exec()
