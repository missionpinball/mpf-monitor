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
from mpfmonitor._version import __version__

# import functiontrace
# functiontrace.trace()

class Command(object):

    # pylint: disable-msg=too-many-locals
    def __init__(self, mpf_path, machine_path, args):

        # Need to have these in here because we don't want them to load when
        # the module is loaded as an mpf.command
        from mpf.core.utility_functions import Util

        del mpf_path

        parser = argparse.ArgumentParser(description='Starts the MPF Monitor')

        parser.add_argument("-l",
                            action="store", dest="logfile",
                            metavar='file_name',
                            default=os.path.join("logs", datetime.now().strftime(
                                "%Y-%m-%d-%H-%M-%S-monitor-" +
                                socket.gethostname() + ".log")),
                            help="The name (and path) of the log file")

        parser.add_argument("-c",
                            action="store", dest="configfile",
                            default="monitor", metavar='config_file(s)',
                            help="The name of a config file to load. Note "
                                 "this is a config for the monitor itself, "
                                 "not an MPF config.yaml. Default is monitor.")

        parser.add_argument("-i",
                            action="extend", nargs="+", dest="image_files",
                            default=[],  # Default for lists must be implemented by custom check
                            metavar='image_files',
                            help="The MPF Monitor image file name. "
                                 "Files must be placed within the folder '<game>/monitor/' "
                                 "Default is playfield.jpg\n"
                                 "Use `-i=image1.jpg image2.png` to add multiple options.\n"
                                 "Supported types: PNG, JPG, BMP, GIF")

        parser.add_argument("-is",
                            action="store_true", dest="all_images",
                            default=False, help="Load all PNG, JPG, BMP, GIF files in '<game>/monitor/'")

        parser.add_argument("-v",
                            action="store_const", dest="loglevel", const=logging.DEBUG,
                            default=logging.INFO, help="Enables verbose logging to the log file")

        parser.add_argument("-V",
                            action="store_true", dest="consoleloglevel",
                            default=logging.INFO,
                            help="Enables verbose logging to the console. Do NOT use on Windows platforms")

        parser.add_argument("-ip",
                            action="store", dest="mpfipaddr",
                            help="The MPF IP Address Default is localhost")

        parser.add_argument("-port",
                            action="store", dest="mpfport",
                            help="The MPF Port Default is 5051")

        args = parser.parse_args(args)
        args.configfile = "{}.yaml".format(args.configfile)

        # Configure logging. Creates a logfile and logs to the console.
        # Formatting options are documented here:
        # https://docs.python.org/2.7/library/logging.html#logrecord-attributes

        try:
            os.makedirs(os.path.join(machine_path, 'logs'))
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise

        logging.basicConfig(level=args.loglevel,
                            format='%(asctime)s : %(levelname)s : %(name)s : %(message)s',
                            filename=os.path.join(machine_path, args.logfile),
                            filemode='w')

        # define a Handler which writes INFO messages or higher to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(args.consoleloglevel)

        # set a format which is simpler for console use
        formatter = logging.Formatter('%(levelname)s : %(name)s : %(message)s')

        # tell the handler to use this format
        console.setFormatter(formatter)

        # add the handler to the root logger
        logging.getLogger('').addHandler(console)

        from mpfmonitor.core.mpfmon import run

        logging.info("Loading MPF Monitor Version {}".format(__version__))

        thread_stopper = threading.Event()

        resolved_images = list(args.image_files)

        # Handle automatic folder scanning if `-is` flag is provided
        if args.all_images:
            monitor_dir = os.path.join(machine_path, 'monitor')
            valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
            if os.path.exists(monitor_dir):
                discovered = [
                    entry.name for entry in os.scandir(monitor_dir)
                    if entry.is_file() and entry.name.lower().endswith(valid_exts)
                ]
                resolved_images.extend(discovered)

        if not resolved_images:
            resolved_images = ["playfield.jpg"]
        else:
            resolved_images.sort(key=lambda path: os.path.basename(path).lower())

        try:
            run(machine_path=machine_path,
                thread_stopper=thread_stopper,
                config_file=args.configfile,
                image_files=resolved_images,
                ip_addr=args.mpfipaddr,
                port=args.mpfport)
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
