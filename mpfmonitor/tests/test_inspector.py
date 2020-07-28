import unittest

from mpfmonitor.core.inspector import *
from unittest.mock import MagicMock


class TestableInspectorNoGUI(InspectorWindow):
    def __init__(self, mpfmon_mock=None, logger=False):
        if mpfmon_mock is not None:
            self.mpfmon = mpfmon_mock

        # super().__init__()
        self.ui = None

        # Call logger=True if "RuntimeError: super-class __init__()" starts failing tests.
        if logger:
            self.log = logging.getLogger('Core')

        # self.draw_ui()
        # self.attach_signals()


class InspectorMode(unittest.TestCase):
    def test_toggle_inspector_mode_on(self):
        mock_mpfmon = MagicMock()
        mock_mpfmon.inspector_enabled = False
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon, logger=True)

        # Register the callback to set the inspector value as a mock
        inspector.register_set_inspector_val_cb(MagicMock())

        inspector.toggle_inspector_mode()

        # Test that the previously registered mock is called.
        inspector.set_inspector_val_cb.assert_called_once_with(True)

    def test_toggle_inspector_mode_off(self):
        mock_mpfmon = MagicMock()
        mock_mpfmon.inspector_enabled = True
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon, logger=True)

        # Register the callback to set the inspector value as a mock
        inspector.register_set_inspector_val_cb(MagicMock())

        # clear_last_selected_device should be called as a result of toggling on -> off
        inspector.clear_last_selected_device = MagicMock()

        inspector.toggle_inspector_mode()

        # Test that the previously registered mock is called.
        inspector.set_inspector_val_cb.assert_called_once_with(False)

        # Test clear_last_selected_device was actually called
        inspector.clear_last_selected_device.assert_called_once()

    def test_cb_register(self):
        inspector = TestableInspectorNoGUI()
        inspector.registered_inspector_cb = False

        callback = MagicMock()
        inspector.register_set_inspector_val_cb(cb=callback)

        # Check that the mocked callback is registered properly
        inspector.set_inspector_val_cb(True)

        self.assertTrue(inspector.registered_inspector_cb)
        inspector.set_inspector_val_cb.assert_called_once_with(True)

class InspectorDeviceManipulation(unittest.TestCase):

    def test_update_last_selected(self):
        inspector = TestableInspectorNoGUI()
        # Mock ui to check that the ui is updated
        inspector.ui = MagicMock()

        # Mock widget to pass into the pf_widget parameter
        mock_widget = MagicMock()

        # Set the mock widget's name and size.
        mock_widget.name.__str__.return_value = 'LastName'
        # Return value doesn't quite work here. Just load in a float.
        widget_size = float(0.10)
        mock_widget.size = widget_size

        inspector.update_last_selected(pf_widget=mock_widget)

        # Check that the name is called.
        mock_widget.name.__str__.assert_called_once()

        inspector.ui.device_group_box.setTitle.assert_called_once_with('"LastName" Size:')
        inspector.ui.size_slider.setValue.assert_called_once_with(widget_size * 100)
        inspector.ui.size_spinbox.setValue.assert_called_once_with(widget_size)

    def test_delete_last_device(self):
        inspector = TestableInspectorNoGUI()

        inspector.last_pf_widget = MagicMock()
        inspector.clear_last_selected_device = MagicMock()

        inspector.delete_last_device()

        inspector.last_pf_widget.destroy.assert_called_once()
        inspector.clear_last_selected_device.assert_called_once()


class InspectorDeviceResizing(unittest.TestCase):

    def test_resize_default_device_default_no_save(self):
        mock_mpfmon = MagicMock()
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon)

        size = float(0.07)

        inspector.last_pf_widget = None
        inspector.update_last_device(new_size=size, save=False)

        # self.assertEqual(mock_mpfmon.pf_device_size, size)

    def test_resize_default_device_default_save(self):
        mock_mpfmon = MagicMock()
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon)

        size = float(0.07)

        inspector.last_pf_widget = None
        inspector.resize_all_devices = MagicMock()
        inspector.update_last_device(new_size=size, save=True)

        # self.assertEqual(mock_mpfmon.pf_device_size, size)
        inspector.resize_all_devices.assert_called_once()
        mock_mpfmon.view.resizeEvent.assert_called_once()  # Re draw the playfiled
        mock_mpfmon.save_config.assert_called_once()  # Save the config with new default to disk

    def test_resize_last_device_default_no_save(self):
        mock_mpfmon = MagicMock()
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon)

        size = float(0.07)

        inspector.last_pf_widget = MagicMock()
        inspector.update_last_device(new_size=size, save=False)

        inspector.last_pf_widget.set_size.assert_called_once_with(size)
        inspector.last_pf_widget.update_pos.assert_called_once_with(save=False)

        mock_mpfmon.view.resizeEvent.assert_called_once()  # Re draw the playfield

    def test_resize_last_device_default_save(self):
        mock_mpfmon = MagicMock()
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon)

        size = float(0.07)

        inspector.last_pf_widget = MagicMock()
        inspector.update_last_device(new_size=size, save=True)

        inspector.last_pf_widget.set_size.assert_called_once_with(size)
        inspector.last_pf_widget.update_pos.assert_called_once_with(save=True)

        mock_mpfmon.view.resizeEvent.assert_called_once()  # Re draw the playfield


class InspectorDeviceRotation(unittest.TestCase):

    def test_rotate_device_without_save(self):
        mock_mpfmon = MagicMock()
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon)

        rotation = 90

        inspector.last_pf_widget = MagicMock()
        inspector.update_last_device(rotation=rotation, save=False)
        inspector.last_pf_widget.set_rotation.assert_called_once_with(rotation)
        inspector.last_pf_widget.update_pos.assert_called_once_with(save=False)

    def test_rotate_device_with_save(self):
        mock_mpfmon = MagicMock()
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon)

        rotation = 90

        inspector.last_pf_widget = MagicMock()
        inspector.update_last_device(rotation=rotation, save=True)
        inspector.last_pf_widget.set_rotation.assert_called_once_with(rotation)
        inspector.last_pf_widget.update_pos.assert_called_once_with(save=True)


class InspectorDeviceShape(unittest.TestCase):
    from mpfmonitor.core.playfield import Shape

    def test_device_shape_without_save(self):
        mock_mpfmon = MagicMock()
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon)

        shape = Shape.TRIANGLE

        inspector.last_pf_widget = MagicMock()
        inspector.update_last_device(shape=shape, save=False)
        inspector.last_pf_widget.set_shape.assert_called_once_with(shape=shape)
        inspector.last_pf_widget.update_pos.assert_called_once_with(save=False)

    def test_device_shape_with_save(self):
        mock_mpfmon = MagicMock()
        inspector = TestableInspectorNoGUI(mpfmon_mock=mock_mpfmon)

        shape = Shape.TRIANGLE

        inspector.last_pf_widget = MagicMock()
        inspector.update_last_device(shape=shape, save=True)
        inspector.last_pf_widget.set_shape.assert_called_once_with(shape=shape)
        inspector.last_pf_widget.update_pos.assert_called_once_with(save=True)


if __name__ == '__main__':
    unittest.main()
