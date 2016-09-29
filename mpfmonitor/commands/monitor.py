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

# Note, other imports are done deeper in this file, which we need to do there
# since Kivy does so much with singletons and we don't want MPF to import
# them when it reads this command


class Command(object):

    # pylint: disable-msg=too-many-locals
    def __init__(self, mpf_path, machine_path, args):

        # undo all of Kivy's built-in logging so we can do it our way
        os.environ['KIVY_NO_FILELOG'] = '1'
        os.environ['KIVY_NO_CONSOLELOG'] = '1'
        from kivy.logger import Logger

        for handler in Logger.handlers:
            Logger.removeHandler(handler)
        sys.stderr = sys.__stderr__

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

        # mpf_config = ConfigProcessor.load_config_file(os.path.join(
        #     mpfmonitor.__path__, args.mpfmonconfigfile), 'machine')
        #
        # machine_path = set_machine_path(machine_path,
        #                                 mpf_config['mpf_monitor']['paths'][
        #                                     'machine_files'])
        #
        # mpf_config = load_machine_config(args.configfile, machine_path,
        #                                  mpf_config['mpf_monitor']['paths'][
        #                                      'config'], mpf_config)
        #
        # self.preprocess_config(mpf_config)

        from mpfmonitor.core.mpfmon import run

        logging.info("Loading MPF Monitor")

        thread_stopper = threading.Event()

        try:
            # MpfMon(options=vars(args), config=mpf_config,
            #       machine_path=machine_path,
            #       thread_stopper=thread_stopper).run()
            run()
            logging.info("MPF Monitor run loop ended.")
        except Exception as e:
            logging.exception(str(e))

        logging.info("Stopping child threads... (%s remaining)", len(threading.enumerate()) - 1)

        thread_stopper.set()

        while len(threading.enumerate()) > 1:
            time.sleep(.1)

        logging.info("All child threads stopped.")

        sys.exit()

    def preprocess_config(self, config):
        from kivy.config import Config

        kivy_config = config['kivy_config']

        try:
            kivy_config['graphics'].update(config['window'])
        except KeyError:
            pass

        if ('top' in kivy_config['graphics'] and
                'left' in kivy_config['graphics']):
            kivy_config['graphics']['position'] = 'custom'

        for section, settings in kivy_config.items():
            for k, v in settings.items():
                try:
                    if k in Config[section]:
                        Config.set(section, k, v)
                except KeyError:
                    continue

        try:  # config not validated yet, so we use try
            if config['window']['exit_on_escape']:
                Config.set('kivy', 'exit_on_escape', '1')
        except KeyError:
            pass

        Config.set('graphics', 'maxfps', int(config['monitor']['fps']))


def get_command():
    return 'monitor', Command
