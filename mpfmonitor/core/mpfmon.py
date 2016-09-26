import logging
import queue
import threading
import ruamel.yaml as yaml

from kivy.app import App
from kivy.uix.label import Label
from kivy.logger import Logger
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.dropdown import DropDown
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup


from mpfmonitor.core.bcp_client import BCPClient

from mpfmonitor._version import __version__

# The following line is needed to allow mpfmon modules to use the getLogger(
# name) method
logging.Logger.manager.root = Logger


class MpfMon(App):

    def __init__(self, **kwargs):
        self.log = logging.getLogger('mpf-mon')
        self.log.info("MPF Monitor v%s", __version__)
        super().__init__(**kwargs)

        self.bcp_client_connected = False
        self.receive_queue = queue.Queue()
        self.sending_queue = queue.Queue()
        self.crash_queue = queue.Queue()
        self.thread_stopper = threading.Event()

        self.device_states = dict()
        self.device_type_widgets = dict()

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, 'localhost', 5051)

    def build(self):
        Clock.schedule_interval(self.tick, 0)
        # self.layout = FloatLayout()
        # self.menu = BoxLayout(padding=10, orientation='vertical',
        #                         size_hint_x=0.2, pos_hint={'y':0})
        # self.layout.add_widget(self.menu)

        self.dropdown = DropDown()

        self.layout = FloatLayout()
        self.popup = None

        self.main_button = Button(text='Devices', size_hint=(None, None))
        self.main_button.bind(on_release=self.dropdown.open)
        self.dropdown.bind(on_select=lambda instance, x: setattr(
            self.main_button, 'text', x))
        self.dropdown.bind(on_select=self.device_type_selected)

        self.device_grid = GridLayout(spacing=20, cols=3, padding=20)

        self.layout.add_widget(self.main_button)
        self.layout.add_widget(self.device_grid)

        return self.layout

    def tick(self, dt):
        del dt

        while not self.receive_queue.empty():
            cmd, kwargs = self.receive_queue.get_nowait()
            if cmd == 'device':
                self.process_device_update(**kwargs)

            if cmd == 'trigger' and kwargs.get('name') == 'client_connected':
                self.socket_thread.start_sending_loop()

    def process_device_update(self, name, state, changes, type):
        try:
            self.device_states[type][name] = state
        except KeyError:
            if type not in self.device_states:
                self.device_states[type] = dict()
                # self.device_type_widgets[type] = Button(text=type)
                # self.layout.add_widget(self.device_type_widgets[type])

                button = Button(text=type, size_hint_y=None, height=44)
                button.bind(on_release=lambda button: self.dropdown.select(
                    button.text))

                self.dropdown.add_widget(button)

            self.device_states[type][name] = state

        try:
            if self.popup.title == '{}: {}'.format(type, name):
                self.popup_text.text = yaml.dump(state, default_flow_style=False)
        except AttributeError:
            pass

    def device_type_selected(self, widget, device_type):

            self.device_grid.clear_widgets()

            for device, state in self.device_states[device_type].items():
               btn = Button(text=device)
               btn.device_type = device_type
               btn.device_name = device
               btn.bind(on_release=self.do_popup)
               self.device_grid.add_widget(btn)

    def do_popup(self, widget):
        self.popup_text = Label(text=yaml.dump(self.device_states[
            widget.device_type][widget.device_name], default_flow_style=False))
        self.popup = Popup(title='{}: {}'.format(widget.device_type, widget.device_name),
                           content=self.popup_text)
        self.popup.open()

    def on_stop(self):
        self.log.info("Stopping...")
        self.thread_stopper.set()
        self.bcp.disconnect()

