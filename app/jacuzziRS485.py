""" This module extends balboa.py to work instead with Jacuzzi
spas. 

It uses an old version of pybalboa (https://github.com/garbled1/pybalboa)

I chose to extend pybalboa so that I could leverage the already-proven
WiFi and protocol parsing behavior in pybalboa. This dependency turns
out to be pretty light; it would not take major effort to decouple
jacuzziRS485.py from pybalboa. Still, I am deeply indebted to 

garbled1 (https://github.com/garbled1/pybalboa)
natekspencer (https://github.com/natekspencer)
ccutrer (https://github.com/ccutrer/balboa_worldwide_app/wiki)
hyperactivej (https://github.com/HyperActiveJ)
dhmsjs (https://github.com/dhmsjs)

along with several others here unnamed, who have helped reverse engineer
balboa hot tub control systems and their many rebranded derivatives.
"""
import asyncio
import time
import queue
from datetime import datetime

# logging.basicConfig(level=logging.INFO)

# Use the local copy of pybalboa as we know this version works.
#
# We use the "from...*" construct here so that all objects in balboa
# (without a leading underscore anyway) become available as local
# objects; i.e. they can only be referenced without the "balboa."
# module prefix.
#
# This is not generally a good idea because it increases the chances
# of duplicate names clashing unintentionally.  Requiring you to use the
# "balboa." prefix would prevent this.
#
# Here we use it intentionally to cleanly reference or override balboa
# module objects when they need to be different for Jacuzzi systems.
from balboa import *

from enum import Enum


class ConnectionStates(Enum):
    """enum types for Wifi connection states."""

    Disconnected = 0
    Connecting = 1
    Connected = 2


# Add unique enumerated constants for Jacuzzi-specific message types.
#
# These constants are NOT the message type values themselves. They are
# just sequentially enumerated constants used to uniquely identify
# each message type.
#
# Differences between Balboa and Jacuzzi systems:
#   The Balboa BMTR_STATUS_UPDATE msg type field is 0x13 instead of 0x16
#   The Balboa BMTR_FILTER_INFO_RESP msg type field is 0x27 instead of 0x23
#   The Balboa BMTS_PANEL_REQ msg type field is 0x22 instead of 0x19
#   The Balboa BMTR_SYS_INFO_REQ msg type field is 0x24 instead of
#     0x1C (PLNK_SECONDARY_FILTER_RESP)
#   There is no PRIMARY_FILTER_RESP msg type or similar in Balboa systems
#   There is no PUMP_STATE_RESP msg type or similar in Balboa systems
#   The Balboa BMTR_SETUP_PARAMS_RESP msg type field is 0x25 instead of 0x1E

JACUZZI_STATUS_UPDATE = 0x16
JACUZZI_LIGHTS_UPDATE = 0x23
CC_REQ = 0x17

# Channel Related
CLIENT_CLEAR_TO_SEND = 0x00
CHANNEL_ASSIGNMENT_REQ = 0x01
CHANNEL_ASSIGNMENT_RESPONSE = 0x02
CHANNEL_ASSIGNMENT_ACK = 0x03
EXISTING_CLIENT_REQ = 0x04
EXISTING_CLIENT_RESPONSE = 0x05
CLEAR_TO_SEND = 0x06
NOTHING_TO_SEND = 0x07

# Used to find our old channel, or an open channel
DETECT_CHANNEL_STATE_START = 0
DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND = (
    5  # Wait this many CTS cycles before deciding that a channel is available to use
)
NO_CHANGE_REQUESTED = -1  # Used to return control to other devices
CHECKS_BEFORE_RETRY = (
    2  # How many status messages we should receive before retrying our command
)

# Override pybalboa text strings for Jacuzzi-specific differences:

text_tscale = ["Fahrenheit", "Celsius"]  # Just to fix the misspelling


class JacuzziRS485(BalboaSpaWifi):
    """Extends BalboaSpaWifi to work with Jacuzzi spas instead."""

    def __init__(self, hostname, port=BALBOA_DEFAULT_PORT):
        super().__init__(hostname, port)
        self.connection_state = ConnectionStates.Disconnected

        # Balboa systems can receive ("auto detect") configuration info from
        # the actual spa. So the BalboaSpaWifi class waits to receive this
        # configuration info before it will start working.
        #
        # Jacuzzi spas don't seem to tell us their config -- and if really
        # true then auto detecting is not possible. So for now we will just
        # set up some default config values.
        #
        # TODO: implement some sort of configuration methods for Jacuzzi spas.

        self.pump_array = [0, 2, 1, 0, 0, 0]  # Jet pumps 1 and 2 only
        self.nr_of_pumps = 2
        self.circ_pump = 1
        self.tempscale = self.TSCALE_C
        self.timescale = self.TIMESCALE_12H
        self.temprange = self.TEMPRANGE_HIGH

        # Initialize low range min and max temperatures as [°F, °C]
        # (but not used in Jacuzzi spas)
        self.tmin[0] = [40, 18.5]
        self.tmax[0] = [104, 40]

        # Initialize high range min and max temperatures as [°F, °C]
        self.tmin[1] = [40, 18.5]
        self.tmax[1] = [104, 40]

        self.filter_mode = self.FILTER_1
        self.heatmode = 0
        self.filter1_hour = 0
        self.filter1_duration_hours = 8
        self.filter2_enabled = 0

        self.isSecondaryOn = 0
        self.isPrimaryOn = 0
        self.isBlowerOn = 0
        self.isUVOn = 0

        self.pump3State = 0
        self.pump2State = 0
        self.pump1State = 0
        self.pump0State = 0

        # Setup some model specific values
        # TODO: remove any that are not relevant to Jacuzzi spas
        self.day = -1
        self.month = -1
        self.year = -1

        self.dayOfMonth = 0
        self.currentMonth = 0
        self.currentYear = 0

        self.temp2 = -1
        self.manualCirc = -1
        self.autoCirc = -1
        self.unknownCirc = -1
        self.heatState2 = -1
        self.displayText = -1
        self.heatMode = -1
        self.UnknownField3 = -1
        self.UnknownField9 = -1
        self.panelLock = -1

        self.lightBrightness = 0
        self.lightMode = 0
        self.lightR = 0
        self.lightG = 0
        self.lightB = 0

        self.statusByte17 = 0
        self.filter1StartHour = 0
        self.filter1DurationHours = 0
        self.filter1Freq = 0

        self.filter2Mode = 0

        # In the J-235 spa the light cycle time for "blend" mode
        # is only 1 change per second. Apparently in Balboa spas
        # there are two speeds: 1 change per second and 2 changes
        # per second (I think).
        # self.lightCycleTime = 1 # In seconds.

        # Messages must be sent on CTS for our channel, not any time
        self.queue = queue.Queue()

        # The Prolink Wifi module always has channel address 0x0A
        # TODO: Set to 0x0A if ProLink is being used
        self.channel = None
        self.discoveredChannels = []  # All the channels the tub is producing CTS's for
        self.activeChannels = []  # Channels we know are in use by other RS485 devices
        self.detectChannelState = DETECT_CHANNEL_STATE_START  # State machine used to find an open channel, or to get us a new one

        # setup some specific items that we need that the base class
        # doesn't.
        # TODO: Not used now; probably can be removed
        self.target_pump_status = [
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
        ]
        self.targetTemp = NO_CHANGE_REQUESTED
        self.checkCounter = 0
        self.prior_status = None

        self.prev_chksums = {}
        self.config_loaded = True  # Done with configuration

        # 2nd temperature sensor. This is apparently in the plumbing
        # not in the tub itself as the primary sensor is. So this
        # one tells you what the water temperature in the pipes is.
        self.statusByte21 = 0

    async def send_mod_ident_req(self):
        """Overrides parent method just to add debug logging."""
        self.log.debug("Requesting module ID (msg type value 0x04)")
        await super().send_mod_ident_req()

    async def send_filter1_cycle_req(self):
        """Sends a request for Primary Filter Cycle Info."""
        await self.send_panel_req(1, 0)

    async def send_filter2_cycle_req(self):
        """Sends a request for Secondary Filter Cycle Info."""
        await self.send_panel_req(2, 0)

    async def send_panel_req(self, ba, bb):
        """Overrides the parent method to accommodate differences
        in the Prolink message format.

        ba and bb specify the type of panel request to send
        """
        # The only difference between Balboa and Jacuzzi panel request
        # message packets (apart from type value itself) is that the
        # Jacuzzi message packet does not have the extra byte field
        # (always 0x00?) between the ba and bb panel request values.
        #
        # Example: 7E 07 0A BF 19 01 00 XX 7E
        # (XX = calculated checksum)
        data = bytearray(5)
        data[0] = self.channel
        data[1] = 0xBF
        data[2] = 0x19  # Was 0x22 for Balboa
        data[3] = ba
        data[4] = bb

        # send_message() will append the start and end flags, the length
        # and the checksum.
        await self.send_message(*data)

    async def set_time(self, new_time, timescale=None):
        """Overrides the parent method to set time on a Jacuzzi spa.
        Jacuzzi spa controllers do not switch to 12 hour timescale,
        so this method override ignores the timescale field.
        """
        # sanity check
        if not isinstance(new_time, time.struct_time):
            return

        data = bytearray(8)
        data[0] = self.channel
        data[1] = 0xBF
        data[2] = 0x18  # Was 0x21 for Balboa

        # Keep the date fields unchanged. The spa control system
        # will ignore this command if the upper 4 bits of the current
        # month are not all set to 1.
        data[3] = self.currentMonth | 0xF0
        data[4] = self.dayOfMonth
        data[5] = self.currentYear - 2000

        # In balboa spas setting bit 7 of the hour value will switch the
        # spa time to 12 hour format. Jacuzzi spa controllers ignore this
        # bit though, so Jacuzzi spas will only operate in 24 hour mode.
        data[6] = new_time.tm_hour
        data[7] = new_time.tm_min

        # send_message() will append the start and end flags, the length
        # and the checksum.
        await self.send_message(*data)

    async def set_date(self, new_date, timescale=None):
        """Sets the current date on a Jacuzzi spa. Since balboa
        spas do not have an internal date, there is no equivalent
        method in balboa.py.
        """
        # sanity check
        if not isinstance(new_date, time.struct_time):
            return

        data = bytearray(8)
        data[0] = self.channel
        data[1] = 0xBF
        data[2] = 0x18  # Was 0x21 for Balboa

        # Update the Set Time command date fields. The Jacuzzi spa
        # control system will ignore this command if the upper 4
        # bits of the current month are not all set to 1.
        data[3] = new_date.tm_mon | 0xF0
        data[4] = new_date.tm_mday
        data[5] = new_date.tm_year - 2000

        # Leave the time fields unchanged
        data[6] = self.time_hour
        data[7] = self.time_minute

        # send_message() will append the start and end flags, the length
        # and the checksum.
        await self.send_message(*data)

    async def change_pump(self, pump, newstate):
        """Overrides the parent method to accommodate differences
        in the Prolink message type fields.

        pump identifies the pump to change.
        """

        # Each message sent emulates a button press on the Jacuzzi
        # topside control panel. So if a pump has two speeds for
        # example, then each message will effect one step through
        # the cycle of 0ff-low-high-off.
        #
        # The only difference between Balboa and Jacuzzi change pump
        # message packets (apart from type value itself) is that the
        # Jacuzzi type field has type field 0x17 for pumps 1 through 3
        # instead of 0x1A
        #
        # Example: 7E 06 0A BF 17 04 XX 7E
        # (XX = calculated checksum)

        # sanity check
        if (
            pump > MAX_PUMPS
            or newstate > self.pump_array[pump]
            or self.pump_status[pump] == newstate
        ):
            return

        if pump == 1 or pump == 2 or pump == 3:
            mtype = 0x17
        else:
            mtype = 0x1A
        pumpcode = pump + 3

        data = bytearray(4)
        data[0] = self.channel
        data[1] = 0xBF
        data[2] = mtype  # Was 0x11 for balboa
        data[3] = pumpcode

        # calculate how many times to push the button
        iter = max((newstate - self.pump_status[pump]) % (self.pump_array[pump] + 1), 1)
        # now push the button that number of times
        for i in range(0, iter):
            # send_message() will append the start and end flags, the length
            # and the checksum.
            await self.send_message(*data)
            await asyncio.sleep(1.0)

    async def change_light(self, newmode):
        """Overrides the parent method to accommodate differences
        in the Prolink message type fields.
        """

        # Note that this is the same message type as brightness
        # control, with only slight differences in content.
        data = bytearray(11)
        data[0] = self.channel
        data[1] = 0xBF
        data[2] = 0x21  # Was 0x11 for balboa
        data[3] = 0x1F  # = 0x2F for brightness
        data[4] = newmode
        data[5] = 0x00
        data[6] = 0x00
        data[7] = 0x00
        data[8] = 0x00
        data[9] = 0xFF  # Brightness field
        data[10] = 0x00

        # send_message() will append the start and end flags, the length
        # and the checksum.
        await self.send_message(*data)

    async def change_brightness(self, newlevel):
        """Sends a command to change the LED brightness level."""

        # Note that this is the same message type as light mode
        # control, with only slight differences in content.
        data = bytearray(11)
        data[0] = self.channel
        data[1] = 0xBF
        data[2] = 0x21  # 0x21 is BMTS_SET_TIME for balboa
        data[3] = 0x2F  # = 0x1F for light mode control
        data[4] = 0x01  # Mode field
        data[5] = 0x00
        data[6] = 0x00
        data[7] = 0x00
        data[8] = 0x00
        data[9] = newlevel  # Brightness value
        data[10] = 0x00

        # send_message() will append the start and end flags, the length
        # and the checksum.
        await self.send_message(*data)

    async def change_filter1_cycle(self, starthour, durationhrs, frequency):
        """Sends a command to change the primary filter cycle
        start hour, duration and frequency (number of cycles per day).
        """

        # Note that this message type is also received by the app in response
        # to it sending the spa a Panel Request message of either the
        # "Filter Cycles" or "Primary Filtration" types.
        #
        # The Prolink app code sends a packet that does not include the frequency byte.
        # The spa controller does accept the packet without that byte, but seems to
        # lose communication temporarily, and then assume the frequency is 01 (1 cycle
        # per day).  Adding the frequency parameter to the packet does work too and does
        # not seem to cause a loss of communication.
        data = bytearray(6)
        data[0] = self.channel
        data[1] = 0xBF  # "PF" byte (always either 0xAF or 0xBF)
        data[
            2
        ] = 0x1B  # BMTR_FILTER_INFO_RESP = 0x23, BMTS_FILTER_REQ = 0x22 for balboa
        data[3] = starthour
        data[4] = durationhrs
        data[5] = frequency

        # send_message() will append the start and end flags, the length
        # and the checksum.
        await self.send_message(*data)

        # Yield a bit while the spa acts on the request
        await asyncio.sleep(0.1)

        # Now request an update of current filter cycle info
        # so the UI can see the change.
        await self.send_filter1_cycle_req()

    async def change_filter2_cycle(self, mode):
        """Sends a command to change the secondary filter cycle
        mode between "Holiday", "Light" and "Heavy" modes. The
        mode values are 0, 1 and 2 respectively.
        """
        # This is essentially the same format as the filter info
        # response message sent by the spa controller to report
        # the current secondary filter mode value.
        data = bytearray(6)
        data[0] = self.channel
        data[1] = 0xBF  # "PF" byte (always either 0xAF or 0xBF)
        data[
            2
        ] = 0x1C  # BMTR_FILTER_INFO_RESP = 0x23, BMTS_FILTER_REQ = 0x22 for balboa
        data[3] = mode
        data[4] = 0
        data[5] = 0

        # send_message() will append the start and end flags, the length
        # and the checksum.
        await self.send_message(*data)

        # Yield a bit while the spa acts on the request
        await asyncio.sleep(0.1)

        # Now request an update of current filter cycle info
        # so the UI can see the change.
        await self.send_filter2_cycle_req()

    async def send_message(self, *bytes):
        """Overrides parent method only to change log messaging."""
        # If not connected, we can't send a message
        if not self.connected:
            self.log.error("Attempted to send a message when not connected.")
            return

        # If we don't have a channel number yet, we can't form a message
        if self.channel is None:
            self.log.error("Attempted to send a message without a channel set.")
            return

        message_length = len(bytes) + 2
        data = bytearray(message_length + 2)
        data[0] = M_STARTEND
        data[1] = message_length
        data[2:message_length] = bytes
        data[-2] = self.balboa_calc_cs(data[1:message_length], message_length - 1)
        data[-1] = M_STARTEND

        self.log.info(f"Queueing Message: {data.hex()}")
        self.queue.put(data)

    async def set_channel(self, chan):
        self.channel = chan
        self.log.info("Channel Assigned: {}".format(self.channel))

    async def parse_status_update(self, data):
        """Override balboa's parsing of a status update from the spa
        to handle Jacuzzi differences.

        Many of the field values are similar between Balboa and Jacuzzi,
        but their position in the message packet is often different.

        The spa sends these messages out at a very high rate of speed.

        Unlike the overridden version in balboa.py, this routine does not
        check to see if config has been loaded already. Thus it does not
        need the async prefix.  Similarly it does not check to see if the
        message data has changed.
        """

        # This will cause our internal states to update once per minute due
        # to the hour/minute counter.  This is ok.

        have_new_data = False

        if self.prior_status is not None and data.hex() != self.prior_status:
            have_new_data = True
            self.prior_status = data.hex()
        elif self.prior_status is None:
            self.prior_status = data.hex()
        else:
            return

        # Modified for Jacuzzi; was data[8] and data[9] for Balboa
        self.time_hour = data[5]
        self.time_minute = data[6]

        # Byte 7 Bits 7,6,5 = currentWeek (actually day of week; 1 = Monday)
        # Byte 7 Bits 4,3,2,1,0 = daysInMonth (actually day of month)
        self.dayOfWeek = (data[7] & 0xE0) >> 5
        self.dayOfMonth = data[7] & 0x1F

        # Byte 8 = currentMonth
        # Byte 9 = currentYear (since 2000)
        self.currentMonth = data[8]
        self.currentYear = data[9] + 2000

        # Byte 10 Bits 7,6 = Filter2Mode (0b00 = off)
        # Byte 10 Bits 5,4 = HeatModeState (0b01 = on-low?)
        # Byte 10 Bits 3,2,1,0 = SpaState
        # (values of 1,2,8,9 or 10 get forced to -1) (0b0010 = 2)
        self.filter2Mode = (data[10] & 0xC0) >> 6
        self.heatModeState = (data[10] & 0x30) >> 4
        self.spaState = data[10] & 0x0F

        # TODO: why are heatmode and heatstate the same bits?
        # flag 2 is heatmode
        # Modified for Jacuzzi; Balboa had no bit shift
        self.heatmode = (data[10] >> 4) & 0x03

        # flag 4 heating state, temp range
        # Modified for Jacuzzi; Balboa was data[15]
        self.heatstate = (data[10] & 0x30) >> 4

        # Byte 11 = errorCode (0x00 = no error)
        self.errorCode = data[11]

        # Modified for Jacuzzi; was data[7] for Balboa
        curtemp = float(data[12])

        # Byte 13 = don't care? (0xFA)
        self.statusByte13 = data[13]

        # Modified for Jacuzzi; was data[25] for Balboa
        settemp = float(data[14])

        self.curtemp = (
            curtemp / (2 if self.tempscale == self.TSCALE_C else 1)
            if curtemp != 255
            else None
        )
        self.settemp = settemp / (2 if self.tempscale == self.TSCALE_C else 1)

        # Byte 15 Bits 7,6 = Pump3State
        # Byte 15 Bits 5,4 = Pump2State (bit posn off by 1??)
        # Byte 15 Bits 3,2 = Pump1State
        # Byte 15 Bits 1,0 read but not used
        self.pump3State = (data[15] & 0xC0) >> 6
        self.pump2State = (data[15] & 0x30) >> 4
        self.pump1State = (data[15] & 0x0C) >> 2
        self.pump0State = data[15] & 0x03

        # Modified for Jacuzzi; does not have a temprange feature
        # self.temprange = (data[15] & 0x04) >> 2

        for i in range(0, 6):
            if not self.pump_array[i]:
                continue
            # 1-4 are in one byte, 5/6 are in another
            if i < 4:
                # Modified for Jacuzzi; Balboa was data[16]
                self.pump_status[i] = (data[15] >> i * 2) & 0x03
            # Modified for Jacuzzi -- does not have pumps 5 or 6
            # else:
            #   self.pump_status[i] = (data[17] >> ((i - 4)*2)) & 0x03

        if self.circ_pump:
            # Modified for Jacuzzi; not clear which pump is circ pump -- pump 0 maybe?
            # Answer: there is no circ pump on J-235. Pump 1 (Jets 1) runs at low speed
            # to circulate during filter cycles. Pump 0 does not exist so bits 0 & 1 of
            # data[15] will always be zero. HOWEVER, J-300 and J-400 series spas do
            # have a circulation pump so this is probably still needed.
            #
            # Balboa was data[18] == 0x02
            if data[15] & 0x03:
                self.circ_pump_status = 1
            else:
                self.circ_pump_status = 0

        # From Jacuzzi app code:
        # Byte 16 Bits 6,5 = IsSecondaryON
        # Byte 16 Bits 5,4 = IsPrimaryON (Bit posn off by 1??)
        # Byte 16 Bits 4,3 = IsBlowerON (Bit posn off by 1??_
        # Byte 16 Bits 2,1 = IsUVON
        #
        # But these bit positions seem to make more sense:
        # Byte 16 Bits 7,6 = IsSecondaryON
        # Byte 16 Bits 5,4 = IsPrimaryON (Bit posn off by 1??)
        # Byte 16 Bits 3,2 = IsBlowerON (Bit posn off by 1??)
        # Byte 16 Bits 1,0 = IsUVON
        # TODO: what are the real bit positions?
        #
        # All of these except isSecondaryOn will come on during
        # a filter cycle and also whenever pump 1 is turned on
        # manually.
        self.isSecondaryOn = (data[16] & 0xC0) >> 6
        self.isPrimaryOn = (data[16] & 0x30) >> 4
        self.isBlowerOn = (data[16] & 0x0C) >> 2
        self.isUVOn = data[16] & 0x03

        # flag 3 is filter mode
        # Modified for Prolink IsPrimaryOn (bit 5,4 of byte 16)
        # Balboa was: self.filter_mode = (data[14] & 0x0c) >> 2
        #
        # It is possible that IsBlowerOn in Prolink is mislabeled
        # and actually is equivalent to filter_mode in Balboa.
        # If so then this should actually be:
        # self.filter_mode = (data[16] & 0x0C) >> 2
        self.filter_mode = (data[16] & 0x30) >> 4

        # It does not appear that any Jacuzzi hot tub has a blower
        # (at least at this time). This status is always on whenever
        # pump 1 is on.
        if self.blower:
            # Modified for Prolink; was data[18]. Same bits as isBlowerOn
            self.blower_status = (data[16] & 0x0C) >> 2

        # Byte 17 = don't care?
        # In Prolink byte17 seems to indicate that pump 1 is running
        # -- i.e. whenever pump 1 is on, byte 17 is 0x01. At all other
        # times it is 0x00. It is delayed by about 1 second with
        # respect to changes in pump 1. It does transition oddly at the
        # end of a filter cycle though; turning off and back on
        # briefly. Perhaps this is a flow sensor signal?
        # UPDATE: Yes I believe it is the flow switch signal
        self.statusByte17 = data[17]

        # Modified for Prolink; was data[14] ; logic reversed??
        # TODO: resolve the logic reversal question
        # (12 hr only if both bits 2 & 1 are 0) (= 0x02)
        if data[18] & 0x06 == 0:
            self.timescale = self.TIMESCALE_12H
        else:
            self.timescale = self.TIMESCALE_24H

        # Modified for Prolink; was data[14] for Balboa (= 0x02)
        if data[18] & 0x01:
            self.tempscale = self.TSCALE_C
        else:
            self.tempscale = self.TSCALE_F

        # Byte 19 = don't care? (= 0x00)
        self.statusByte19 = data[19]

        for i in range(0, 2):
            if not self.light_array[i]:
                continue
            # Prolink light bits unclear; data[19] is unused??
            # Yes it appears data[19] does not hold light status.
            # Instead the light status is contained in message
            # type 0x23.
            self.light_status[i] = ((data[19] >> i * 2) & 0x03) >> 1

        # Byte 20 Bits 5,4 = settingLock
        # Byte 20 Bits 3,2 = accessLock
        # Byte 20 Bits 1,0 = maintenanceLock (Bit posn error off by 1??)
        self.settingLock = (data[20] & 0x30) >> 4
        self.accessLock = (data[20] & 0x0C) >> 2
        self.serviceLock = data[20] & 0x03

        # Prolink does not support mister? data[20] has lock bits
        # if self.mister:
        #    self.mister_status = data[20] & 0x01
        #
        # Yes it appears Jacuzzi does not have a mister feature on
        # any of its spas.

        # Modified for Prolink; does not have Aux channels?
        # It does not appear that any Jacuzzi hot tub has Aux 1 or 2
        # for i in range(0, 2):
        #     if not self.aux_array[i]:
        #         continue
        #     if i == 0:
        #         self.aux_status[i] = data[20] & 0x08
        #     else:
        #         self.aux_status[i] = data[20] & 0x10

        # Byte 21 = don't care? -- actually 2nd sensor of current water temp
        # Byte 22 = don't care?
        # Byte 23 = don't care?
        self.statusByte21 = data[21]
        self.statusByte22 = data[22]
        self.statusByte23 = data[23]

        # Byte 24 = CLEARRAYLSB
        # Byte 25 = CLEARRAYMSB
        # NOTE: MSB is actually LSB and LSB is MSB!
        self.clearrayTime = (data[24] * 256) + data[25]

        # Byte 26 = WATERLSB
        # Byte 27 = WATERMSB
        # NOTE: MSB is actually LSB and LSB is MSB!
        self.waterTime = (data[26] * 256) + data[27]

        if data[1] >= 30:  # packet length including checksum byte
            # Byte 28 = OUTERFILTERLSB
            # Byte 29 = OUTERFILTERMSB
            # NOTE: MSB is actually LSB and LSB is MSB!
            self.outerFilterTime = (data[28] * 256) + data[29]

        if data[1] >= 32:  # packet length including checksum byte
            # Byte 30 = INNERFILTERLSB
            # Byte 31 = INNERFILTERMSB
            # NOTE: MSB is actually LSB and LSB is MSB!
            self.innerFilterTime = (data[30] * 256) + data[31]

        if data[1] >= 33:  # packet length including checksum byte
            # Byte 32 Bits 7,6,5,4 = WiFiState
            #  0 = SpaWifiState.Unknown
            #  1 = SpaWifiState.SoftAPmodeUnavailable
            #  2 = SpaWifiState.SoftAPmodeAvailable
            #  3 = SpaWifiState.InfrastructureMode
            #  4 = SpaWifiState.InfrastructureModeConnectedToNeworkNotCloud
            #  5 = SpaWifiState.InfrastructureModeConnectedToNeworkCloud
            #  14 = SpaWifiState.LINKINGTONETWORK
            #  15 = SpaWifiState.NOTCOMMUNICATINGTOSPA
            self.spaWifiState = (data[32] & 0xF0) >> 4

        if data[1] >= 37:  # packet length including checksum byte
            # Byte 33 = don't care
            # Byte 34 = don't care
            # Byte 35 = don't care
            # Byte 36 = don't care
            self.statusByte33 = data[33]
            self.statusByte34 = data[34]
            self.statusByte35 = data[35]
            self.statusByte36 = data[36]

        # time.time() increments once per second
        self.lastupd = time.time()

    def parse_system_information(self, data):
        """Overrides parent method to handle the dofferemces in Jaccuzi
        system information message packets vs those in Balboa systems.

        Emulating the Prolink app behavior -- this just reads byte 7 of
        the message packet and if the value there is less than 6, it
        sets isOldVersion = true, or false otherwise.
        """

        self.sysInfoByte5 = data[5]
        self.sysInfoByte6 = data[6]
        if data[7] < 6:
            self.isOldVersion = True
        else:
            self.isOldVersion = False

    def parse_secondary_filter(self, data):
        """Decodes the Jaccuzi-specifc Secondary Filter Cycle
        message packet.
        """

        # According to the Prolink app this message has 3 data bytes but
        # only the first (data[5]) contains the current Secondary Filter
        # Cycle setting. Allowed values are 0, 1 or 2 indicating
        # "Holiday" "Light" or "Heavy" respectively.
        #
        # The value of second and 3rd data bytes always seems to be 0x0A
        self.SecondaryFilterCycle = data[5]
        self.secFilterByte6 = data[6]
        self.secFilterByte7 = data[7]

    def parse_primary_filtration(self, data):
        """Parse a Jacuzzi Primary Filtration message packet."""

        # This just reads bytes 5 and 6 of the message packet and
        # saves them. Oddly though, I have not found any code in
        # the Prolink app that handles these bytes. Yet the app
        # does display the primary filtration start time and duration.
        # It also seems to let you change the number of cycles per
        # day, which may be the purpose of data[7].
        #
        # The display of primary filtration in the Prolink app may
        # come from reading the panel update status message instead.
        startHour = data[5]
        durationHours = data[6]
        if startHour >= 0:
            self.filter1StartHour = startHour
        if durationHours >= 0:
            self.filter1DurationHours = durationHours

        # Manual says 1,2,3,4, or 8 are allowed values for frequency
        filter1Freq = data[7]
        if (filter1Freq > 0 and filter1Freq <= 4) or filter1Freq == 8:
            self.filter1Freq = filter1Freq

    def parse_setup_parameters(self, data):
        """Parse a Jacuzzi Setup Parameters message packet."""

        # This message type is defined in the Prolink app but it does
        # not seem to be used in the app.  Might be a leftover from
        # Balboa code that was not needed or implemented.  This message
        # type in Balboa systems seems to handle features (such as high
        # and low temperature ranges) that Jacuzzi does not support.
        #
        # There is a Panel Request Type of the same name, so presumably
        # the app can request setup parameters from the spa controller.
        # But there does not seem to be any code in Prolink to parse this
        # message type if it is received from the spa controller. And yet
        # the Jacuzzi spa controller does return this message type.
        #
        # In the actual J-235 hot tub, sending a Panel Request message
        # (type 0x19 with payload1 = 0x04, payload2 = 0x00) to the spa
        # controller returns this message with type value 0x1E which is
        # not defined in either Balboa systems or the Prolink app. The
        # two data bytes in the returned message packet (Byte 5 and 6)
        # always seem to be 0x18 and 0x01.
        self.setupByte5 = data[5]
        self.setupByte6 = data[6]

    def parse_pump_state(self, data):
        """Parses a Jacuzzi "Pump State" message."""

        # This just reads the 6 upper bits of Byte 11 of the message
        # packet, counts the number of pumps present, and saves that
        # to the spa object's attributes. Oddly though, in the Prolink
        # app, nothing is ever done with the results.
        self.pumpStateByte5 = data[5]
        self.pumpStateByte6 = data[6]
        self.pumpStateByte7 = data[7]
        self.pumpStateByte8 = data[8]
        self.pumpStateByte9 = data[9]
        self.pumpStateByte10 = data[10]

        pump3bits = (data[11] & 0xC0) >> 6
        pump2bits = (data[11] & 0x30) >> 4
        pump1bits = (data[11] & 0x0C) >> 2
        pump0bits = data[11] & 0x03
        pumpcount = 0
        if pump3bits != 0:
            pumpcount += 1
        if pump2bits != 0:
            pumpcount += 1
        if pump1bits != 0:
            pumpcount += 1
        if pump0bits != 0:
            pumpcount += 1
        self.numberOfPumps = pumpcount
        self.pump3State = pump3bits
        self.pump2State = pump2bits
        self.pump1State = pump1bits
        self.pump0State = pump0bits

        self.pumpStateByte12 = data[12]
        self.pumpStateByte13 = data[13]
        self.pumpStateByte14 = data[14]
        self.pumpStateByte15 = data[15]
        self.pumpStateByte16 = data[16]
        self.pumpStateByte17 = data[17]
        # self.log.debug('Pump3: {0} Pump2: {1} Pump1: {2}; Total = {3}'.format(pump3bits, pump2bits, pump1bits, pumpcount))

    async def parse_light_status_update(self, data):
        """Parse a Jacuzzi Light status update message packet."""

        # This message type is not defined in the Prolink app
        # or balboa.py but the Jacuzzi J-235 spa does broadcast this
        # at regular intervals, much like the PLNK_STATUS_UPDATE
        # message. It contains the current state of the LED lights.
        #
        # Byte 5 = Color code
        # Byte 7 = Brightness level
        # Byte 8 = Red Level
        # Byte 9 = Green Level
        # Byte 10 = Blue Level
        self.lightMode = data[5]
        self.lightBrightness = data[7]
        self.lightR = data[8]
        self.lightG = data[9]
        self.lightB = data[10]
        self.log.debug(
            "Light status: L: {0} R: {1} G: {2} B: {3}".format(
                self.lightBrightness, self.lightR, self.lightG, self.lightB
            )
        )

    async def read_one_message(self):
        """Overrides parent method to update self.connection_state
        and add debug logging.
        """
        msg = await super().read_one_message()

        # If we recieve a non-empty message and ConnectionStates != Connected
        # Then update to ConnectionStates == Connected
        if msg is not None and self.connection_state is not ConnectionStates.Connected:
            self.connection_state = ConnectionStates.Connected

        if msg is not None:
            self.log.debug("Received message: {}".format(msg.hex()))
        else:
            self.log.debug("Read failed in read_one_message()")

        return msg

    async def check_connection_status(self):
        """Overrides the parent method to connect and reconnect as needed
        for Jacuzzi spas. This should run as a coroutine or task concurrently
        with other asynchronous coroutines.
        """

        timeout = 120  # Seconds
        while True:
            # self.connect() will set self.connected to True when
            # asyncio.open_connection() succeeds.
            #
            # self.read_one_message() will set self.connected to False
            # on any socket read error.

            if not self.connected:
                self.log.info(
                    "Attempting to connect to Jacuzzi ({}:{})...".format(
                        self.host, self.port
                    )
                )
                await self.connect()
                self.connection_state = ConnectionStates.Connecting

                # if connect() succeeded then send a primary filter request
                if self.connected and self.channel is not None:
                    await self.send_filter1_cycle_req()

            else:
                # We are connected. New updates typically come in every
                # second or so. So if we haven't received one recently,
                # send the spa a message to see if it will respond.

                if self.channel is not None and time.time() > self.lastupd + timeout:
                    self.connection_state = ConnectionStates.Disconnected
                    self.log.info("Requesting module ID.")
                    await self.send_mod_ident_req()

                    self.lastupd = time.time()

                    # Wait a bit before checking again. The spa seems to need
                    # more time to recover from a module_ident_req() command.
                    # await asyncio.sleep(10)
                    continue

            # Wait a bit before checking again.
            await asyncio.sleep(1)

    async def listen(self):
        """Overrides parent method to parse Jacuzzi-specific msg types

        This is an infinite loop to read and process incoming messages.
        It checks periodically to see if we are connected to the spa,
        When connected it reads and processes one message packet at a
        time, sleeping briefly between packets.
        """

        while True:
            if not self.connected:
                # sleep and hope the checker fixes us
                await asyncio.sleep(5)
                continue

            data = await self.read_one_message()

            if data is None:
                self.connection_state = ConnectionStates.Disconnected
                await asyncio.sleep(1)
                continue

            channel = data[2]
            mid = data[3]
            mtype = data[4]

            self.log.debug(
                "Processing msg type 0x{:02X} in process_message()".format(data[4])
            )

            if mtype == JACUZZI_STATUS_UPDATE:
                await self.parse_status_update(data)
            elif mtype == JACUZZI_LIGHTS_UPDATE:
                await self.parse_light_status_update(data)
            elif mtype == CLIENT_CLEAR_TO_SEND:
                if (
                    self.channel is None
                    and self.detectChannelState
                    == DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND
                ):
                    message_length = 8
                    data = bytearray(10)
                    data[0] = M_STARTEND
                    data[1] = message_length
                    data[2] = 0xFE
                    data[3] = 0xBF
                    data[4] = CHANNEL_ASSIGNMENT_REQ  # type
                    data[5] = 0x02
                    data[6] = 0xF1  # Random Magic
                    data[7] = 0x73
                    data[8] = self.balboa_calc_cs(
                        data[1:message_length], message_length - 1
                    )
                    data[9] = M_STARTEND
                    self.writer.write(data)
                    await self.writer.drain()
            elif mtype == CHANNEL_ASSIGNMENT_RESPONSE:
                await self.set_channel(data[5])
                message_length = 5
                data = bytearray(7)
                data[0] = M_STARTEND
                data[1] = message_length
                data[2] = self.channel
                data[3] = 0xBF
                data[4] = CHANNEL_ASSIGNMENT_ACK  # type
                data[5] = self.balboa_calc_cs(
                    data[1:message_length], message_length - 1
                )
                data[6] = M_STARTEND
                self.writer.write(data)
                await self.writer.drain()
            elif mtype == EXISTING_CLIENT_REQ:
                message_length = 8
                data = bytearray(9)
                data[0] = M_STARTEND
                data[1] = message_length
                data[2] = self.channel
                data[3] = 0xBF
                data[4] = EXISTING_CLIENT_RESPONSE  # type
                data[5] = 0x04  # Don't know!
                data[6] = 0x08  # Don't know!
                data[7] = 0x00  # Don't know!
                data[8] = self.balboa_calc_cs(
                    data[1:message_length], message_length - 1
                )
                data[9] = M_STARTEND
                self.writer.write(data)
                await self.writer.drain()
            elif mtype == CLEAR_TO_SEND:
                if not channel in self.discoveredChannels:
                    self.discoveredChannels.append(data[2])
                    self.log.info(
                        "Discovered Channels: {0}".format(self.discoveredChannels)
                    )
                elif channel == self.channel:
                    if self.queue.empty():
                        await self.writer.drain()
                    else:
                        msg = self.queue.get()
                        self.log.info("Sending message: {0}".format(msg.hex()))
                        self.writer.write(msg)
                        await self.writer.drain()
            else:
                if mtype == CC_REQ:
                    if not channel in self.activeChannels:
                        self.activeChannels.append(data[2])
                        self.log.info(
                            "Active Channels: {0}".format(self.activeChannels)
                        )
                    elif (
                        self.detectChannelState < DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND
                    ):
                        self.detectChannelState += 1
                        if (
                            self.detectChannelState
                            == DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND
                        ):
                            self.discoveredChannels.sort()
                            for chan in self.discoveredChannels:
                                if not chan in self.activeChannels:
                                    await self.set_channel(chan)
                                    break
                    if mtype == CC_REQ:
                        if (data[5]) != 0:
                            self.log.info(
                                "Got Button Press x".format(channel, mid, mtype)
                                + "".join(map("{:02X} ".format, bytes(data)))
                            )
                else:
                    self.log.error(
                        "Unhandled msg type 0x{0:02X} ({0}) in process_message()".format(
                            data[4]
                        )
                    )

    async def spa_configured(self):
        # TODO: make this override actually work for Jacuzzi spas
        # Jacuzzi spa must be manually configured so make this always true
        # for now. The parent method will never work for Jacuzzi spas since
        # panel request types are different between Balboa and Jacuzzi
        # systems. Also I have not been able to get the J-235 to respond
        # with a config data message packet. Doesn't seem like Jacuzzi supports
        # this method of configuration.
        return True

    async def listen_until_configured(self, maxiter=20):
        # TODO: remove this config override if not relevant to Jacuzzi spas
        return True

    # Additional accessors not provided by the parent class
    # TODO: remove any accessors that are not relevant to Jacuzzi spas

    def get_connection_state_text(self):
        return "{0} (Channel: {1})".format(self.connection_state.name, self.channel)

    def get_spatime_text(self):
        return "Spa Time: {0:02d}:{1:02d} {2}".format(
            self.time_hour, self.time_minute, self.get_timescale(True)
        )

    def get_day(self):
        return self.dayOfMonth

    def get_month(self):
        return self.currentMonth

    def get_year(self):
        return self.currentYear

    def get_spadate_text(self):
        return "Spa Date: {0}/{1}/{2}".format(
            self.get_month(), self.get_day(), self.get_year()
        )

    def get_curtemp_text(self):
        return "Water Temp: {0}".format(self.get_curtemp())

    def get_2ndtemp_text(self):
        return "2nd Temp: {0}".format(self.statusByte21)

    def get_settemp_text(self):
        return "Setpoint Temp: {0}".format(self.get_settemp())

    def change_settemp(self, newtemp):
        self.send_temp_change(newtemp)

    def get_temp2(self):
        return self.temp2

    def get_manualCirc(self):
        return self.manualCirc

    def get_autoCirc(self):
        return self.autoCirc

    def get_unknownCirc(self):
        return self.unknownCirc

    def get_heatstate_text(self):
        return "Heater: {0}".format(self.get_heatstate(True))

    def get_heatState2(self):
        return self.heatState2

    def get_displayText(self):
        return self.displayText

    def get_heatMode(self):
        return self.heatMode

    def get_UnknownField3(self):
        return self.UnknownField3

    def get_UnknownField9(self):
        return self.UnknownField9

    def get_panelLock(self):
        return self.panelLock

    def get_lightBrightness(self):
        return self.lightBrightness

    def get_lightMode(self):
        return self.lightMode

    def get_lightR(self):
        return self.lightR

    def get_lightB(self):
        return self.lightB

    def get_lightG(self):
        return self.lightG

    def get_last_update_text(self):
        if self.lastupd == 0:
            return "Last Update: N/A"
        else:
            current_time = datetime.now()
            input_datetime = datetime.fromtimestamp(self.lastupd)
            time_difference = current_time - input_datetime
            second_since_update = int(time_difference.total_seconds())
            return "Last Update: {0}s ago".format(second_since_update)
            
    def set_temp_value_formatter(self, val):
        # We accept float at .0 and .5 if temp scale is celsius
        # If temp scale if fahrenheit we round to the nearest whole numer

        # Ensure input is float
        val = float(val)

        if self.tempscale == self.TSCALE_C:
            new_temp = round(val * 2) / 2
        else:
            new_temp = round(val,0)

        return new_temp
