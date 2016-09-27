import logging
import queue
import threading
from collections import OrderedDict

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
from kivy.lang import Builder
from kivy.uix.treeview import TreeViewLabel, TreeViewNode
from kivy.uix.widget import WidgetException
from kivy.graphics import *
from kivy.uix.bubble import Bubble, BubbleButton
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics.vertex_instructions import RoundedRectangle
from kivy.uix.behaviors import DragBehavior
from kivy.uix.image import Image
from kivy.uix.widget import Widget

from mpfmonitor.core.bcp_client import BCPClient
from kivy.uix.tabbedpanel import TabbedPanel

from mpfmonitor._version import __version__

from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

# The following line is needed to allow mpfmon modules to use the getLogger(
# name) method
logging.Logger.manager.root = Logger


Builder.load_string("""

<Test>:
    size_hint: 1, 1
    pos_hint: {'center_x': .5, 'center_y': .5}
    do_default_tab: False

    TabbedPanelItem:
        text: 'Devices'
        BoxLayout:
            padding: 4
            spacing: 4
            ScrollView:
                size_hint_x: .4
                TreeView:
                    text: 'First tab content area'
                    id: device_tree
                    size_hint: (1, 10)
                    # y: device_tree.minimum_height
                    hide_root: True
            RelativeLayout:
                id: device_frame

    TabbedPanelItem:
        text: 'Playfield'
        FloatLayout:
            id: playfield_image
""")

class Test(TabbedPanel):
    pass

class TreeViewButton(Button, TreeViewNode):
    pass


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

        self.device_states = OrderedDict()
        self.device_type_widgets = dict()

        self.bcp = BCPClient(self, self.receive_queue,
                             self.sending_queue, 'localhost', 5051)

    def build(self):
        Clock.schedule_interval(self.tick, 0)

        self.tabbed_panel = Test()
        self.device_tree = self.tabbed_panel.ids.device_tree
        self.playfield_image = self.tabbed_panel.ids.playfield_image

        self.playfield_image.add_widget(Image(source='monitor/playfield.jpg'))

        return self.tabbed_panel

    def tick(self, dt):
        del dt
        while not self.receive_queue.empty():
            cmd, kwargs = self.receive_queue.get_nowait()
            if cmd == 'device':
                self.process_device_update(**kwargs)

            if cmd == 'trigger' and kwargs.get('name') == 'client_connected':
                self.socket_thread.start_sending_loop()

    def process_device_update(self, name, state, changes, type):

        if type not in self.device_states:
            self.device_states[type] = OrderedDict()
            node = TreeViewLabel(text=type, id='{}'.format(type))
            self.device_tree.ids['{}'.format(type)] = node
            self.device_tree.add_node(node)

        if name not in self.device_states[type]:

            self.device_states[type][name] = state

            cls = device_classes.get(type, TreeViewLabel)

            node = cls(on_touch_down=self.device_clicked,
                                 id='{}.{}'.format(type, name))
            node = cls(id='{}.{}'.format(type, name))


            label = Label(text=name)
            node.add_widget(label)

            self.device_tree.ids['{}.{}'.format(type, name)] = node
            self.device_tree.add_node(node, self.device_tree.ids['{}'.format(type)])


            if type == 'led' and name == 'l_mystery':

                self.pf_widget = LedPlayfield(size=(10,10),
                                              on_touch_down=self.device_clicked)
                self.playfield_image.add_widget(self.pf_widget)

        self.device_states[type][name] = state

        if type == 'switch':

            widget = self.device_tree.ids['{}.{}'.format(type, name)]
            state = self.device_states[type][name]['state']

            if state:
                widget.bold = True
                widget.color = [1, 0, 0, 1]
            else:
                widget.bold = False
                widget.color = [1, 1, 1, 1]

        elif type == 'led':

            widget = self.device_tree.ids['{}.{}'.format(type, name)]
            color = self.device_states[type][name]['_color']

            widget.update_states(self.device_states[type][name])

            if type == 'led' and name == 'l_mystery':
                self.pf_widget.update(self.device_states[type][name])

    def device_clicked(self, widget, motion_event):

        if motion_event.button == 'left':

            # type, name = widget.id.split('.')

            print(motion_event)

        elif motion_event.button == 'right':
            # self.bubble = Bubble()
            # self.bubble.add_widget(BubbleButton(text='Hit'))
            # self.bubble.add_widget(BubbleButton(text='Toggle'))
            # widget.add_widget(self.bubble)
            print(motion_event)

    def on_stop(self):
        self.log.info("Stopping...")
        self.thread_stopper.set()
        self.bcp.disconnect()

class SwitchLabel(RelativeLayout, TreeViewLabel):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas:
            Color(1, 0, 0, 1)
            RoundedRectangle(pos=(150, 8), size=(10,10), radius=[5, 5])

    def update_states(self, state_dict):
        self.canvas.clear()

        with self.canvas:
            Color(0,1,0)
            RoundedRectangle(pos=(150, 8), size=(10,10), radius=[5, 5])


class LedLabel(DragBehavior, RelativeLayout, TreeViewLabel):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas:
            Color(1, 0, 0, 1)
            self.rec = RoundedRectangle(pos=(150, 8), size=(10,10), radius=[5,
                                                                          5])

    def update_states(self, state_dict):
        self.canvas.remove(self.rec)

        with self.canvas:
            Color(state_dict['_color'][0]/255,
                  state_dict['_color'][1]/255,
                  state_dict['_color'][2]/255)
            self.rec = RoundedRectangle(
                pos=(150, 8), size=(10,10), radius=[5, 5])

    # def on_touch_down(self, touch):
    #     print(self.children[0].text, touch)
    #
    # def on_touch_up(self, touch):
    #     print(self.children[0].text, touch)

    # def on_touch_move(self, touch):
    #     print(self.children[0].text, touch, self.collide_point(touch.pos[0], touch.pos[1]))

class LedPlayfield(DragBehavior, Widget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas:
            Color(1, 0, 0, 1)
            self.rec = RoundedRectangle(pos=(100,100), size=(10,10), radius=[
                5,5])

    def update(self, state_dict):
        self.canvas.clear()

        with self.canvas:
            Color(state_dict['_color'][0]/255,
                  state_dict['_color'][1]/255,
                  state_dict['_color'][2]/255)
            self.rec = RoundedRectangle(pos=(100,100), size=(10,10), radius=[
                5, 5])

    # def on_touch_move(self, touch):
    #     print("move", self, touch, self.collide_point(touch.pos[0],
    #                                                  touch.pos[1]))
    #
    # def on_touch_down(self, touch):
    #     print("click", self, touch)
    #
    # def on_touch_up(self, touch):
    #     print("release", self, touch)

device_classes = {'switch': SwitchLabel,
                  'led': LedLabel}
# device_classes = {}

class LedWidget():
    pass

