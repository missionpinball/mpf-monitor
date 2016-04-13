We'll kick off the mpf-monitor project after MPF 0.30 is done, but in the meantime we started this repo to have a place
to collect ideas.

MPF Monitor will be a GUI app that connects to a live running MPF instance.

* All communication will be via BCP. We’ll have to add some stuff to it to support this, but that’s fine and will be nice since people could use it for other things too.
* Want to make it so the monitor can run and stay open, even as MPF stops and starts, so maybe monitor runs on a set port and then when MPF starts, it tries to connect to the monitor automatically (and fails silently if not).
* Set a background image for the playfield. Have a slider to set how bright the playfield image is so you can see the lights easier.
* Drag and drop devices onto the PF where they can be interacted with.
* Possibly different layers for different types of devices.
* Click on a switch to activate the switch. Maybe right-click to toggle.
* Set insert shape and color
* Right-click on a device to view its properties, both from the config and device-specific properties (current values of attributes)
* Player section shows player as well as the values of all player vars
* Mode section shows all modes, whether they’re active or not, mode-specific attributes
* Logic blocks, timers, etc.
* Events section shows X most recent posted events, can show registered handlers
* Export/save a paused state for troubleshooting purposes
* Clock section shows scheduled clock events
* Pause button can pause the entire machine. (Will be complex to do. Probably it should go into a blocking subroutine that manually calls the BCP events needed to keep the connection alive) I think we'll have to pause the clock and use our own routine. Will also have to figure out how to pause the mc.
* Shows section shows currently running shows, priorities, show queue, etc.
* Also have the ability to connect to the MC to show current slides, screen space light shows, FBOs, sounds, etc.
* Change debug levels dynamically
* Will need to have a plugin in MPF which sends/receives the data in the way the monitor needs it.
* Layout & config information for monitor can be in a YAML file, but it can also pull much of what it needs directly from config files and/or the running instance of MPF.
* Enter a config for a mode which can be dynamically added to the game.

Changes to MPF
* Will register as a plugin, so we need to make MPF plugins use standard entry points.
* Need to change MPF so it can connect to multiple servers at the same time, and so MPF can listen for incoming connections.
