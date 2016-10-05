MPF Monitor (mpf-monitor)
=========================

<img align="right" height="146" src="mpfmc/icons/mpfmc-logo.png"/>

This package is for Mission Pinball Framework (MPF) Monitor (mpf-monitor).

The MPF monitor is a graphical app that connects to a live running instance of MPF and shows the status of various devices.
(LEDs, switches, ball locks, etc.). You can add a picture of your playfield and drag-and-drop devices to their proper locations
so you can interact with your machine when you're not near your physical machine.

The MPF Monitor can run on Windows, Mac, and Linux. It uses PyQt5 (Python bindings for Qt5) for its visual framework.

Features
--------

* Connects to a live running instance of MPF.
* Automatically discovers all devices.
* Device state is updated in real time in the device tree view.
* Add a photo of your playfield.
* Drag and drop LEDs and switches from the device tree onto the playfield. LEDs (circle icons) show their color in real 
  time. Switches (square icons) show their state (green = active, black = inactive).
* Left-click on a switch to activate & release. Right-click on a switch to toggle and hold it.
* Devices added to the playfield image are saved & restored.
* Window sizes and positions are remembered and restored on next use.
* You can start the monitor and leave it running, and it will automatically connect
  & reconnect when MPF starts

Installation
------------

1. If you have Windows, first install this: https://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-5.5.1/ (Mac and Linux
  will install it automatically when mpf-monitor is installed.
2. Download / sync this repo.
3. Run one of the following commands from the repo folder on your computer. (The trailing dot is part of the command):
    * If you run MPF by running `mpf`, then run `pip install -e .`
    * If you run MPF by running `python3 -m mpf` then run `python3 -m pip install -e .`
    * If you run MPF by running `kivy -m mpf` then run `kivy -m pip install -e .`
4. The `-e` option means that this package is installed in "editable" mode, meaning that you can pull/sync the mpf-monitor
  repo to update your mpf-monitor installation. This is useful in MPF monitor's early stages as it will change often.

Running MPF Monitor
-------------------

1. Create a subfolder in your MPF machine folder called `monitor`
2. Put an image of your playfield in that folder named `playfield.jpg`
3. Run MPF monitor from a command prompt in a new window in the same way you run "mc" or "both", just use the word
   "monitor" instead. (So `mpf monitor` or `kivy -m monitor` or whatever you use)
4. Start MPF and MPF-MC. (You can start MPF before or after monitor is started, and leave
   the monitor running while MPF is not.)
5. MPF Monitor should connect to MPF and populate the devices tree. You can look through there to see the states of
   various devices. The columns are sortable and resizeable.
6. Drag-and-drop switches and LEDs onto the playfield image. When you do this, a config file called `monitor.yaml` will
   be created in your machine's `monitor` folder. x/y values of devices are stored in percentages instead of pixels, so 
   they should stay in the right place even if you change your playfield image. The yaml file is updated automatically.
7. Edit the YAML file to remove devices from the playfield you don't want anymore.
8. Window size and position is saved to `monitor/layout.yaml`. Exclude this from your game repo (via .gitignore) if you use
   multiple computers and want to save a custom layout per computer.

Future Features
---------------

MPF Monitor is *very* rough at this point. In the near future (after Expo 2016), we'll add
more features, including:

* Events that have been posted, current registered handlers
* Pulling information about running modes (priority, etc.)
* Shots, shot groups, and shot profiles
* Logic blocks
* Timers
* Clock events
* Shows (running shows, step they're on, priority, etc.)
* Players (show all player vars and their values)
* A "snapshot" button that can dump the entire current state to a file
  for debugging later
* Export position (x/y) settings of widgets back to the MPF config
* Allow the monitor to stay running when MPF stops and automatically
  reconnect when MPF starts again
* Connect to MPF-MC to get information about slides, displays, widgets, etc.
* Add color controls to the playfield image to set brightness and color saturation
* Buttons to enable/disable different types of devices
* Show additional properties from the selected device
* Change debug levels of various devices dynamically
* Save config / layout with a specified file name
* Add multiple playfield views which could each have different devices
* Set colors, shapes, rotation, & sizes of devices (so inserts can be the
  right shape). Allow configurable "off" colors which can include opacity
  and "glow" so inserts look like real lights.
* Allow all devices to be added to the playfield image, with custom
  representation (diverters that animate, flippers that animate, etc.).
* Device state change history that shows what properties changed and when.
* Default (mostly blank) playfield image if no playfield image is specified
* Configurable default options (folder location, playfield image name, etc.)

License
-------
* MPF and the MPF Monitor are released under the terms of the MIT License. Please refer to the LICENSE file for details.
* The MIT license basically means you can do anything you want with MPF, including using it for commercial projects.
  You don't have to pay us or share your changes if you don't want to.
