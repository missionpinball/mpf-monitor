import unittest
from mpfmonitor.core.playfield import *
from unittest.mock import MagicMock

class TestablePfWidgetNonDrawn(PfWidget):
    def __init__(self, mpfmon_mock=None):

        if mpfmon_mock is not None:
            self.mpfmon = mpfmon_mock

    """
    __init__ of PfWidget:


    def __init__(self, mpfmon, widget, device_type, device_name, x, y,
                 size=None, rotation=0, shape=Shape.DEFAULT, save=True):
        super().__init__()

        self.widget = widget
        self.mpfmon = mpfmon
        self.name = device_name
        self.move_in_progress = True
        self.device_type = device_type
        self.set_size(size=size)
        self.shape = shape
        self.angle = rotation

        self.setToolTip('{}: {}'.format(self.device_type, self.name))
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setPos(x, y)
        self.update_pos(save)
        self.click_start = 0
        self.release_switch = False

        self.log = logging.getLogger('Core')

        old_widget_exists = widget.set_change_callback(self.notify)

        if old_widget_exists:
            self.log.debug("Previous widget exists.")
            old_widget_exists(destroy=True)

        """


class TestPfWidgetParameters(unittest.TestCase):

    def setUp(self):
        self.widget = TestablePfWidgetNonDrawn()

    def test_shape_set_valid(self):
        shape_to_be_set = Shape.TRIANGLE
        self.widget.set_shape(shape_to_be_set)

        self.assertEqual(self.widget.shape, shape_to_be_set)

    def test_shape_set_invalid(self):
        widget = TestablePfWidgetNonDrawn()

        shape_to_be_set = "Not_A_Shape"
        self.widget.set_shape(shape_to_be_set)

        self.assertEqual(self.widget.shape, Shape.DEFAULT)

    def test_rotation_set_valid(self):
        rotation_to_be_set = 42
        self.widget.set_rotation(rotation_to_be_set)

        self.assertEqual(self.widget.angle, rotation_to_be_set)

    def test_rotation_set_invalid(self):
        rotation_to_be_set = 451
        self.widget.set_rotation(rotation_to_be_set)

        expected_angle = rotation_to_be_set % 360

        self.assertEqual(self.widget.angle, expected_angle)

    def test_size_set_default(self):
        self.widget.mpfmon = MagicMock()
        default_size = 0.07
        scene_width = 1.00

        self.widget.mpfmon.pf_device_size = default_size
        self.widget.mpfmon.scene.width.return_value = scene_width

        self.widget.set_size()

        self.assertEqual(self.widget.size, default_size)
        self.assertEqual(self.widget.device_size, default_size * scene_width)

    def test_size_set_valid(self):
        self.widget.mpfmon = MagicMock()
        scene_width = 1.00

        self.widget.mpfmon.scene.width.return_value = scene_width

        size_to_be_set = 0.07

        self.widget.set_size(size=size_to_be_set)

        self.assertEqual(self.widget.size, size_to_be_set)
        self.assertEqual(self.widget.device_size, size_to_be_set * scene_width)


class TestPfWidgetResizeToDefault(unittest.TestCase):

    def setUp(self):
        self.mock_mpfmon = MagicMock()

        self.widget = TestablePfWidgetNonDrawn(mpfmon_mock=self.mock_mpfmon)

        self.widget.device_type = MagicMock()
        self.widget.name = MagicMock()
        self.widget.set_size = MagicMock()
        self.widget.update_pos = MagicMock()

        self.config = MagicMock()
        self.mock_mpfmon.config[self.widget.device_type].get.return_value = self.config
        self.config.get.return_value = None

        """
        def resize_to_default(self, force=False):
        device_config = self.mpfmon.config[self.device_type].get(self.name, None)

        if force:
            device_config.pop('size', None) # Delete saved size info, None is incase key doesn't exist (popped twice)

        device_size = device_config.get('size', None)

        if device_size is not None:
            # Do not change the size if it's already set
            pass
        elif device_config is not None:
            self.set_size()

        self.update_pos(save=False)  # Do not save at this point. Let it be saved elsewhere. This reduces writes."""

    def test_size_resize_to_default(self):
        self.widget.resize_to_default()

        self.mock_mpfmon.config[self.widget.device_type].get.assert_called_once_with(self.widget.name, None)
        self.widget.set_size.assert_called_once()
        self.widget.update_pos.assert_called_once_with(save=False)

    def test_size_resize_to_default_with_force(self):
        self.widget.resize_to_default(force=True)

        self.mock_mpfmon.config[self.widget.device_type].get.assert_called_once_with(self.widget.name, None)
        self.widget.set_size.assert_called_once()
        self.widget.update_pos.assert_called_once_with(save=False)
        self.config.pop.assert_called_once_with('size', None)


class TestPfWidgetColorFuncs(unittest.TestCase):

    def setUp(self):
        self.widget = TestablePfWidgetNonDrawn()

    def test_color_gamma(self):
        color_in = [0, 128, 255]
        expected_color_out = [0, 203, 255]  # Manually calculated 128 -> 203

        mock_widget = DeviceNode()
        mock_widget.setData({"color": color_in})
        mock_widget.setType('light')
        color_out = mock_widget._calculate_color_gamma_correction(color=color_in)

        self.assertEqual(color_out, expected_color_out, 'Gamma does not match expected value')

    def test_colored_brush_light(self):
        color_in = [0, 128, 255]
        expected_color_out = [0, 203, 255]  # Manually calculated 128 -> 203
        device_type = 'light'
        mock_widget = DeviceNode()
        mock_widget.setData({"color": color_in})
        mock_widget.setType(device_type)

        expected_q_brush_out = QBrush(QColor(*expected_color_out), Qt.BrushStyle.SolidPattern)
        q_brush_out = mock_widget.get_colored_brush()

        self.assertEqual(q_brush_out, expected_q_brush_out, 'Brush is not returning correct value')

    def test_colored_brush_switch_off(self):
        device_type = 'switch'
        expected_color_out = [0, 0, 0]
        mock_widget = DeviceNode()
        mock_widget.setData({'state': False})
        mock_widget.setType(device_type)

        expected_q_brush_out = QBrush(QColor(*expected_color_out), Qt.BrushStyle.SolidPattern)
        q_brush_out = mock_widget.get_colored_brush()

        self.assertEqual(q_brush_out, expected_q_brush_out, 'Brush is not returning correct value')

    def test_colored_brush_switch_on(self):
        device_type = 'switch'
        expected_color_out = [0, 255, 0]
        mock_widget = DeviceNode()
        mock_widget.setData({'state': True})
        mock_widget.setType(device_type)

        expected_q_brush_out = QBrush(QColor(*expected_color_out), Qt.BrushStyle.SolidPattern)
        q_brush_out = mock_widget.get_colored_brush()

        self.assertEqual(q_brush_out, expected_q_brush_out, 'Brush is not returning correct value')


class TestPfWidgetGetAndDestroy(unittest.TestCase):

    def setUp(self):
        self.widget = TestablePfWidgetNonDrawn(mpfmon_mock=MagicMock())

    def test_delete_from_config(self):
        device_type = MagicMock()
        self.widget.device_type = device_type

        name = "delete_test"
        self.widget.name = name

        self.widget.delete_from_config()

        self.widget.mpfmon.config[device_type].pop.assert_called_once_with(name)
        self.widget.mpfmon.save_config.assert_called_once()

    def test_send_to_inspector_window(self):
        self.widget.send_to_inspector_window()
        self.widget.mpfmon.inspector_window_last_selected_cb.assert_called_once_with(pf_widget=self.widget)
