import logging

# will change these to specific imports once code is more final
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

class InspectorWindow(QWidget):

    def __init__(self, mpfmon):
        self.mpfmon = mpfmon
        super().__init__()

        self.setWindowTitle('Inspector')


        self.log = logging.getLogger('Core')

        self.move(self.mpfmon.local_settings.value('windows/inspector/pos',
                                                   QPoint(1100, 500)))
        self.resize(self.mpfmon.local_settings.value('windows/inspector/size',
                                                     QSize(300, 300)))

        self.last_pf_widget = None

        self.populate()
        self.register_last_selected_cb()

    def populate(self):
        self.tabs = QTabWidget()

        self.layout = QVBoxLayout()

        self.layout.addWidget(self.tabs)
        self.dev_inspect_tab = self.build_device_inspector_tab(self.tabs)
        self.monitor_inspect_tab = self.build_monitor_inspector_tab(self.tabs)

        self.setLayout(self.layout)


    def build_device_inspector_tab(self, tabs):
        dev_inspect_tab = QWidget()
        dev_inspect_tab.layout = QVBoxLayout()

        tabs.addTab(dev_inspect_tab, "Device Inspector")

        toggle_inspector_button = QPushButton('Toggle Device Inspector', self)
        toggle_inspector_button.clicked.connect(self.toggle_inspector_mode)
        toggle_inspector_button.setCheckable(True) # Makes the button "toggle-able"
        dev_inspect_tab.layout.addWidget(toggle_inspector_button)

        refresh_pf_button = QPushButton("Refresh Playfield Drawing", self)
        refresh_pf_button.clicked.connect(self.mpfmon.view.resizeEvent)
        dev_inspect_tab.layout.addWidget(refresh_pf_button)

        self.last_selected_label = QLabel("Last Selected:") # Text gets overwritten later
        dev_inspect_tab.layout.addWidget(self.last_selected_label)

        slider_spin_combo = QHBoxLayout()

        self.slider = QSlider(Qt.Horizontal)

        # Slider values are ints, and we need floats, so range is 1-60, mapped to 0.01-0.6
        self.slider.setMinimum(1)
        self.slider.setMaximum(60)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(5)

        slider_spin_combo.addWidget(self.slider)

        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(0.01, 0.6)
        self.spinbox.setSingleStep(0.01)

        slider_spin_combo.addWidget(self.spinbox)

        self.slider.valueChanged.connect(self.slider_drag) # Doesn't save value, just for live preview
        self.slider.sliderReleased.connect(self.slider_changed) # Saves value on release
        self.spinbox.valueChanged.connect(self.spinbox_changed)


        self.clear_last_selected_device()

        default_size_button = QPushButton("Default", self)
        default_size_button.clicked.connect(self.force_resize_last_device)
        slider_spin_combo.addWidget(default_size_button)


        dev_inspect_tab.layout.setAlignment(Qt.AlignTop)

        dev_inspect_tab.layout.addLayout(slider_spin_combo)



        delete_last_device_button = QPushButton("Delete device", self)
        delete_last_device_button.clicked.connect(self.delete_last_device)
        dev_inspect_tab.layout.addWidget(delete_last_device_button)



        dev_inspect_tab.setLayout(dev_inspect_tab.layout)

        return dev_inspect_tab


    def build_monitor_inspector_tab(self, tabs):
        tab_scroll = QScrollArea()
        tab = QWidget()
        scroll_layout = QVBoxLayout(tab)

        scroll_layout.setAlignment(Qt.AlignTop)

        tabs.addTab(tab_scroll, "Monitor Inspector")

        toggle_device_win_button = QCheckBox("Show device window", self)
        toggle_device_win_button.setChecked(self.mpfmon.toggle_device_window_action.isChecked())
        toggle_device_win_button.stateChanged.connect(self.mpfmon.toggle_device_window)
        scroll_layout.addWidget(toggle_device_win_button)

        toggle_event_win_button = QCheckBox("Show event window", self)
        toggle_event_win_button.setChecked(self.mpfmon.toggle_event_window_action.isChecked())
        toggle_event_win_button.stateChanged.connect(self.mpfmon.toggle_event_window)
        scroll_layout.addWidget(toggle_event_win_button)

        toggle_pf_win_button = QCheckBox("Show playfield window", self)
        toggle_pf_win_button.setChecked(self.mpfmon.toggle_pf_window_action.isChecked())
        toggle_pf_win_button.stateChanged.connect(self.mpfmon.toggle_pf_window)
        scroll_layout.addWidget(toggle_pf_win_button)

        toggle_mode_win_button = QCheckBox("Show mode window", self)
        toggle_mode_win_button.setChecked(self.mpfmon.toggle_mode_window_action.isChecked())
        toggle_mode_win_button.stateChanged.connect(self.mpfmon.toggle_mode_window)
        scroll_layout.addWidget(toggle_mode_win_button)


        line = QFrame()
        line.setFixedHeight(3)
        line.setFrameShadow(QFrame.Sunken)
        line.setFrameShape(QFrame.HLine)
        line.setLineWidth(1)
        scroll_layout.addWidget(line)

        quit_on_close_button = QCheckBox("Quit on single window close", self)
        quit_on_close_button.setChecked(
            "true" == str(self.mpfmon.local_settings.value('settings/quit-on-close', False))
        )

        quit_on_close_button.stateChanged.connect(self.mpfmon.toggle_quit_on_close)
        scroll_layout.addWidget(quit_on_close_button)

        tab_scroll.setWidget(tab)

        return tab


    def toggle_inspector_mode(self):
        inspector_enabled = not self.mpfmon.inspector_enabled
        if self.registered_inspector_cb:
            self.set_inspector_val_cb(inspector_enabled)
            if inspector_enabled:
                self.log.debug('Inspector mode toggled ON')
            else:
                self.log.debug('Inspector mode toggled OFF')
                self.clear_last_selected_device()

    def register_set_inspector_val_cb(self, cb):
        self.registered_inspector_cb = True
        self.set_inspector_val_cb = cb

    def update_last_selected(self, pf_widget=None):
        if pf_widget is not None:
            self.last_pf_widget = pf_widget
            text = '"' + str(self.last_pf_widget.name) + '" Size:'
            self.last_selected_label.setText(text)
            self.slider.setValue(self.last_pf_widget.size * 100)
            self.spinbox.setValue(self.last_pf_widget.size)


    def slider_drag(self):
        # For live preview
        new_size = self.slider.value() / 100  # convert from int to float
        self.resize_last_device(new_size=new_size, save=False)

    def slider_changed(self):
        new_size = self.slider.value() / 100  # convert from int to float
        # Update spinbox value
        self.spinbox.setValue(new_size)

        # Don't need to call resize_last_device because updating the spinbox takes care of it
        # self.resize_last_device(new_size=new_size)

    def spinbox_changed(self):
        new_size = self.spinbox.value()
        # Update slider value
        self.slider.setValue(new_size*100)

        self.resize_last_device(new_size=new_size)



    def clear_last_selected_device(self):
        # Must be called AFTER spinbox valueChanged is set. Otherwise slider will not follow

        self.last_selected_label.setText("Default Device Size:")
        self.last_pf_widget = None
        self.spinbox.setValue(self.mpfmon.pf_device_size) # Reset the value to the stored default.


    def resize_last_device(self, new_size=None, save=True):
        new_size = round(new_size, 3)
        if self.last_pf_widget is not None:
            self.last_pf_widget.set_size(new_size)
            self.last_pf_widget.update_pos(save=save)
            self.mpfmon.view.resizeEvent()

        else:   # Change the default size.
            self.mpfmon.pf_device_size = new_size
            self.mpfmon.config["device_size"] = new_size

            if save:
                self.resize_all_devices() # Apply new sizes to all devices without default sizes
                self.mpfmon.view.resizeEvent() # Re draw the playfiled
                self.mpfmon.save_config() # Save the config with new default to disk


    def delete_last_device(self):
        if self.last_pf_widget is not None:
            self.last_pf_widget.destroy()
            self.clear_last_selected_device()
        else:
            self.log.info("No device selected to delete")

    def force_resize_last_device(self):
        if self.last_pf_widget is not None:

            # Redraw the device without saving
            default_size = self.mpfmon.pf_device_size
            self.resize_last_device(new_size=default_size, save=False)

            # Update the device info and clear saved size data
            self.last_pf_widget.resize_to_default(force=True)


            # Redraw the device
        else:
            self.spinbox.setValue(0.07)
            self.log.info("No device selected to resize")

    def resize_all_devices(self):
        for i in self.mpfmon.scene.items():
            try:
                i.resize_to_default()
            except AttributeError as e:
                # Can't resize object. That's ok.
                pass

    def register_last_selected_cb(self):
        self.mpfmon.inspector_window_last_selected_cb = self.update_last_selected


    def closeEvent(self, event):
        self.mpfmon.write_local_settings()
        event.accept()
        self.mpfmon.check_if_quit()
