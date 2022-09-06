import logging

# will change these to specific imports once code is more final
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6 import uic

from mpfmonitor.core.playfield import Shape

import os


class InspectorWindow(QWidget):

    def __init__(self, mpfmon):
        self.mpfmon = mpfmon
        super().__init__()
        self.ui = None

        self.log = logging.getLogger('Core')

        self.draw_ui()
        self.attach_signals()

        self.enable_non_default_widgets(enabled=False)

        self.last_pf_widget = None

    def draw_ui(self):
        # Load ui file from ./ui/
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "inspector.ui")
        self.ui = uic.loadUi(ui_path, self)

        self.ui.setWindowTitle('Inspector')

        self.ui.move(self.mpfmon.local_settings.value('windows/inspector/pos',
                                                   QPoint(1100, 465)))
        self.ui.resize(self.mpfmon.local_settings.value('windows/inspector/size',
                                                     QSize(300, 340)))

    def attach_signals(self):
        self.attach_inspector_tab_signals()
        self.attach_monitor_tab_signals()

    def attach_inspector_tab_signals(self):
        self.ui.toggle_inspector_button.clicked.connect(self.toggle_inspector_mode)

        self.ui.shape_combo_box.currentIndexChanged.connect(self.shape_combobox_changed)
        self.ui.rotationDial.valueChanged.connect(self.dial_changed)

        self.ui.size_slider.valueChanged.connect(self.slider_drag)  # Doesn't save value, just for live preview
        self.ui.size_slider.sliderReleased.connect(self.slider_changed)  # Saves value on release
        self.ui.size_spinbox.valueChanged.connect(self.spinbox_changed)

        self.ui.reset_to_defaults_button.clicked.connect(self.reset_defaults_last_device)
        self.ui.delete_last_device_button.clicked.connect(self.delete_last_device)

    def attach_monitor_tab_signals(self):
        self.ui.toggle_device_win_button.setChecked(self.mpfmon.toggle_device_window_action.isChecked())
        self.ui.toggle_device_win_button.stateChanged.connect(self.mpfmon.toggle_device_window)

        self.ui.toggle_event_win_button.setChecked(self.mpfmon.toggle_event_window_action.isChecked())
        self.ui.toggle_event_win_button.stateChanged.connect(self.mpfmon.toggle_event_window)

        self.ui.toggle_pf_win_button.setChecked(self.mpfmon.toggle_pf_window_action.isChecked())
        self.ui.toggle_pf_win_button.stateChanged.connect(self.mpfmon.toggle_pf_window)

        self.ui.toggle_mode_win_button.setChecked(self.mpfmon.toggle_mode_window_action.isChecked())
        self.ui.toggle_mode_win_button.stateChanged.connect(self.mpfmon.toggle_mode_window)

        self.ui.exit_on_close_button.setChecked(self.mpfmon.get_local_settings_bool('settings/exit-on-close'))
        self.ui.exit_on_close_button.stateChanged.connect(self.mpfmon.toggle_exit_on_close)

    def toggle_inspector_mode(self):
        inspector_enabled = not self.mpfmon.inspector_enabled
        if self.registered_inspector_cb:
            self.set_inspector_val_cb(inspector_enabled)
            if inspector_enabled:
                self.log.debug('Inspector mode toggled ON')
            else:
                self.log.debug('Inspector mode toggled OFF')
                self.enable_non_default_widgets(enabled=False)
                self.clear_last_selected_device()

    def register_set_inspector_val_cb(self, cb):
        self.registered_inspector_cb = True
        self.set_inspector_val_cb = cb

    def update_last_selected(self, pf_widget=None):
        if pf_widget is not None:
            self.enable_non_default_widgets(enabled=True)

            self.last_pf_widget = pf_widget

            # Update the label to show name of last selected
            text = '"' + str(self.last_pf_widget.name) + '" Size:'
            self.ui.device_group_box.setTitle(text)

            # Update the size slider and spinbox
            self.ui.size_slider.setValue(self.last_pf_widget.size * 100)
            self.ui.size_spinbox.setValue(self.last_pf_widget.size)

            # Update the shape combo box
            self.ui.shape_combo_box.setCurrentIndex(self.last_pf_widget.shape.value)

            # Update the rotation dial
            rotation = int(self.last_pf_widget.angle / 10) + 18
            self.ui.rotationDial.setValue(rotation)


    def slider_drag(self):
        # For live preview
        new_size = self.ui.size_slider.value() / 100  # convert from int to float
        self.update_last_device(new_size=new_size, save=False)

    def slider_changed(self):
        new_size = self.ui.size_slider.value() / 100  # convert from int to float
        # Update spinbox value
        self.ui.size_spinbox.setValue(new_size)

        # Don't need to call resize_last_device because updating the spinbox takes care of it
        # self.resize_last_device(new_size=new_size)

    def spinbox_changed(self):
        new_size = self.ui.size_spinbox.value()
        # Update slider value
        self.ui.size_slider.setValue(new_size*100)

        self.update_last_device(new_size=new_size)

    def dial_changed(self):
        rot_value = self.ui.rotationDial.value() * 10
        # Offset the dial by 180
        rot_value = (rot_value - 180) % 360
        # self.rotate_last_device(rotation=rot_value, save=False)
        self.update_last_device(rotation=rot_value, save=True)

    def shape_combobox_changed(self):
        shape_index = self.ui.shape_combo_box.currentIndex()
        self.update_last_device(shape=Shape(shape_index), save=True)

    def clear_last_selected_device(self):
        # Must be called AFTER spinbox valueChanged is set. Otherwise slider will not follow

        # self.last_selected_label.setText("Default Device Size:")
        self.ui.device_group_box.setTitle("Default Device:")
        self.last_pf_widget = None
        self.ui.size_spinbox.setValue(self.mpfmon.pf_device_size)  # Reset the value to the stored default.
        self.enable_non_default_widgets(enabled=False)


    def enable_non_default_widgets(self, enabled=False):
        if self.ui is not None:
            self.ui.rotationDial.setEnabled(enabled)
            self.ui.shape_combo_box.setEnabled(enabled)


    def update_last_device(self, new_size=None, rotation=None, shape=None, save=True):
        # Check that there is a last widget
        if self.last_pf_widget is not None:

            update_and_resize = False

            if new_size is not None:
                new_size = round(new_size, 3)

                self.last_pf_widget.set_size(new_size)
                update_and_resize = True

            if rotation is not None:
                self.last_pf_widget.set_rotation(rotation)
                update_and_resize = True

            if shape is not None:
                self.last_pf_widget.set_shape(shape=shape)
                update_and_resize = True

            if update_and_resize:
                self.last_pf_widget.update_pos(save=save)
                self.mpfmon.view.resizeEvent()

        else:
            if new_size is not None:
                self.mpfmon.pf_device_size = new_size
                self.mpfmon.config["device_size"] = new_size

            if save:
                self.resize_all_devices()  # Apply new sizes to all devices without default sizes
                self.mpfmon.view.resizeEvent()  # Re draw the playfield
                self.mpfmon.save_config()  # Save the config with new default to disk


    def delete_last_device(self):
        if self.last_pf_widget is not None:
            self.last_pf_widget.destroy()
            self.clear_last_selected_device()
        else:
            self.log.info("No device selected to delete")

    def reset_defaults_last_device(self):
        if self.last_pf_widget is not None:

            # Redraw the device and save changes
            default_size = self.mpfmon.pf_device_size
            self.update_last_device(new_size=default_size, shape=Shape.DEFAULT,
                                    rotation=0, save=True)

            self.ui.size_spinbox.setValue(default_size)
            self.ui.rotationDial.setValue(18)
            self.ui.shape_combo_box.setCurrentIndex(0)


            # Update the device info and clear saved size data
            self.last_pf_widget.resize_to_default(force=True)


            # Redraw the device
        else:
            self.ui.size_spinbox.setValue(0.07)
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
