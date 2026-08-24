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

from ruamel import yaml

from mpfmonitor.core.devices import *
from mpfmonitor.core.playfield import *
from mpfmonitor.core.bcp_client import BCPClient
from mpfmonitor.core.events import EventWindow
from mpfmonitor.core.modes import ModeWindow
from mpfmonitor.core.inspector import InspectorWindow
from mpfmonitor.core.variables import VariableWindow

def run(machine_path, thread_stopper, config_file, image_files, ip_addr="localhost", port="5051", testing=False):
    app = QApplication(sys.argv)
    MPFMonitor(app, machine_path, thread_stopper, config_file, image_files, ip_addr, port, testing=testing)
    app.exec()

class MPFMonitor():
    def __init__(self, app, machine_path, thread_stopper, config_file, image_files, ip_addr=None, port=None, parent=None, testing=False):

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
        self.mpf_ip_addr = ip_addr
        self.mpf_port = port
        self.hide_layer_lights = False
        self.hide_layer_others = False
        self.hide_layer_switches = False
        self.device_name_filter = ''

        self.config_file = os.path.join(self.machine_path, "monitor", config_file)
        self.settings_file = os.path.join(self.machine_path, "monitor", "settings.ini")

        resolved = [os.path.abspath(os.path.join(self.machine_path, "monitor", f)) for f in image_files]
        deduped = list(dict.fromkeys(resolved))
        deduped.sort(key=lambda path: os.path.basename(path).lower())
        self.image_files = deduped

        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        self.local_settings = QSettings(self.settings_file, QSettings.Format.IniFormat)

        self.load_config()

        self.device_window = DeviceWindow(self)

        self.pf_device_size = self.config.get("device_size", .02)
        if not isinstance(self.pf_device_size, float):  # Protect against corrupted device size
            self.pf_device_size = .02

        self.pf_device_alpha = self.config.get("device_alpha", 220)
        self.pf_device_outline = self.config.get("device_outline", 3)

        #Command line takes priority over settings file. If command line is None, then read the settings file.

        #if mpf_ip_address is not in the settings file, then localhost will be used
        if (self.mpf_ip_addr == None):
            self.mpf_ip_addr = self.local_settings.value("settings/mpf-ip-address", "localhost")

        #if mpf_port is not in the settings file, then 5051 will be used
        if (self.mpf_port == None):
            self.mpf_port = self.local_settings.value("settings/mpf-port", "5051")

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, self.mpf_ip_addr, self.mpf_port,
                             simulate=testing, cache=False)

        self.tick_timer = QTimer(self.device_window)
        self.tick_timer.setInterval(20)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start()

        self.toggle_pf_window_action = QAction('&Playfield', self.device_window,
                                        triggered=self.toggle_pf_window)

        self.toggle_device_window_action = QAction('&Devices', self.device_window,
                                        triggered=self.toggle_device_window)

        self.toggle_event_window_action = QAction('&Events', self.device_window,
                                        triggered=self.toggle_event_window)

        self.toggle_mode_window_action = QAction('&Modes', self.device_window,
                                        triggered=self.toggle_mode_window)

        self.toggle_variables_window_action = QAction('&Variables', self.device_window,
                                        triggered=self.toggle_variables_window)


        self.toggle_layer_lights_action = QAction('&Lights', self.device_window,
                                        statusTip='Show light devices',
                                        toolTip='Show light devices',
                                        triggered=self.toggle_layer_lights)
        self.toggle_layer_lights_action.setCheckable(True)
        self.toggle_layer_lights_action.setChecked(True)

        self.toggle_layer_switches_action = QAction('&Switches', self.device_window,
                                        statusTip='Show switch devices',
                                        toolTip='Show switch devices',
                                        triggered=self.toggle_layer_switches)
        self.toggle_layer_switches_action.setCheckable(True)
        self.toggle_layer_switches_action.setChecked(True)

        self.toggle_layer_others_action = QAction('&Others', self.device_window,
                                        statusTip='Show other devices',
                                        toolTip='Show other devices',
                                        triggered=self.toggle_layer_others)
        self.toggle_layer_others_action.setCheckable(True)
        self.toggle_layer_others_action.setChecked(True)

        self.cycle_layer_pf_image_action = QAction('&Image', self.device_window,
                                        statusTip='Cycle the playfield image',
                                        toolTip='Cycle the playfield image',
                                        triggered=self.cycle_pf_image)

        name_filter_input = QLineEdit()
        name_filter_input.setPlaceholderText('Device name filter')
        name_filter_input.setToolTip("Type <b>^</b> first to do starts-with matching.<br>Or use a <b>/</b> to do regex matching.")
        name_filter_input.setText('')
        name_filter_input.setMinimumWidth(80)
        name_filter_input.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
        name_filter_input.textChanged.connect(self.update_device_name_filter)
        name_filter_input.setFrame(False)

        pf_device_filter_action = QWidgetAction(self.device_window)
        pf_device_filter_action.setDefaultWidget(name_filter_input)
        pf_device_filter_action.isWidgetWithAction = True

        self.name_filter_input = name_filter_input
        self.pf_device_filter_action = pf_device_filter_action

        self.scene = QGraphicsScene()

        self._current_image_index = None
        self.pf = PfPixmapItem(QPixmap(self.get_next_image_file()), self)
        self.scene.addItem(self.pf)

        self.view = QGraphicsView(self.scene)
        self.view.resizeEvent = lambda event=None: self.view.fitInView(self.pf, Qt.AspectRatioMode.KeepAspectRatio)

        self.pf_window = QMainWindow()
        self.pf_window.setWindowTitle('Playfield')
        self.pf_window.setCentralWidget(self.view)
        self.pf_window.closeEvent = lambda event: self.closeEvent(event)
        self.pf_window.move(self.local_settings.value('windows/pf/pos', QPoint(800, 200)))
        self.pf_window.resize(self.local_settings.value('windows/pf/size', QSize(300, 600)))

        self.event_window = EventWindow(self)

        self.variables_window = VariableWindow(self)

        self.mode_window = ModeWindow(self)

        if self.get_local_settings_bool('windows/pf/visible'):
            self.toggle_pf_window()

        if self.get_local_settings_bool('windows/events/visible'):
            self.toggle_event_window()

        if self.get_local_settings_bool('windows/devices/visible'):
            self.toggle_device_window()

        if self.get_local_settings_bool('windows/modes/visible'):
            self.toggle_mode_window()

        if self.get_local_settings_bool('windows/variables/visible'):
            self.toggle_variables_window()

        self.exit_on_close = False
        if self.get_local_settings_bool('settings/exit-on-close'):
            self.toggle_exit_on_close()

        self.close_on_disconnect = False
        if self.get_local_settings_bool('settings/close-on-disconnect'):
            self.toggle_close_on_disconnect()

        self.set_inspector_mode(False)
        self.inspector_window = InspectorWindow(self)
        self.inspector_window.show()
        self.inspector_window.register_last_selected_cb()

        self.inspector_window.register_set_inspector_val_cb(self.set_inspector_mode)

        inspector_menu_bar = QMenuBar()
        view_menu = inspector_menu_bar.addMenu("&View")
        view_menu.addAction(self.toggle_pf_window_action)
        view_menu.addAction(self.toggle_device_window_action)
        view_menu.addAction(self.toggle_event_window_action)
        view_menu.addAction(self.toggle_mode_window_action)
        view_menu.addAction(self.toggle_variables_window_action)
        self.inspector_window.layout().setMenuBar(inspector_menu_bar)

        layers_toolbar = QToolBar('Layers')

        layers_toolbar.setFloatable(False)
        layers_toolbar.setStyleSheet("""
            QToolButton {
                background-color: palette(button);
                color: palette(button-text);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 4px 8px;
                margin: 0px 2px;
            }
            QToolButton:hover {
                background-color: palette(highlight);
                color: palette(highlighted-text);
                border: 1px solid palette(dark);
            }
            QToolButton:checked {
                background-color: palette(dark);
                color: palette(bright-text);
                border: 1px solid palette(shadow);
            QToolButton:checked:hover {
                background-color: palette(shadow);
            }
            QLineEdit {
                background-color: palette(base);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 4px;
            }
        """)

        layers_toolbar.addAction(self.toggle_layer_lights_action)
        layers_toolbar.addAction(self.toggle_layer_switches_action)
        layers_toolbar.addAction(self.toggle_layer_others_action)
        layers_toolbar.addAction(self.cycle_layer_pf_image_action)
        layers_toolbar.addSeparator()
        layers_toolbar.addAction(self.pf_device_filter_action)

        self.pf_window.addToolBar(layers_toolbar)

    def get_next_image_file(self):
        if self._current_image_index is None:
            self._current_image_index = 0
        else:
            self._current_image_index += 1
        if self._current_image_index >= len(self.image_files):
            self._current_image_index = None
            return None

        return self.image_files[self._current_image_index]

    def update_device_name_filter(self, text):
        self.device_name_filter = text
        self.scene.update()

    def cycle_pf_image(self):
        """Cycles through background images, or hides if on the last item."""
        if self.pf_window.isVisible():
            next_file = self.get_next_image_file()

            if next_file:
                self.pf.setPixmap(QPixmap(next_file))
                self.pf.show()
            else:
                # Reached the end of the sequence (None); hide the background layer
                self.pf.hide()

    def toggle_pf_window(self):
        if self.pf_window.isVisible():
            self.pf_window.hide()
            self.toggle_pf_window_action.setChecked(False)
        else:
            self.pf_window.show()
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

    def toggle_layer_lights(self):
        self.hide_layer_lights = not self.toggle_layer_lights_action.isChecked()
        self.scene.update()

    def toggle_layer_switches(self):
        self.hide_layer_switches = not self.toggle_layer_switches_action.isChecked()
        self.scene.update()

    def toggle_layer_others(self):
        self.hide_layer_others = not self.toggle_layer_others_action.isChecked()
        self.scene.update()

    def toggle_variables_window(self):
        if self.variables_window.isVisible():
            self.variables_window.hide()
            self.toggle_variables_window_action.setChecked(False)
        else:
            self.variables_window.show()
            self.toggle_variables_window_action.setChecked(True)

    def toggle_exit_on_close(self):
        self.exit_on_close = not self.exit_on_close

    def toggle_close_on_disconnect(self):
        self.close_on_disconnect = not self.close_on_disconnect

    def toggle_sort_by_time(self):
        self.sort_by_time = not self.sort_by_time

    def except_hook(self, cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)
        self.app.exit()

    def reset_connection(self):
        self.start_time = 0
        self.event_window.model.clear()
        self.mode_window.model.clear()

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
                self.variables_window.update_variable("player", kwargs["name"], kwargs["value"])
            elif cmd == 'machine_variable':
                self.variables_window.update_variable("machine", kwargs["name"], kwargs["value"])

        if added_events:
            self.event_window.update_events()

    def about(self):
        QMessageBox.about(self, "About MPF Monitor", "This is the MPF Monitor")

    def load_config(self):
        try:
            _yaml = yaml.YAML(typ='safe')
            with open(self.config_file, 'r') as f:
                self.config = _yaml.load(f)
        except FileNotFoundError:
                self.config = dict()

    def save_config(self):
        self.log.debug("Saving config to disk")
        with open(self.config_file, 'w') as f:
            _yaml = yaml.YAML(typ='safe')
            _yaml.default_flow_style = False
            _yaml.dump(self.config, f)

    def closeEvent(self, event):
        self.write_local_settings()
        event.accept()
        self.check_if_quit()

    def check_if_quit(self):
        if self.exit_on_close:
            self.log.info("Quitting due to quit on close")
            QCoreApplication.exit(0)

    def handle_mpf_disconnected(self):
        if self.close_on_disconnect:
            self.log.info("Quitting due to MPF connection and close_on_disconnect setting")
            self.write_local_settings()
            QCoreApplication.instance().exit(0)

    def write_window_settings(self, window_name, window):
        settings = {
            'pos': window.pos(),
            'size': window.size(),
            'visible': window.isVisible()
        }

        if hasattr(window, 'ui') and window.ui and hasattr(window.ui, 'sortComboBox'):
            settings['sort_index'] = window.ui.sortComboBox.currentIndex()

        for line in settings.keys():
            setting_name = 'windows/' + window_name + '/' + line
            self.local_settings.setValue(setting_name, settings.get(line))

    def get_local_settings_bool(self, setting):
        return "true" == str(self.local_settings.value(setting, False)).lower()

    def write_local_settings(self):
        monitor_windows = {
            'devices': self.device_window,
            'pf': self.pf_window,
            'modes': self.mode_window,
            'events': self.event_window,
            'inspector': self.inspector_window,
            'variables': self.variables_window,
        }

        for window in monitor_windows.keys():
            self.write_window_settings(window, monitor_windows.get(window))

        self.local_settings.setValue('settings/exit-on-close', self.exit_on_close)
        self.local_settings.setValue('settings/close-on-disconnect', self.close_on_disconnect)

        self.local_settings.sync()

    def set_inspector_mode(self, enabled=False):
        self.inspector_enabled = enabled

        if enabled:
            self.pf_window.setWindowTitle('Inspector Enabled - Playfield')
        else:
            self.pf_window.setWindowTitle('Playfield')
