"""BCP Server interface for the MPF Media Controller"""

import logging
import queue
import socket
import threading
import os

import select

from datetime import datetime
import math

import mpf.core.bcp.bcp_socket_client as bcp
from PyQt6.QtCore import QTimer


class BCPClient(object):

    def __init__(self, mpfmon, receiving_queue, sending_queue,
                 interface='localhost', port=5051, simulate=False, cache=False):

        self.mpfmon = mpfmon
        self.log = logging.getLogger('BCP Client')
        self.interface = interface
        self.port = port
        self.receive_queue = receiving_queue
        self.sending_queue = sending_queue
        self.connected = False
        self.socket = None
        self.sending_thread = None
        self.receive_thread = None
        self.done = False
        self.last_time = datetime.now()

        self.simulate = simulate
        self.caching_enabled = cache

        try:
            self.cache_file_location = os.path.join(self.mpfmon.machine_path, "monitor", "cache.txt")
        except FileNotFoundError:
            self.simulate = False
            self.caching_enabled = False

        self.mpfmon.log.info('Looking for MPF at %s:%s', self.interface, self.port)

        self.reconnect_timer = QTimer(self.mpfmon.device_window)
        self.simulator_timer = QTimer(self.mpfmon.device_window)


        self.simulator_messages = []
        self.simulator_msg_timer = []
        self.enable_simulator(enable=self.simulate)

    def register_timer(self):
        if self.simulate:
            self.reconnect_timer.stop()

            self.simulator_init()

            self.simulator_timer.setInterval(100)
            self.simulator_timer.timeout.connect(self.simulate_received)
            self.simulator_timer.start()
        else:
            self.simulator_timer.stop()

            self.reconnect_timer.setInterval(1000)
            self.reconnect_timer.timeout.connect(self.connect_to_mpf)
            self.reconnect_timer.start()

    def enable_simulator(self, enable=True):
        if enable:
            self.simulate = True
            if self.caching_enabled:
                try:
                    self.cache_file = open(self.cache_file_location, "r")
                except FileNotFoundError:
                    self.log.warn("Caching enabled but no cache file found.")
                    self.simulate = False
                    self.caching_enabled = False
                    self.enable_simulator(False)
        else:
            self.simulate = False
            if self.caching_enabled:
                self.cache_file = open(self.cache_file_location, "w")

        self.start_time = datetime.now()
        self.register_timer()

    def connect_to_mpf(self, *args):
        del args

        if self.connected:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.connect((self.interface, self.port))
            self.connected = True
            # self.mc.reset_connection()
            self.log.info("Connected to MPF")

        except socket.error:
            self.socket = None

        if self.create_socket_threads():
            self.start_monitoring()

    def start_monitoring(self):
        self.sending_queue.put('monitor_start?category=devices')
        self.sending_queue.put('monitor_start?category=events')
        self.sending_queue.put('monitor_start?category=modes')
        self.sending_queue.put('monitor_start?category=machine_vars')
        self.sending_queue.put('monitor_start?category=player_vars')

    def create_socket_threads(self):
        """Creates and starts the sending and receiving threads for the BCP
        socket.
        Returns:
            True if the socket exists and the threads were started. False if
            not.
        """

        if self.socket:

            self.receive_thread = threading.Thread(target=self.receive_loop)
            # self.receive_thread.daemon = True
            self.receive_thread.start()

            self.sending_thread = threading.Thread(target=self.sending_loop)
            # self.sending_thread.daemon = True
            self.sending_thread.start()

            return True

        else:
            return False

    def receive_loop(self):
        """The socket thread's run loop."""
        socket_chars = b''
        while self.connected and not self.mpfmon.thread_stopper.is_set():
            try:
                ready = select.select([self.socket], [], [], 1)
                if ready[0]:
                    data_read = self.socket.recv(8192)
                    if data_read:
                        socket_chars += data_read
                        commands = socket_chars.split(b"\n")

                        # keep last incomplete command
                        socket_chars = commands.pop()

                        # process all complete commands
                        for cmd in commands:
                            if cmd:
                                self.process_received_message(cmd.decode())
                    else:
                        # no bytes -> socket closed
                        break

            except socket.timeout:
                pass

            except OSError:
                break

        self.connected = False

    def disconnect(self):
        if not self.connected:
            self.log.info("Disconnecting from BCP")
            self.sending_queue.put('goodbye', None)

    def close(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()

        except (OSError, AttributeError):
            pass

        if self.caching_enabled:
            self.cache_file.close()

        self.socket = None
        self.connected = False

        with self.receive_queue.mutex:
            self.receive_queue.queue.clear()

        with self.sending_queue.mutex:
            self.sending_queue.queue.clear()

    def sending_loop(self):
        while self.connected and not self.mpfmon.thread_stopper.is_set():
            try:
                msg = self.sending_queue.get(block=True, timeout=1)
            except queue.Empty:
                if self.mpfmon.thread_stopper.is_set():
                    return

                else:
                    continue

            self.socket.sendall(('{}\n'.format(msg)).encode('utf-8'))

        self.connected = False

    def process_received_message(self, message):
        """Puts a received BCP message into the receiving queue.

        Args:
            message: The incoming BCP message

        """
        self.log.debug('Received "%s"', message)
        if self.caching_enabled and not self.simulate:
            time = datetime.now() - self.last_time
            message_tmr = math.floor(time.microseconds / 1000)
            self.last_time = datetime.now()
            self.cache_file.write(str(message_tmr) + "," + message + "\n")

        try:
            cmd, kwargs = bcp.decode_command_string(message)
            self.receive_queue.put((cmd, kwargs))
        except ValueError:
            self.log.error("DECODE BCP ERROR. Message: %s", message)
            raise

    def send(self, bcp_command, **kwargs):
            self.sending_queue.put(bcp.encode_command_string(bcp_command,
                                                             **kwargs))

    def simulator_init(self):
        if self.caching_enabled:
            self.simulator_msg_timer.append(int(0))
            for message in self.cache_file:
                message_tmr = int(message.split(',', 1)[0])
                message_str = message.split(',', 1)[1]

                self.simulator_msg_timer.append(message_tmr)
                self.simulator_messages.append(message_str)
        else:
            messages = [
                'device?json={"type": "switch", "name": "s_start", "changes": false, "state": {"state": 0, "recycle_jitter_count": 0}}',
                'device?json={"type": "switch", "name": "s_trough_1", "changes": false, "state": {"state": 1, "recycle_jitter_count": 0}}',
                'device?json={"type": "light", "name": "l_shoot_again", "changes": ["color", [255, 255, 255], [0, 0, 0]], "state": {"color": [0, 0, 0]}}',
                'device?json={"type": "light", "name": "l_ball_save", "changes": ["color", [0, 0, 0], [255, 255, 255]], "state": {"color": [255, 255, 255]}}',
            ]
            self.simulator_messages = messages
            self.simulator_msg_timer = [100, 100, 100, 100]

    def simulate_received(self):
        if len(self.simulator_messages) > 0:
            next_message = self.simulator_messages.pop(0)
            timer = self.simulator_msg_timer.pop(0)
            self.simulator_timer.setInterval(timer)
            self.process_received_message(next_message)
        else:
            self.simulator_timer.stop()
            self.log.info("End of cached file reached.")
