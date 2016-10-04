"""Starts the MPF Monitor."""

import argparse
import logging
import os
import socket
import sys
import threading
from datetime import datetime
import time

import errno


class Command(object):

    # pylint: disable-msg=too-many-locals
    def __init__(self, mpf_path, machine_path, args):

        # Need to have these in here because we don't want them to load when
        # the module is loaded as an mpf.command
        import mpfmonitor
        from mpf.core.utility_functions import Util
        from mpfmc.core.config_processor import ConfigProcessor
        from mpfmc.core.utils import set_machine_path, load_machine_config

        del mpf_path

        parser = argparse.ArgumentParser(description='Starts the MPF Monitor')

        parser.add_argument("-l",
                            action="store", dest="logfile",
                            metavar='file_name',
                            default=os.path.join("logs", datetime.now().strftime(
                                "%Y-%m-%d-%H-%M-%S-monitor-" +
                                socket.gethostname() +
                                ".log")),
                            help="The name (and path) of the log file")

        parser.add_argument("-c",
                            action="store", dest="configfile",
                            default="monitor", metavar='config_file(s)',
                            help="The name of a config file to load. Note "
                                 "this is a config for the monitor itself, "
                                 "not an MPF config.yaml. Default is "
                                 "monitor.yaml. Multiple files can be used "
                                 "via a comma-separated list (no spaces between)")

        parser.add_argument("-v",
                            action="store_const", dest="loglevel", const=logging.DEBUG,
                            default=logging.INFO, help="Enables verbose logging to the"
                                                       " log file")

        parser.add_argument("-V",
                            action="store_true", dest="consoleloglevel",
                            default=logging.INFO,
                            help="Enables verbose logging to the console. Do NOT on "
                                 "Windows platforms")

        parser.add_argument("-C",
                            action="store", dest="mpfmonconfigfile",
                            default="mpfmonitor.yaml",
                            metavar='config_file',
                            help="The MPF Monitor default config file. "
                                 "Default is <mpf-monitor install "
                                 "folder>/mpfmonitor.yaml")

        args = parser.parse_args(args)

        args.configfile = Util.string_to_list(args.configfile)

        # Configure logging. Creates a logfile and logs to the console.
        # Formatting options are documented here:
        # https://docs.python.org/2.7/library/logging.html#logrecord-attributes

        try:
            os.makedirs(os.path.join(machine_path, 'logs'))
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise

        logging.basicConfig(level=args.loglevel,
                            format='%(asctime)s : %(levelname)s : %(name)s : '
                                   '%(message)s',
                            filename=os.path.join(machine_path, args.logfile),
                            filemode='w')

        # define a Handler which writes INFO messages or higher to the
        # sys.stderr
        console = logging.StreamHandler()
        console.setLevel(args.consoleloglevel)

        # set a format which is simpler for console use
        formatter = logging.Formatter('%(levelname)s : %(name)s : %(message)s')

        # tell the handler to use this format
        console.setFormatter(formatter)

        # add the handler to the root logger
        logging.getLogger('').addHandler(console)

        from mpfmonitor.core.mpfmon import run

        logging.info("Loading MPF Monitor")

        thread_stopper = threading.Event()

        try:
            run(machine_path=machine_path, thread_stopper=thread_stopper)
            logging.info("MPF Monitor run loop ended.")
        except Exception as e:
            logging.exception(str(e))

        logging.info("Stopping child threads... (%s remaining)",
                     len(threading.enumerate()) - 1)

        thread_stopper.set()

        while len(threading.enumerate()) > 1:
            time.sleep(.1)

        logging.info("All child threads stopped.")

        sys.exit()


def get_command():
    return 'monitor', Command
