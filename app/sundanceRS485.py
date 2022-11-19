import asyncio
import logging
import time
import queue
import socket

try:
    from balboa import *
except:
    from .balboa import *

# Values that are common to all known Balboa produdcts
CLIENT_CLEAR_TO_SEND = 0x00
CHANNEL_ASSIGNMENT_REQ = 0x01
CHANNEL_ASSIGNMENT_RESPONCE = 0x02
CHANNEL_ASSIGNMENT_ACK = 0x03
EXISTING_CLIENT_REQ = 0x04
EXISTING_CLIENT_RESPONCE = 0x05
CLEAR_TO_SEND = 0x06
NOTHING_TO_SEND = 0x07

# Values that are unique for Jacuzzi J335
STATUS_UPDATE = 0x16
LIGHTS_UPDATE = 0x23
CC_REQ = 0x17

# Button CC equivs
BTN_CLEAR_RAY = 0x0F
BTN_P1 = 0x04
BTN_P2 = 0x05
BTN_TEMP_DOWN = 0x02
BTN_TEMP_UP = 0x01
BTN_MENU = 0x1E
BTN_LIGHT_ON = 0x11
BTN_LIGHT_COLOR = 0x12
BTN_NA = 224


# Button codes as byte arrays
button_codes = {
    "temp_up": bytes([0x7E, 0x06, 0x10, 0xBF, 0x17, 0x01, 0x7C, 0x7E]),
    "temp_down": bytes([0x7E, 0x06, 0x10, 0xBF, 0x17, 0x02, 0x75, 0x7E]),
    "jet_1": bytes([0x7E, 0x06, 0x10, 0xBF, 0x17, 0x04, 0x67, 0x7E]),
    "jet_2": bytes([0x7E, 0x06, 0x10, 0xBF, 0x17, 0x05, 0x60, 0x7E]),
    "menu": bytes([0x7E, 0x06, 0x10, 0xBF, 0x17, 0x1E, 0x21, 0x7E]),
    "clear_ray": bytes([0x7E, 0x06, 0x10, 0xBF, 0x17, 0x0F, 0x56, 0x7E]),
    "light": bytes([0x7E, 0x06, 0x10, 0xBF, 0x17, 0x11, 0x0C, 0x7E]),
    "light_colour": bytes([0x7E, 0x06, 0x10, 0xBF, 0x17, 0x12, 0x05, 0x7E]),
}

# Used to find our old channel, or an open channel
DETECT_CHANNEL_STATE_START = 0
DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND = (
    5  # Wait this many CTS cycles before deciding that a channel is available to use
)
NO_CHANGE_REQUESTED = -1  # Used to return control to other devices
CHECKS_BEFORE_RETRY = (
    2  # How many status messages we should receive before retrying our command
)

# Array to convert value returned to temp in C (manually recorded and verified each temp)
temp_convert = {
    48: 24,
    47: 24.5,
    51: 25,
    50: 25.5,
    53: 26,
    52: 26.5,
    55: 27,
    54: 27.5,
    57: 28,
    56: 28.5,
    59: 29,
    58: 29.5,
    61: 30,
    60: 30.5,
    63: 31,
    62: 31.5,
    65: 32,
    64: 32.5,
    67: 33,
    66: 33.5,
    69: 34,
    68: 34.5,
    71: 35,
    70: 35.5,
    73: 36,
    72: 36.5,
    75: 37,
    74: 37.5,
    77: 38,
    76: 38.5,
    79: 39,
    78: 39.5,
    81: 40,
}

# Array to convert value returned to set temp in C (manually recorded and verified each temp)
set_temp_convert = {
    171: 40,
    180: 39.5,
    181: 39,
    182: 38.5,
    183: 38,
    176: 37.5,
    177: 37,
    178: 36.5,
    179: 36,
    188: 35.5,
    189: 35,
    190: 34.5,
    191: 34,
    184: 33.5,
    185: 33,
    186: 32.5,
    187: 32,
    196: 31.5,
    197: 31,
    198: 30.5,
    199: 30,
    192: 29.5,
    193: 29,
    194: 28.5,
    195: 28,
    204: 27.5,
    205: 27,
    206: 26.5,
    207: 26,
    200: 25.5,
    201: 25,
    202: 24.5,
    203: 24,
    212: 23.5,
    213: 23,
    214: 22.5,
    215: 22,
    208: 21.5,
    209: 21,
    210: 20.5,
    211: 20,
    220: 19.5,
    221: 19,
    222: 18.5,
}


class SundanceRS485(BalboaSpaWifi):
    def __init__(self, hostname, port=8899):
        super().__init__(hostname, port)

        print("Test For @jackbrown1993")

        # DEBUG
        logging.basicConfig()
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)

        # Hard coded some values that the base class needs and we dont know how to auto detect yet
        self.config_loaded = True
        self.pump_array = [1, 1, 1, 0, 0, 0]
        self.nr_of_pumps = 3
        self.circ_pump = 1
        self.tempscale = self.TSCALE_C  # Can probably be determined...
        self.timescale = self.TIMESCALE_24H
        self.temprange = 1

        self.filter_mode = 1  # Can probably be determined...
        self.heatmode = 0  # Can probably be determined...
        self.filter1_hour = 0  # Can probably be determined...
        self.filter1_duration_hours = 8  # Can probably be determined...
        self.filter2_enabled = 0  # Can probably be determined...

        # Setup some model specific values
        self.day = -1
        self.month = -1
        self.year = -1
        self.temp2 = -1
        self.manualCirc = -1
        self.autoCirc = -1
        self.unknownCirc = -1
        self.heatState2 = -1
        self.displayText = -1
        self.heatMode = -1
        self.UnknownField3 = -1
        self.UnknownField9 = -1
        self.panelLock = -1  # Assuming this can be determined eventaully

        self.lightBrightnes = -1
        self.lightMode = -1
        self.lightR = -1
        self.lightG = -1
        self.lightB = -1
        self.lightCycleTime = -1

        # Setup some specific items that we need that the base class doesn't
        self.queue = (
            queue.Queue()
        )  # Messages must be sent on CTS for our channel, not any time
        self.channel = None  # The channel we are assigned to
        self.discoveredChannels = []  # All the channels the tub is producing CTS's for
        self.activeChannels = []  # Channels we know are in use by other RS485 devices
        self.detectChannelState = DETECT_CHANNEL_STATE_START  # State machine used to find an open channel, or to get us a new one
        self.target_pump_status = [
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
            NO_CHANGE_REQUESTED,
        ]  # Not all messages seem to get accepted, so we have to check if our change compelted and retry if needed
        self.targetTemp = NO_CHANGE_REQUESTED
        self.checkCounter = 0
        self.CAprior_status = None

    async def connect(self):
        """Connect to the spa."""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
        except (asyncio.TimeoutError, ConnectionRefusedError):
            self.log.error(
                "Cannot connect to spa at {0}:{1}".format(self.host, self.port)
            )
            return False
        except Exception as e:
            self.log.error(f"Error connecting to spa at {self.host}:{self.port}: {e}")
            return False
        self.connected = True
        sock = self.writer.transport.get_extra_info("socket")
        print(str(sock))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return True

    async def send_temp_change(self, newtemp):
        """Change the set temp to newtemp."""
        # Check if the new temperature is valid for the current heat mode
        if (
            newtemp < self.tmin[self.temprange][self.tempscale]
            or newtemp > self.tmax[self.temprange][self.tempscale]
        ):
            self.log.error("Attempt to set temperature outside of heat mode boundary")
            return

        self.targetTemp = newtemp

    async def change_light(self, light, newstate):
        """Change light #light to newstate."""
        # Sanity check
        if (
            light > 1
            or not self.light_array[light]
            or self.light_status[light] == newstate
        ):
            return

        if light == 0:
            await self.send_CCmessage(241)  # Lights Brightness Button
        else:
            await self.send_CCmessage(242)  # Lights Color Button

    async def change_pump(self, pump, newstate):
        """Change pump #pump to newstate."""
        # Sanity check
        print("{} {}".format(self.pump_status[pump], newstate))
        if (
            pump > MAX_PUMPS
            or newstate > self.pump_array[pump]
            or self.pump_status[pump] == newstate
        ):
            return

        self.target_pump_status[pump] = newstate

    async def send_CCmessage(self, val):
        """Sends a message to the spa with variable length bytes."""
        # If not connected, we can't send a message
        if not self.connected:
            self.log.info("Tried to send CC message while not connected")
            return

        # If we don't have a channel number yet, we can't form a message
        if self.channel is None:
            self.log.info(
                "Tried to send CC message without having been assigned a channel"
            )
            return

        print("Sending message on channel: " + str(self.channel))

        # data = bytearray(8)
        # message_length = 6
        # data[0] = M_STARTEND
        # data[1] = message_length
        # data[2] = self.channel
        # data[3] = 0xBF
        # data[4] = CC_REQ
        # data[5] = val
        # data[6] = 0x7C
        # data[7] = M_STARTEND

        self.log.debug(f"Queuing message: {val.hex()}")

        self.queue.put(val)

    async def send_message(self, *bytes):
        """Sends a message to the spa with variable length bytes."""
        self.log.info("Not supported with New Format messaging")
        return

    def xormsg(self, data):
        lst = []
        for i in range(0, len(data) - 1, 2):
            c = data[i] ^ data[i + 1] ^ 1
            lst.append(c)
        return lst

    async def parse_C4status_update(self, data):
        """Parse a status update from the spa.
        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
        7E 26 FF AF C4 AE A7 AA AB A4 A1 C9 5D A5 A1 C2 A1 9C BD CE BB E2 B9 BB AD B4 B5 A7 B7 DF B1 B2 9B D3 8D 8E 8F 88 F9 7E
        """

        # print ("".join(map("{:02X} ".format, bytes(data))))

        # "Decrypt" the message
        data = self.xormsg(data[5 : len(data) - 2])

        # print ("x{}".format(data))

        """Parse a status update from the spa.
        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
        [9, 0, 5, 148, 5, 99, 32, 124, 96, 23, 0, 33, 110, 39, 96, 0]
        """

        # Check if the spa had anything new to say.
        # This will cause our internal states to update once per minute due
        # to the hour/minute counter.  This is ok.
        have_new_data = False
        if self.prior_status is not None:
            for i in range(0, len(data)):
                if data[i] != self.prior_status[i]:
                    have_new_data = True
                    break
        else:
            have_new_data = True
            self.prior_status = bytearray(len(data))

        HOUR_FIELD = 0  # XOR 6 to get 24 hour time
        HOUR_XOR = 6  # Need to XOR the hour field with 6 to get the actual hour

        self.time_hour = data[HOUR_FIELD] ^ HOUR_XOR

        MINUTE_FIELD = 11  # OK as is

        self.time_minute = data[MINUTE_FIELD]

        PUMP_FIELD_1 = 1  # Most bit data
        PUMP_2_BIT_SHIFT = 2  # b100 When pump running
        PUMP_CIRC_BIT_SHIFT = 6  # b1000000 when pump running
        MANUAL_CIRC = 7  # b11000000 Includeding Pump running
        AUTO_CIRC = 6  # b1100000 Includeding Pump running

        self.pump_status[1] = (data[PUMP_FIELD_1] >> PUMP_2_BIT_SHIFT) & 1

        self.circ_pump_status = (data[PUMP_FIELD_1] >> PUMP_CIRC_BIT_SHIFT) & 1
        self.pump_status[2] = self.circ_pump_status  # Circ Pump is controllable
        self.autoCirc = (data[PUMP_FIELD_1] >> AUTO_CIRC) & 1
        self.manualCirc = (data[PUMP_FIELD_1] >> MANUAL_CIRC) & 1

        TBD_FIELD_4 = (
            4  # 5 when everything off. 69 when clear ray / circulation pump on?
        )
        TBD_4_CIRC_SHIFT = (
            6  # Field 4 goes up by 64 when circulation pump is running, it seems
        )

        self.unknownCirc = (data[TBD_FIELD_4] >> TBD_4_CIRC_SHIFT) & 1

        SET_TEMP_FIELD = 4  # Multiply by 2 if in F, otherwise C
        settemp = int(data[SET_TEMP_FIELD])
        self.settemp = set_temp_convert[settemp]

        self.tempsensor1 = data[3]
        self.tempsensor2 = data[9]

        TEMP_FEILD_2 = 14  # Appears to be 2nd temp sensor C  or F directly. Changes when pump is on!
        temp = float(data[TEMP_FEILD_2])
        if self.circ_pump_status == 1:  # Unclear why this is necessary
            temp = temp + 32
        self.temp2 = temp  # Hide the data here for now

        TEMP_FIELD_1 = 3  # Divide by 2 if in C, otherwise F
        self.tempField = data[3]
        self.curtemp = temp_convert[data[3]]

        HEATER_FIELD_1 = 10  # = 64 when Heat on
        HEATER_SHIFT_1 = 6  # b1000000 when Heat on

        self.heatstate = (data[HEATER_FIELD_1] >> HEATER_SHIFT_1) & 1

        HEATER_FIELD_2 = 11  # = 2 when Heat on
        HEATER_SHIFT_1 = 1  # b10 when Heat on

        self.heatState2 = (data[HEATER_FIELD_2] >> HEATER_SHIFT_1) & 1

        DISPLAY_FIELD = 13
        DISPLAY_MAP = [
            [36, "Temp"],
            [35, "PF"],
            [47, "SF"],
            [42, "Heat"],
            [53, "FC"],
            [48, "UV"],
            [51, "H2O"],
            [62, "Time"],
            [59, "Date"],
            [0, "Temp"],
            [3, "Lang"],
            [14, "Lock"],
        ]

        # TODO Convert to text
        self.displayText = data[DISPLAY_FIELD]

        HEAT_MODE_FIELD = 6  #
        HEAT_MODE_MAP = [
            [32, "AUTO"],
            [34, "ECO"],
            [36, "DAY"],
        ]

        # TODO Convert to text
        self.heatMode = data[HEAT_MODE_FIELD]

        DATE_FIELD_1 = 2  # Don't know how to use this yet...
        DATE_FIELD_2 = 7
        DAY_SHIFT = 3  # Shift date field 2 by this amount to get day of month
        MONTH_AND = 7  # Shift date field 2 by this to get month of year
        # YEAR Dont have a guess yet

        self.day = data[DATE_FIELD_2] >> DAY_SHIFT
        self.month = data[DATE_FIELD_2] & MONTH_AND
        # TBD self.year =

        # TODO DOUBLE CHECK THIS!
        self.pump_status[0] = (data[DATE_FIELD_1] >> 4) & 1

        UNKOWN_FIELD_3 = 3  # Always 145? Might might be days untill water refresh, UV, or filter change

        self.UnknownField3 = data[UNKOWN_FIELD_3]

        UNKOWN_FIELD_9 = (
            9  # Always 107? Might be days untill water refresh, UV, or filter change
        )

        self.UnknownField9 = data[UNKOWN_FIELD_9]

        # Check that targetTemp is setTemp
        sendCmd = False
        if (
            self.settemp != self.targetTemp
            and self.targetTemp != NO_CHANGE_REQUESTED
            and self.checkCounter > CHECKS_BEFORE_RETRY
        ):
            if self.targetTemp < self.settemp:
                print(
                    "Set temp ({}C) is higher than target temp ({}C) - Sending temp down button".format(
                        self.settemp, self.targetTemp
                    )
                )
                await self.send_CCmessage(button_codes["temp_down"])  # Temp Down Key
            else:
                print(
                    "Set temp ({}C) is lower than target temp ({}C) - Sending temp up button".format(
                        self.settemp, self.targetTemp
                    )
                )
                await self.send_CCmessage(button_codes["temp_up"])  # Temp Up Key
            self.checkCounter = 0
        elif self.settemp == self.targetTemp:
            self.targetTemp = NO_CHANGE_REQUESTED
        else:
            sendCmd = True

        for i in range(0, len(self.target_pump_status)):
            if (
                self.pump_status[i] != self.target_pump_status[i]
                and self.target_pump_status[i] != NO_CHANGE_REQUESTED
            ):
                if self.checkCounter > CHECKS_BEFORE_RETRY:
                    if i == 0:
                        await self.send_CCmessage(228)  # Pump 1 Button
                    elif i == 1:
                        await self.send_CCmessage(229)  # Pump 2 Button
                    else:
                        await self.send_CCmessage(239)  # Clear Ray / Circulating Pump
                    self.checkCounter = NO_CHANGE_REQUESTED
            elif self.pump_status[i] == self.target_pump_status[i]:
                self.target_pump_status[i] = -1
            else:
                sendCmd = True

        if sendCmd:
            self.checkCounter += 1

        if not have_new_data:
            return
        self.log.info("C4{}".format(data))

        self.lastupd = time.time()
        # Populate prior_status
        for i in range(0, len(data)):
            self.prior_status[i] = data[i]
        await self.int_new_data_cb()

    async def parse_CA_light_status_update(self, data):
        """Parse a status update from the spa.
        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
        7E 22 FF AF CA 8A 36 CA CB C4 C5 C6 FB C0 C1 C2 3C DC DD DE DF D8 D9 DA DB D4 D5 D6 D7 D0 D1 D2 D3 EC E5 7E
        """
        # "Decrypt" the message
        data = self.xormsg(data[5 : len(data) - 2])

        """Parse a status update from the spa.
        01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29
        TODO Example after decryption
        """
        # TODO: The rest...

        LIGHT_MODE_FIELD = 0  # TBD
        DISPLAY_MAP = [
            [128, "Fast Blend"],  # With 2 second constant
            [127, "Slow Blend"],  # With 4 second constant
            [255, "Frozen Blend"],
            [2, "BLue"],
            [7, "Violet"],
            [6, "Red"],
            [8, "Amber"],
            [3, "Green"],
            [9, "Aqua"],
            [1, "White"],
        ]

        self.lightBrightnes = data[1]
        self.lightMode = data[4]
        self.lightB = data[2]
        self.lightG = data[6]
        self.lightR = data[8]
        self.lightCycleTime = data[9]
        self.lightUnknown1 = data[0]
        self.lightUnknown3 = data[3]
        self.lightUnknown4 = data[5]
        self.lightUnknown7 = data[7]
        self.lightUnknown9 = data[9]

        have_new_data = False
        if self.CAprior_status is not None:
            for i in range(0, len(data)):
                if data[i] != self.CAprior_status[i]:
                    have_new_data = True
                    break
        else:
            have_new_data = True
            self.CAprior_status = bytearray(len(data))

        if not have_new_data:
            return
        self.log.info("CA{}".format(data))
        for i in range(0, len(data)):
            self.CAprior_status[i] = data[i]

    async def setMyChan(self, chan):
        self.channel = chan
        self.log.info("Got assigned channel = {}".format(self.channel))
        message_length = 7
        self.NTS = bytearray(9)
        self.NTS[0] = M_STARTEND
        self.NTS[1] = message_length
        self.NTS[2] = self.channel
        self.NTS[3] = 0xBF
        self.NTS[4] = CC_REQ
        self.NTS[5] = 0  # cDummy
        self.NTS[6] = 0
        self.NTS[7] = self.balboa_calc_cs(
            self.NTS[1:message_length], message_length - 1
        )
        self.NTS[8] = M_STARTEND

    async def listen(self):
        """Listen to the spa babble forever."""

        # teststring = "7E25FFAF161012270B16420026FA260A140181000042011C00098000000A000000FF0000002F7E"
        # data = bytes.fromhex(teststring)
        # await self.parse_C4status_update(data)

        # return

        while True:
            if not self.connected:
                # Sleep and hope the checker fixes us
                await asyncio.sleep(5)
                continue

            data = await self.read_one_message()
            if data is None:
                # await asyncio.sleep(0.0001)
                continue

            channel = data[2]
            mid = data[3]
            mtype = data[4]

            if mtype == STATUS_UPDATE:
                await self.parse_C4status_update(data)
            elif mtype == LIGHTS_UPDATE:
                await self.parse_CA_light_status_update(data)
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
            elif mtype == CHANNEL_ASSIGNMENT_RESPONCE:
                # TODO Check for magic numbers to be repeated back
                await self.setMyChan(data[5])
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
                print("Existing Client")
                message_length = 8
                data = bytearray(9)
                data[0] = M_STARTEND
                data[1] = message_length
                data[2] = self.channel
                data[3] = 0xBF
                data[4] = EXISTING_CLIENT_RESPONCE  # type
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
                    # print("Discovered Channels:" + str(self.discoveredChannels))
                elif channel == self.channel:
                    if self.queue.empty():
                        # self.writer.write(self.NTS)
                        await self.writer.drain()
                    else:
                        msg = self.queue.get()
                        self.writer.write(msg)
                        await self.writer.drain()
                        # print("sent")
            else:
                if mtype == CC_REQ:
                    if not channel in self.activeChannels:
                        self.activeChannels.append(data[2])
                        print("Active Channels:" + str(self.activeChannels))
                    elif (
                        self.detectChannelState < DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND
                    ):
                        self.detectChannelState += 1
                        # print(self.detectChannelState)
                        if (
                            self.detectChannelState
                            == DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND
                        ):
                            self.discoveredChannels.sort()
                            # print("Discovered Channels:" + str(self.discoveredChannels))
                            for chan in self.discoveredChannels:
                                if not chan in self.activeChannels:
                                    await self.setMyChan(chan)
                                    break
                    if mtype == CC_REQ:
                        if (data[5]) != 0:
                            self.log.warn(
                                "Got Button Press x".format(channel, mid, mtype)
                                + "".join(map("{:02X} ".format, bytes(data)))
                            )
                elif mtype > NOTHING_TO_SEND:
                    self.log.warn(
                        "Unknown Message {:02X} {:02X} {:02X} x".format(
                            channel, mid, mtype
                        )
                        + "".join(map("{:02X} ".format, bytes(data)))
                    )

    async def spa_configured(self):
        return True

    async def listen_until_configured(self, maxiter=20):
        """Listen to the spa babble until we are configured."""
        return True

    def string_to_hex(string):
        base16INT = int(str, 16)
        hex_value = hex(base16INT)
        return hex_value

    def get_day(self):
        return self.day

    def get_month(self):
        return self.month

    def get_year(self):
        return self.year

    def get_temp2(self):
        return self.temp2

    def get_manualCirc(self):
        return self.manualCirc

    def get_autoCirc(self):
        return self.autoCirc

    def get_unknownCirc(self):
        return self.unknownCirc

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

    def get_LightBrightnes(self):
        return self.LightBrightnes

    def get_lightMode(self):
        return self.lightMode

    def get_lightR(self):
        return self.lightR

    def get_lightG(self):
        return self.lightG

    def get_lightB(self):
        return self.lightB
