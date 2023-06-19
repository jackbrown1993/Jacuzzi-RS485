""" Provides a text-mode windowing user interface for jacuzziRS485.py. """

import sys
import argparse

# Create an argument parser
parser = argparse.ArgumentParser()

# Add an IP address argument
parser.add_argument("--ip", type=str, help="IP address")
parser.add_argument("--port", type=int, help="Port number", default=4257)

# Parse the arguments
args = parser.parse_args()

# Access the IP address argument
jacuzzi_ip_address = args.ip
jacuzzi_port = args.port

# Check if IP address is provided
if not jacuzzi_ip_address:
    print(
        "Error: Please provide an IP address for Jacuzzi using the --ip flag. eg. python3 ui_app.py --ip 192.168.1.125"
    )
    sys.exit(1)

try:
    import jacuzziRS485
except ImportError:
    import jacuzziRS485 as jacuzziRS485

# These are the specific CursesUI identifiers that this application
# references.
try:
    from cursesui import (
        log,
        Align,
        Textfield,
        KeyResponse,
        SubWindow,
        PadWindow,
        EditDialog,
        EnumDialog,
        ListDialog,
        TextDialog,
    )
except ImportError:
    print("Could not import something needed from cursesui.py!")
    exit()

import curses.ascii  # Provides useful key value constants

from enum import Enum
import time
import random


def setup_ui_display(spa_ui):
    """Defines all the Windows for the Jacuzzi Spa UI."""
    # Create a SubWindow instance for menu messages
    menuwin = SubWindow(spa_ui.display, 15, 30, 2, 2, "Menu")

    # Add some static menu items to the menu Window.
    #
    # These never change so they do not need update
    # callback functions. Note that you can also
    # use a single Textfield to display multiple
    # lines of text. Any empty, trailing newlines
    # will be stripped from your text.
    menurow = menuwin.get_first_row() + 1
    menucol = menuwin.get_center_col()
    menu1 = (
        "Press <Tab> to select next\n"
        "<Enter> to go in selected\n"
        "<Esc> to go back out\n"
        "Ctrl-p adds a message\n"
        "Arrows scroll messages\n"
        "Resize at will\n"
        "Ctrl-x to exit"
    )
    menu1field = Textfield(menurow, menucol, Align.CENTER)
    menu1field.write(menu1)
    menuwin.add_field(menu1field)

    # The menu Window is read-only so make it unselectable
    menuwin.set_selectable(False)

    # Create a SubWindow for current status. Position it
    # relative to the menu Window.
    row = menuwin.get_top_edge_row()
    col = menuwin.get_right_edge_col() + 2
    stswin = SubWindow(spa_ui.display, 15, 30, row, col, "Status")

    # The status Window is read-only so make it unselectable
    stswin.set_selectable(False)

    # Add current spa time to the Status Window.
    row = stswin.get_first_row()
    col = stswin.get_center_col()
    timefield = Textfield(row, col, Align.CENTER)

    def _get_current_time_text():
        return "{0}".format(time.asctime(time.localtime(time.time())))

    timefield.set_update_cb(_get_current_time_text)
    stswin.add_field(timefield)
    timefield.update()
    row += timefield.get_required_rows()

    # Add spa time to the Status Window.
    spatimefield = Textfield(row, col, Align.CENTER)
    spatimefield.set_update_cb(spa.get_spatime_text)
    stswin.add_field(spatimefield)
    spatimefield.update()
    row += spatimefield.get_required_rows()

    # Add the hot tub connection state to the status
    # Window.
    cnctfield = Textfield(row, col, Align.CENTER)
    cnctfield.set_update_cb(spa.get_connection_state_text)
    stswin.add_field(cnctfield)
    cnctfield.update()
    row += cnctfield.get_required_rows()

    # Add the lastupd to the status
    # Window.
    lastupdatefield = Textfield(row, col, Align.CENTER)
    lastupdatefield.set_update_cb(spa.get_last_update_text)
    stswin.add_field(lastupdatefield)
    lastupdatefield.update()
    row += lastupdatefield.get_required_rows()

    # Add the current water temperature to the status
    # Window.
    row += 1
    col = stswin.get_first_col()
    tempfield = Textfield(row, col)
    tempfield.set_update_cb(spa.get_curtemp_text)
    stswin.add_field(tempfield)
    tempfield.update()
    row += tempfield.get_required_rows()

    def _get_pump1_text():
        # A local routine to get current pump 1 status
        return "Pump 1: {0}".format(spa.get_pump(1, True))

    # Add current spa pump 1 value to the status window.
    pump1field = Textfield(row, col)
    pump1field.set_update_cb(_get_pump1_text)
    stswin.add_field(pump1field)
    pump1field.update()
    flowrow = row
    flowcol = pump1field.get_required_cols() + 3
    row += pump1field.get_required_rows()

    def _get_flow_text():
        # A local routine to get current flow status
        return "Flow: {0}".format("On" if spa.statusByte17 else "Off")

    # Add current flow status to the status window.
    flowfield = Textfield(flowrow, flowcol)
    flowfield.set_update_cb(_get_flow_text)
    stswin.add_field(flowfield)
    flowfield.update()

    # Jacuzzi spas return a pump status of 0x02 when pump
    # 2 is On, which means the text returned by get_pump()
    # is "High". Since pump 2 has only 2 states (On or Off)
    # we use this local string array instead.

    _pump2_text = ["Off", "On", "On"]

    def _get_pump2_text():
        # A local routine to get current pump 2 status
        return "Pump 2: {0}".format(_pump2_text[spa.get_pump(2, False)])

    # Add current spa pump 2 value to the status window.
    pump2field = Textfield(row, col)
    pump2field.set_update_cb(_get_pump2_text)
    stswin.add_field(pump2field)
    pump2field.update()
    row += pump2field.get_required_rows()

    def _get_uvon_text():
        # A local routine to get current UV lamp status
        return "UV (ClearRay): {0}".format("On" if spa.isUVOn else "Off")

    # Add current spa UV value to the status window.
    uvonfield = Textfield(row, col)
    uvonfield.set_update_cb(_get_uvon_text)
    stswin.add_field(uvonfield)
    uvonfield.update()
    row += uvonfield.get_required_rows()

    def _get_primary_text():
        # A local routine to get primary filter cycle state
        return "On" if spa.isPrimaryOn else "Off"

    def _get_secondary_text():
        # A local routine to get secondary filter cycle state
        return "On" if spa.isSecondaryOn else "Off"

    def _get_filters_text():
        # Returns both primary and secondary filter texts
        return "Pri: {0} Sec: {1}".format(_get_primary_text(), _get_secondary_text())

    # Add current Primary and Secondary filter states to the status window.
    filterfield = Textfield(row, col)
    filterfield.set_update_cb(_get_filters_text)
    stswin.add_field(filterfield)
    filterfield.update()
    row += filterfield.get_required_rows()

    def _get_filtermode_cb():
        # A local callback to get current filter mode
        return "Filter: {0}".format(spa.get_filtermode(True))

    # Add current spa filter cycle mode value to the status window.
    cyclefield = Textfield(row, col)
    cyclefield.set_update_cb(_get_filtermode_cb)
    stswin.add_field(cyclefield)
    cyclefield.update()
    row += cyclefield.get_required_rows()

    _light_mode_names = [
        "Off",
        "Unk1",
        "Blu",
        "Grn",
        "Unk4",
        "Org",
        "Red",
        "Vio",
        "Unk8",
        "Aqua",
        "Blnd",
    ]

    def _get_light_mode_text():
        # Returns just the light mode text.
        light_mode = spa.get_lightMode()
        # Convert blend mode value to a list index
        if light_mode == 0x80:
            light_mode = 10
        return "Lights:{0}".format(_light_mode_names[light_mode])

    def _get_brightness_text():
        # Returns just the brightness text.
        return "Brightness:{0}%".format(spa.get_lightBrightness())

    def _get_full_light_cb():
        # Returns both light mode and brightness text
        return "{0} {1}".format(_get_light_mode_text(), _get_brightness_text())

    # Add full light mode text to the status window.
    lightfield = Textfield(row, col)
    lightfield.set_update_cb(_get_full_light_cb)
    stswin.add_field(lightfield)
    lightfield.update()

    # The color swatch will be on the same row
    # as the mode and brightness level text.
    swatchrow = row
    row += lightfield.get_required_rows()

    # Need to add 4 to prevent the color swatch Textfield
    # from overlapping the light mode Textfield.
    swatchcol = lightfield.get_required_cols() + 4

    # Initialize the curses color info
    light_color_pair = spa_ui.total_color_pairs - 1

    spa.log.info(
        "Colors: {0} Pair: {1} Has Color: {2} Can Change: {3}".format(
            spa_ui.total_color_numbers,
            light_color_pair,
            spa_ui.has_colors,
            spa_ui.can_change_color,
        )
    )

    # When TERM=xterm, can_change_color is False even though
    # has_colors is True and total_color_numbers = 8, while
    # light_color_pair gets assigned pair 63. In this situation
    # a call to init_pair() will fail, so we will only set up
    # the color swatch Textfield when both has_colors and
    # can_change_color are True.

    if spa_ui.has_colors and spa_ui.can_change_color:

        def _set_light_color():
            # Assigns a new color number to the Textfield
            # that displays the current spa LED color, based
            # on the current RGB and brightness values sent
            # by the spa.
            #
            # Although curses can support direct RGB control
            # of displayed colors via init_color(), not all
            # terminals (notably puTTY) support that direct
            # control. However any terminal that supports the
            # TERM=xterm-256color standard will display a
            # fixed palette of colors which can approximate
            # an arbitrary RGB color value.
            #
            # We use that mapping of RGB to palette value
            # here to display the current state of the spa's
            # LED lights. Credit for the conversion routine
            # goes to Terrorbite (https://github.com/TerrorBite)
            # and RichardBronosky (https://gist.github.com/RichardBronosky)
            # from the discussion at https://gist.github.com/MicahElliott/719710

            y = spa.lightBrightness / 100  # Division converts to float
            red = int(y * spa.lightR)  # int() converts back to integer
            green = int(y * spa.lightG)
            blue = int(y * spa.lightB)

            # Default color levels for the color cube
            cubelevels = [0x00, 0x5F, 0x87, 0xAF, 0xD7, 0xFF]
            # Generate a list of midpoints of the above list
            snaps = [(x + y) / 2 for x, y in zip(cubelevels, [0] + cubelevels)][1:]

            def _rgb2short(r, g, b):
                # Converts RGB values to the nearest equivalent xterm-256 color.
                #
                # Using the list of snap points, convert RGB value to cube indexes
                r, g, b = map(
                    lambda x: len(tuple(s for s in snaps if s < x)), (r, g, b)
                )
                # Simple colorcube transform
                return r * 36 + g * 6 + b + 16

            colornum = _rgb2short(red, green, blue)

            # When TERM=xterm, this call fails because COLOR_WHITE is not found
            curses.init_pair(light_color_pair, curses.COLOR_WHITE, colornum)

        def _get_color_swatch_cb():
            # Updates the color pair for LED color display with the new color
            # attributes and then returns a short string of spaces to be used
            # as the color swatch.
            _set_light_color()
            return "  "

        # Add current spa lights color swatch to the status window.
        swatchfield = Textfield(swatchrow, swatchcol)
        swatchfield.set_update_cb(_get_color_swatch_cb)
        stswin.add_field(swatchfield)

        # Set up the color attributes for this Textfield
        #
        # Each time the color pair gets a new color, curses
        # will automatically update the attribute bits of this
        # Textfield. Thus there is no need to call add_attrs()
        # more than once.
        swatchfield.add_attrs(curses.color_pair(light_color_pair))

        # No need to call update() since the swatchfield is on the
        # same row as lightfield -- so row already points to the
        # next row.
        # swatchfield.update()

    # Create a SubWindow for values that the user can control.
    # Position it relative to the menu and status Windows.
    row = menuwin.get_top_edge_row()
    col = stswin.get_right_edge_col() + 2
    ctlwin = SubWindow(spa_ui.display, 15, 30, row, col, "Controls")

    # Add the temperature setpoint to the controls Window.
    row = ctlwin.get_first_row()
    col = ctlwin.get_first_col()
    tsetfield = Textfield(row, col)
    tsetfield.set_update_cb(spa.get_settemp_text)
    ctlwin.add_field(tsetfield)
    tsetfield.update()
    row += tsetfield.get_required_rows()

    def _change_settemp(newtemp):
        # This local routine starts an asynchronous task to send the
        # new temperature setpoint to the spa.
        #
        # Note that we use a lambda to include the newtemp parameter
        # with the coroutine.
        spa_ui.add_coroutine(lambda: spa.send_temp_change(newtemp))

    # Now add the dialog to the Textfield
    tsetdialog = EditDialog(
        spa_ui.display, "Enter the new setpoint\n" "temperature:", _change_settemp
    )
    tsetfield.set_dialog(tsetdialog)

        # Add pump 1 to the controls Window.
    pump1setfield = Textfield(row, col)
    pump1setfield.set_update_cb(_get_pump1_text)
    ctlwin.add_field(pump1setfield)
    pump1setfield.update()
    row += pump1setfield.get_required_rows()

    class Pump1States(Enum):
        """enum types for pump 1 states."""

        Off = 0
        Low = 1
        High = 2

    def _change_pump1(newstate):
        # This local routine starts an asynchronous task to send the
        # new pump 1 state to the spa.
        #
        # Note that we use a lambda to include the newstate parameter
        # with the coroutine.
        #
        # Since in this case newstate is a attribute of an instance of
        # an enum class, we need to convert it to an integer value before
        # passing it to change_pump().
        spa_ui.add_coroutine(lambda: spa.change_pump(1, newstate.value))

    # Now add the enum dialog to the Textfield
    pump1setdialog = EnumDialog(
        spa_ui.display, Pump1States, "Select the new state:", _change_pump1
    )
    pump1setfield.set_dialog(pump1setdialog)

    # Add pump 2 to the controls Window.
    pump2setfield = Textfield(row, col)
    pump2setfield.set_update_cb(_get_pump2_text)
    ctlwin.add_field(pump2setfield)
    pump2setfield.update()
    row += pump2setfield.get_required_rows()

    class Pump2States(Enum):
        """enum types for pump 2 states."""

        Off = 0
        On = 1

    def _change_pump2(newstate):
        # This local routine starts an asynchronous task to send the
        # new pump 2 state to the spa.
        #
        # Note that we use a lambda to include the newstate parameter
        # with the coroutine.
        spa_ui.add_coroutine(lambda: spa.change_pump(2, newstate))

    # Now add the list dialog to the Textfield
    pump2setdialog = ListDialog(
        spa_ui.display, _pump2_text, "Select the new state:", _change_pump2
    )
    pump2setfield.set_dialog(pump2setdialog)



    # Add spa time to the controls Window.
    timesetfield = Textfield(row, col)
    timesetfield.set_update_cb(spa.get_spatime_text)
    ctlwin.add_field(timesetfield)
    timesetfield.update()
    row += timesetfield.get_required_rows()

    def _change_spatime(time_text):
        # This local routine starts an asynchronous task to send the
        # new spa time to the spa.
        #
        # Note that we use a lambda to include the new_time parameter
        # with the coroutine.
        new_time = time.strptime(time_text, "%H:%M")
        spa_ui.add_coroutine(lambda: spa.set_time(new_time))

    # Now add the text dialog to the Textfield
    timesetdialog = TextDialog(
        spa_ui.display, "Enter time in hr:min format:", _change_spatime
    )
    timesetfield.set_dialog(timesetdialog)

    # Add spa date to the controls Window.
    datesetfield = Textfield(row, col)
    datesetfield.set_update_cb(spa.get_spadate_text)
    ctlwin.add_field(datesetfield)
    datesetfield.update()
    row += datesetfield.get_required_rows()

    def _change_spadate(date_text):
        # This local routine starts an asynchronous task to send the
        # new spa date to the spa.
        #
        # Note that we use a lambda to include the new_date parameter
        # with the coroutine.
        new_date = time.strptime(date_text, "%m/%d/%y")
        spa_ui.add_coroutine(lambda: spa.set_date(new_date))

    # Now add the text dialog to the Textfield
    datesetdialog = TextDialog(
        spa_ui.display, "Enter date in m/d/y format:", _change_spadate
    )
    datesetfield.set_dialog(datesetdialog)

    # Add light mode to the controls Window.
    lightsetfield = Textfield(row, col)
    lightsetfield.set_update_cb(_get_light_mode_text)
    ctlwin.add_field(lightsetfield)
    lightsetfield.update()
    brightrow = row

    # We need to add 3 to column value to make sure level
    # Textfield does not overlap with light mode Textfield.
    brightcol = lightsetfield.get_required_cols() + 3
    row += lightsetfield.get_required_rows()

    def _change_light_mode(newmode):
        # This local routine starts an asynchronous task to send the
        # new light state to the spa.
        #
        # The spa controller won't set the mode to Off; instead
        # we need to tell it to set the brightness to 0.
        if newmode == 0:
            _change_brightness(0)
            return

        # The spa controller also won't directly set the mode
        # to Blend. Instead the only way to put the spa lights
        # into blend mode is to turn the brightness from 0
        # to some other level.
        #
        # After we have started a coroutine to set the brightness
        # to zero, we can start another coroutine to set the
        # brightness to 100%. Since the second task cannot run
        # until the first has finished, this should always work.
        if newmode == 10:
            _change_brightness(0)
            _change_brightness(5)  # 20 * 5 = 100%
            return

        # For any other light mode just send the mode command
        # with the new mode value.
        spa_ui.add_coroutine(lambda: spa.change_light(newmode))

    # Now add the list dialog to the light mode Textfield
    lightsetdialog = ListDialog(
        spa_ui.display, _light_mode_names, "Select the new mode:", _change_light_mode
    )
    lightsetfield.set_dialog(lightsetdialog)

    _brightness_levels = ["Off", "20%", "40%", "60%", "80%", "100%"]

    # Add light brightness control to the controls Window.
    brightsetfield = Textfield(brightrow, brightcol)
    brightsetfield.set_update_cb(_get_brightness_text)
    ctlwin.add_field(brightsetfield)

    def _change_brightness(newlevelindex):
        # This local routine starts an asynchronous task to send the
        # new light brightness to the spa.
        #
        # If the light mode was off and new brightness level is
        # not 0, then the spa controller will also set the light mode
        # to blend.
        #
        # At no time should we ever call _change_light_mode() from
        # here because it can call _change_brightness() -- resulting
        # in infinite recursion.
        #
        # Convert the list index into brightness level
        newlevel = int(newlevelindex * 20)
        spa_ui.add_coroutine(lambda: spa.change_brightness(newlevel))

    # Now add the list dialog to the Textfield
    brightsetdialog = ListDialog(
        spa_ui.display, _brightness_levels, "Select the new brightness:", _change_brightness
    )
    brightsetfield.set_dialog(brightsetdialog)

    # Add primary filter cycle controls to the controls Window.

    def _get_cyc1hr_text():
        return "Cycle 1 Hr:{0}".format(spa.filter1StartHour)

    cyc1hrsetfield = Textfield(row, col)
    cyc1hrsetfield.set_update_cb(_get_cyc1hr_text)
    ctlwin.add_field(cyc1hrsetfield)
    cyc1hrsetfield.update()
    durationrow = row
    durationcol = cyc1hrsetfield.get_required_cols() + 3
    row += cyc1hrsetfield.get_required_rows()

    def _change_filter1_cyclehr(newhour):
        # This local routine starts an asynchronous task to send the
        # new primary filter cycle start hour to the spa.
        #
        # Note that we use a lambda to include the newhour parameter
        # with the coroutine.
        spa_ui.add_coroutine(
            lambda: spa.change_filter1_cycle(
                newhour, spa.filter1DurationHours, spa.filter1Freq
            )
        )

    # Now add the edit dialog to the Textfield
    cyc1hrsetdialog = EditDialog(
        spa_ui.display, "Enter the new start hour (24hr):", _change_filter1_cyclehr
    )
    cyc1hrsetfield.set_dialog(cyc1hrsetdialog)

    def _get_cyc1dur_text():
        return "Dur:{0}".format(spa.filter1DurationHours)

    cyc1dursetfield = Textfield(durationrow, durationcol)
    cyc1dursetfield.set_update_cb(_get_cyc1dur_text)
    ctlwin.add_field(cyc1dursetfield)
    cyc1dursetfield.update()
    freqrow = durationrow
    freqcol = durationcol + cyc1dursetfield.get_required_cols() + 2

    def _change_filter1_cycle_dur(newdur):
        # This local routine starts an asynchronous task to send the
        # new primary filter cycle duration hours to the spa.
        #
        # Note that we use a lambda to include the newdur parameter
        # with the coroutine.
        spa_ui.add_coroutine(
            lambda: spa.change_filter1_cycle(
                spa.filter1StartHour, newdur, spa.filter1Freq
            )
        )

    # Now add the edit dialog to the Textfield
    cyc1dursetdialog = EditDialog(
        spa_ui.display, "Enter the new duration (hours):", _change_filter1_cycle_dur
    )
    cyc1dursetfield.set_dialog(cyc1dursetdialog)

    def _get_cyc1freq_text():
        return "Freq:{0}".format(spa.filter1Freq)

    cyc1freqsetfield = Textfield(freqrow, freqcol)
    cyc1freqsetfield.set_update_cb(_get_cyc1freq_text)
    ctlwin.add_field(cyc1freqsetfield)

    def _change_filter1_cycle_freq(newfreq):
        # This local routine starts an asynchronous task to send the
        # new primary filter cycle duration hours to the spa.
        #
        # Note that we use a lambda to include the newfreq parameter
        # with the coroutine.
        spa_ui.add_coroutine(
            lambda: spa.change_filter1_cycle(
                spa.filter1StartHour, spa.filter1DurationHours, newfreq
            )
        )

    # Now add the edit dialog to the Textfield
    cyc1freqsetdialog = EditDialog(
        spa_ui.display, "Enter the new frequency (per day):", _change_filter1_cycle_freq
    )
    cyc1freqsetfield.set_dialog(cyc1freqsetdialog)

    # Add secondary filter cycle controls to the controls Window.
    #
    # This UI code works but the Secondary Filter Cycle does not
    # change in the spa controller.  This is also true with the
    # Prolink app -- so maybe this is an unimplemented feature??
    #
    # Update: While some Jacuzzi spas do support the Secondary
    # Filter Cycle feature, the J-235 does not.  This is why
    # the Prolink app does not seem to work. Maybe this UI code
    # will work with Jacuzzi hot tub models that have a Secondary
    # Filter Cycle feature?

    _cycle2_mode_names = ["Holiday", "Light", "Heavy"]

    def _get_cyc2mode_text():
        mode = spa.filter2Mode
        name = "Err" if mode < 0 or mode > 2 else _cycle2_mode_names[mode]
        return "Cycle 2:{0}".format(name)

    cyc2modesetfield = Textfield(row, col)
    cyc2modesetfield.set_update_cb(_get_cyc2mode_text)
    ctlwin.add_field(cyc2modesetfield)
    cyc2modesetfield.update()
    row += cyc2modesetfield.get_required_rows()

    def _change_filter2_mode(mode):
        # This local routine starts an asynchronous task to send the
        # new secondary filter cycle mode value to the spa.
        #
        # Note that we use a lambda to include the mode parameter
        # with the coroutine.
        spa_ui.add_coroutine(lambda: spa.change_filter2_cycle(mode))

    # Now add the edit dialog to the Textfield
    cyc2modesetdialog = ListDialog(
        spa_ui.display, _cycle2_mode_names, "Enter the new mode:", _change_filter2_mode
    )
    cyc2modesetfield.set_dialog(cyc2modesetdialog)

    # Create a PadWindow at the bottom for status messages.
    #
    # For PadWindows the width and height apply to the underlying
    # pad dimensions, which can be any size at all. Subtracting 2
    # here just accounts for the width of the right and left
    # borders, so that this pad should be fully visible in the
    # PadWindow's bordered viewport without needing to scroll
    # horizontally.
    # width = spa_ui.display.get_last_col() - 2
    width = 180

    # We'll choose to make the height of the pad equal to the
    # size of the TextBuffer that holds output sent to stdout
    # and stderr during the CursesUI session.
    height = spa_ui.stdout_bfr.get_maxlines()

    # Specify upper-left corner of the viewport.
    ulcrow = menuwin.get_bottom_edge_row() + 1
    ulccol = 1

    # Specify lower-right corner of the viewport.
    #
    # These make the Messages Window fill the entire bottom
    # section of the display Window at whatever its current size
    # is when the CursesUI instance starts.
    # lrcrow = spa_ui.display.get_last_row()
    # lrccol = spa_ui.display.get_last_col()
    #
    # These set a fixed height and width for the Messages Window
    lrcrow = ulcrow + 30
    lrccol = 96

    def _get_stdout_text():
        # A local update callback that displays in the Messages
        # Window any log messages and any output from calls to
        # print().
        return spa_ui.stdout_bfr.read()

    # Create the Messages PadWindow
    msgwin = PadWindow(
        spa_ui.display, height, width, ulcrow, ulccol, lrcrow, lrccol, "Messages"
    )

    # The Messages Window is read-only so make it unselectable
    msgwin.set_selectable(False)

    # Add a single Textfield that will display all message
    # lines in the stdout_bfr. Locate this Textfield at the
    # upper leftmost corner of the pad.
    msgfield = Textfield(0, 0)
    msgfield.set_update_cb(_get_stdout_text)
    msgwin.add_field(msgfield)

    # Uncomment this if you like to test attributes that
    # will apply to the entire Window and its contents:
    # msgwin.add_attrs(curses.A_REVERSE)

    # Create the KeyResponse instance for arrow keys.
    # These keys will scroll the contents of the Messages
    # Window.
    arrow_key_list = [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_RIGHT, curses.KEY_LEFT]
    arrow_keys = KeyResponse("arrows", arrow_key_list)

    # If we add this KeyResponse to the msgwin, then the
    # arrow keys will only be active while the msgwin is
    # selected.  If instead we add the KeyResponse instance
    # to the display Window, then the arrow keys will be
    # active during the entire CursesUI session. You can
    # test this by switching the comment character between
    # the two statements below.
    #
    # msgwin.add_key(arrow_keys)
    spa_ui.display.add_key(arrow_keys)

    def _kr_scroll_msgwin(keyhit):
        # This is a single local key response routine that
        # handles scrolling the Messages Window in any of
        # the 4 directions.
        if keyhit == curses.KEY_UP:
            msgwin.scroll_up()
        elif keyhit == curses.KEY_DOWN:
            msgwin.scroll_down()
        elif keyhit == curses.KEY_RIGHT:
            msgwin.scroll_right()
        elif keyhit == curses.KEY_LEFT:
            msgwin.scroll_left()

    # Bind the scrolling key response routine to the
    # arrow keys.
    arrow_keys.bind(_kr_scroll_msgwin)


def setup_ui_responses(spa_ui):
    """Configure the initial key responses for the Jacuzzi
    Spaa UI.

    This sets up key responses that will be active during the
    entire UI session.
    """
    # Note that curses.ascii.ctrl('x') returns the same
    # type you pass to it; given 'x' it returns string
    # '\x18', not the integer value 0x18.
    #
    # ord() converts a character to its integer value.
    #
    # So to get the integer value we need to use ord()
    # on either the argument or on the return value. Either
    # way will work.
    #
    # Create a KeyResponse instance for Ctrl-x and
    # add it to the display Window.
    ctrl_x_key = KeyResponse("ctrl_x", ord(curses.ascii.ctrl("x")))
    spa_ui.display.add_key(ctrl_x_key)
    ctrl_x_key.bind(spa_ui.kr_done_with_ui)

    # Create and install the KeyResponse instance for Ctrl-p
    ctrl_p_key = KeyResponse("ctrl_p", ord(curses.ascii.ctrl("p")))
    spa_ui.display.add_key(ctrl_p_key)

    def _kr_ctrl_p_response(_):
        # Define some random message strings to print
        msglist = [
            "Hello, world.",
            "Forty-two.",
            "Beautiful is better than ugly.",
            "Readability counts.",
            "Nobody expects the Spanish Inquisition!",
            "What is the air-speed velocity of an unladen swallow?",
            "So long and thanks for all the fish.",
            "Don't panic.",
            "THIS IS AN EX-PARROT!!",
        ]

        # Note that while the CursesUI instance has control of the
        # screen, you can still use simple print statements even
        # though curses is maintaining its windows.  Output from
        # print() statements will go instead into the stdout_bfr
        # which will be dumped to the screen on exit.
        #
        # Also, the Message Window displays the contents of the
        # stdout_bfr. So for the demo, any print() output will be
        # visible there too.
        print("Msg: {0}".format(random.choice(msglist)))

    # Bind Ctrl-p to its local response routine
    ctrl_p_key.bind(_kr_ctrl_p_response)

    # Create and install the KeyResponse instance for TAB
    tab_key = KeyResponse("tab", curses.ascii.TAB)
    spa_ui.display.add_key(tab_key)

    # The TAB key will select the next child Window
    tab_key.bind(spa_ui.display.kr_select_next_child)

    # Create and install the KeyResponse instance for ENTER
    enter_key = KeyResponse("enter", curses.ascii.LF)
    spa_ui.display.add_key(enter_key)

    # ENTER will begin editing the selected child Window
    enter_key.bind(spa_ui.display.kr_begin_child_edit)


# The code below runs only when jacuzziui.py is invoked from the
# command line with "python3 jacuzziui.py"
if __name__ == "__main__":
    # The normal curses keyboard handling system adds a
    # configurable delay to the ESCAPE key so that it can
    # be combined with other keys to generate special keycodes.
    # The delay is typically around 1 second, which can be
    # noticably slow if you are not using the ESCAPE key that way.
    # You can change the delay by setting the ESCDELAY environment
    # variable to a shorter delay but you have to change it before
    # the curses windowing system gets initialized.
    #
    # Since the demoUI system does use the ESCAPE key we will set
    # a shorter delay (in milliseconds) here.
    import os

    os.environ.setdefault("ESCDELAY", "25")

    import logging

    # Set up a CursesUI instance to run concurrently with the
    # SpaProcess instance.
    from cursesui import CursesUI

    spa = jacuzziRS485.JacuzziRS485(jacuzzi_ip_address, jacuzzi_port)

    # Create the user interface, telling it how
    # to set up the display and keyboard responses.
    spa_ui = CursesUI(
        setup_ui_display,
        setup_ui_responses,
        "JacuzziRS485 Spa UI - Thanks to dhmsjs for UI creation",
    )

    # Tell the spa instance to use the CursesUI logging instance
    spa.log = log

    # Tell the user interface to run spa communications concurrently.
    spa_ui.add_coroutine(spa.check_connection_status)
    spa_ui.add_coroutine(spa.listen)

    # Set up the logging level for this user interface.
    #
    # Typical log filter levels are logging.DEBUG
    # for development, logging.ERROR for normal use.
    # Set level to logging.CRITICAL + 1 to suppress
    # all log messages from a CursesUI instance.
    #
    # spa_ui.initialize_loglevel(logging.DEBUG)
    spa_ui.initialize_loglevel(logging.INFO)

    fh = logging.FileHandler("logfile.txt")
    formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    fh.setFormatter(formatter)
    log.addHandler(fh)

    # Run the CursesUI instance until the user quits
    spa_ui.run()
