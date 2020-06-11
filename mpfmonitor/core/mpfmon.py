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



from mpfmonitor.core.devices import *
from mpfmonitor.core.playfield import *
from mpfmonitor.core.bcp_client import BCPClient
from mpfmonitor.core.events import EventWindow
from mpfmonitor.core.modes import ModeWindow
from mpfmonitor.core.inspector import InspectorWindow

"""

Maybe use these soon
import mpfmonitor.core.devices
import mpfmonitor.core.playfield
import mpfmonitor.core.bcp_client
import mpfmonitor.core.events
import mpfmonitor.core.modes
import mpfmonitor.core.inspector


"""





class MainWindow(QTreeView):
    def __init__(self, app, machine_path, thread_stopper, parent=None):

        super().__init__(parent)

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
                                        "monitor.yaml")
        self.playfield_image_file = os.path.join(self.machine_path,
                                        "monitor", "playfield.jpg")

        self.local_settings = QSettings("mpf", "mpf-monitor")

        self.load_config()

        self.move(self.local_settings.value('windows/devices/pos',
                                            QPoint(200, 200)))
        self.resize(self.local_settings.value('windows/devices/size',
                                            QSize(300, 600)))

        self.setWindowTitle("Devices")

        self.pf_device_size = self.config.get("device_size", .02)

        self.device_states = dict()
        self.device_type_widgets = dict()

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, 'localhost', 5051)

        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(20)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start()

        self.toggle_pf_window_action = QAction('&Playfield', self,
                                        statusTip='Show the playfield window',
                                        triggered=self.toggle_pf_window)
        self.toggle_pf_window_action.setCheckable(True)

        self.toggle_device_window_action = QAction('&Devices', self,
                                        statusTip='Show the device window',
                                        triggered=self.toggle_device_window)
        self.toggle_device_window_action.setCheckable(True)

        self.toggle_event_window_action = QAction('&Events', self,
                                        statusTip='Show the events window',
                                        triggered=self.toggle_event_window)
        self.toggle_event_window_action.setCheckable(True)

        self.toggle_mode_window_action = QAction('&Modes', self,
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


        self.treeview = self
        self.model = DeviceTreeModel(self)
        self.rootNode = self.model.root
        self.treeview.setDragDropMode(QAbstractItemView.DragOnly)
        self.treeview.setItemDelegate(DeviceDelegate())
        self.treeview.setModel(self.model)

        self.event_window = EventWindow(self)

        self.mode_window = ModeWindow(self)

        if 1 or self.local_settings.value('windows/pf/visible', True):
            self.toggle_pf_window()

        if 1 or self.local_settings.value('windows/events/visible', True):
            self.toggle_event_window()

        if 1 or self.local_settings.value('windows/devices/visible', True):
            self.toggle_device_window()

        if 1 or self.local_settings.value('windows/modes/visible', True):
            self.toggle_mode_window()

        self.quit_on_close = False

        if str(self.local_settings.value('settings/quit-on-close', False)) == "true": # QSettings outputs string
            self.toggle_quit_on_close()

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
        if self.treeview.isVisible():
            self.treeview.hide()
            self.toggle_device_window_action.setChecked(False)
        else:
            self.treeview.show()
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

    def toggle_quit_on_close(self):
        if self.quit_on_close:
            self.quit_on_close = False
        else:
            self.quit_on_close = True

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
                    self.playfield.size(), Qt.KeepAspectRatio,
                    Qt.SmoothTransformation))
        except AttributeError:
            pass

        return super().eventFilter(source, event)

    def tick(self):
        """
        Called every 20 mSec
        Check the queue to see if BCP has any messages to process.
        If any devices have updated, refresh the model data.
        """

        device_update = False
        while not self.receive_queue.empty():
            cmd, kwargs = self.receive_queue.get_nowait()
            if cmd == 'device':
                self.process_device_update(**kwargs)
                device_update = True
            elif cmd == 'monitored_event':
                self.process_event_update(**kwargs)
            elif cmd in ('mode_start', 'mode_stop', 'mode_list'):
                self.process_mode_update(kwargs['running_modes'])
            elif cmd == 'reset':
                self.reset_connection()
                self.bcp.send("reset_complete")
        if device_update:
            self.model.refreshData()

    def process_mode_update(self, running_modes):
        """Update mode list."""
        self.mode_window.model.clear()

        for mode in running_modes:
            mode_name = QStandardItem(mode[0])
            mode_prio = QStandardItem(str(mode[1]))
            self.mode_window.model.insertRow(0, [mode_name, mode_prio])

        # Reset the headers for the tree. For some reason clear() wipes these too.
        self.mode_window.model.setHeaderData(0, Qt.Horizontal, "Mode")
        self.mode_window.model.setHeaderData(1, Qt.Horizontal, "Priority")

    def process_device_update(self, name, state, changes, type):
        self.log.debug("Device Update: {}.{}: {}".format(type, name, state))

        if type not in self.device_states:
            self.device_states[type] = dict()
            node = DeviceNode(type, "", "", self.rootNode)
            self.device_type_widgets[type] = node
            self.model.insertRow(0, QModelIndex())
            self.rootNode.sortChildren()

        if name not in self.device_states[type]:

            node = DeviceNode(name, "", "", self.device_type_widgets[type])
            self.device_states[type][name] = node
            self.device_type_widgets[type].sortChildren()

            self.pf.create_widget_from_config(node, type, name)

        self.device_states[type][name].setData(state)
        self.model.setData(self.model.index(0, 0, QModelIndex()), None)

    def process_event_update(self, event_name, event_type, event_callback,
                             event_kwargs, registered_handlers):

        from_bcp = event_kwargs.pop('_from_bcp', False)

        name = QStandardItem(event_name)
        kwargs = QStandardItem(str(event_kwargs))
        # ev_time = QStandardItem(time.time())
        self.event_window.model.insertRow(0, [name, kwargs])

        # for rh in registered_handlers:
        #     rh_name = QStandardItem(rh[0])
        #     rh_kwargs = QStandardItem(rh[1])
        #     self.event_window.model.index(0, 0).appendRow([rh_name, rh_kwargs])

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
        if self.quit_on_close:
            self.log.info("Quitting due to quit on close")
            QCoreApplication.exit(0)


    def write_local_settings(self):
        self.local_settings.setValue('windows/devices/pos', self.pos())
        self.local_settings.setValue('windows/devices/size', self.size())
        self.local_settings.setValue('windows/devices/visible', self.isVisible())

        self.local_settings.setValue('windows/pf/pos', self.view.pos())
        self.local_settings.setValue('windows/pf/size', self.view.size())
        self.local_settings.setValue('windows/pf/visible', self.view.isVisible())

        self.local_settings.setValue('windows/modes/pos', self.mode_window.pos())
        self.local_settings.setValue('windows/modes/size', self.mode_window.size())
        self.local_settings.setValue('windows/modes/visible', self.mode_window.isVisible())

        self.local_settings.setValue('windows/inspector/pos', self.inspector_window.pos())
        self.local_settings.setValue('windows/inspector/size', self.inspector_window.size())
        self.local_settings.setValue('windows/inspector/visible', self.inspector_window.isVisible())

        self.local_settings.setValue('windows/events/pos',
                                     self.event_window.pos())
        self.local_settings.setValue('windows/events/size',
                                     self.event_window.size())
        self.local_settings.setValue('windows/event/visible',
                                     self.event_window.isVisible())

        self.local_settings.setValue('settings/quit-on-close', self.quit_on_close)

        self.local_settings.sync()

    def set_inspector_mode(self, enabled=False):
        self.inspector_enabled = enabled
        self.view.set_inspector_mode_title(inspect=enabled)




def run(machine_path, thread_stopper):

    app = QApplication(sys.argv)
    MainWindow(app, machine_path, thread_stopper)
    app.exec_()
