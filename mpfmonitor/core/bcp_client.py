"""BCP Server interface for the MPF Media Controller"""

import logging
import queue
import socket
import threading

import select

import mpf.core.bcp.bcp_socket_client as bcp
from PyQt5.QtCore import QTimer


class BCPClient(object):

    def __init__(self, mc, receiving_queue, sending_queue,
                 interface='localhost', port=5051):

        self.mc = mc
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

        self.mc.log.info('Looking for MPF at %s:%s', self.interface, self.port)

        self.reconnect_timer = QTimer(self.mc)
        self.reconnect_timer.setInterval(1000)
        self.reconnect_timer.timeout.connect(self.connect_to_mpf)
        self.reconnect_timer.start()

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
        self.sending_queue.put('monitor_devices')
        self.sending_queue.put('monitor_events')

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
        while self.connected and not self.mc.thread_stopper.is_set():

            socket_chars = b''

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

        self.socket = None
        self.connected = False

        with self.receive_queue.mutex:
            self.receive_queue.queue.clear()

        with self.sending_queue.mutex:
            self.sending_queue.queue.clear()

    def sending_loop(self):
        while self.connected and not self.mc.thread_stopper.is_set():
            try:
                msg = self.sending_queue.get(block=True, timeout=1)
            except queue.Empty:
                if self.mc.thread_stopper.is_set():
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

        try:
            cmd, kwargs = bcp.decode_command_string(message)
            self.receive_queue.put((cmd, kwargs))
        except ValueError:
            self.log.error("DECODE BCP ERROR. Message: %s", message)
            raise

    def send(self, bcp_command, **kwargs):
            self.sending_queue.put(bcp.encode_command_string(bcp_command,
                                                             **kwargs))
