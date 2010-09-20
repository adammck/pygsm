#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
# see LICENSE file (it's BSD)


from __future__ import with_statement

import re, csv, datetime, time
import errors, message
import traceback
import StringIO
import threading

# arch: pacman -S python-pyserial
# debian: apt-get install pyserial
import serial

# Constants
CMGL_STATUS="REC UNREAD"
CMGL_MATCHER=re.compile(r'^\+CMGL: (\d+),"(.+?)","(.+?)",.*?,"(.+?)".*?$')


class GsmModem(object):
    """
    pyGSM is a Python module which uses pySerial to provide a nifty
    interface to send and receive SMS via a GSM Modem. It was ported
    from RubyGSM, and provides (almost) all of the same features. It's
    easy to get started:

      # create a GsmModem object:
      >>> modem = pygsm.GsmModem(port="/dev/ttyUSB0")

      # harass Evan over SMS:
      # (try to do this before 11AM)
      >>> modem.send_sms(*REDACTED*, "Hey, wake up!")

      # check for incoming SMS:
      >>> print modem.next_message()
      <pygsm.IncomingMessage from *REDACTED*: "Leave me alone!">

    pyGSM is distributed via GitHub:
    http://github.com/adammck/pygsm

    Bug reports (especially for
    unsupported devices) are welcome:
    http://github.com/adammck/pygsm/issues
    """


    # override these after init, and
    # before boot. they're not sanity
    # checked, so go crazy.
    cmd_delay = 0.1
    retry_delay = 2
    max_retries = 10
    _modem_lock = threading.RLock()


    def __init__(self, *args, **kwargs):
        """
        Create a GsmModem object. All of the arguments are passed along
        to serial.Serial.__init__ when GsmModem.connect is called. For
        all of the possible configration options, see:

        http://pyserial.wiki.sourceforge.net/pySerial#tocpySerial10

        Alternatively, a single 'device' kwarg can be passed, which
        overrides the default proxy-args-to-pySerial behavior. This is
        useful when testing, or wrapping the serial connection with some
        custom logic.

        NOTE: The serial connection isn't created until GsmModem.connect
        is called. It might still fail (but should raise GsmConnectError
        when it does so.)
        """

        if "logger" in kwargs:
            self.logger = kwargs.pop("logger")

        # if a ready-made device was provided, store it -- self.connect
        # will see that we're already connected, and do nothing. we'll
        # just assume it quacks like a serial port
        if "device" in kwargs:
            self.device = kwargs.pop("device")

            # if a device is given, the other args are never
            # used, so were probably included by mistake.
            if len(args) or len(kwargs):
                raise(TypeError("__init__() does not accept other arguments when a 'device' is given"))

        # for regular serial connections, store the connection args, since
        # we might need to recreate the serial connection again later
        else:
            self.device = None
            self.device_args = args
            self.device_kwargs = kwargs

        # to cache parts of multi-part messages
        # until the last part is delivered
        self.multipart = {}

        # to store unhandled incoming messages
        self.incoming_queue = []


    LOG_LEVELS = {
        "traffic": 4,
        "read":    4,
        "write":   4,
        "debug":   3,
        "warn":    2,
        "error":   1 }


    def _log(self, msg_str, event_type="debug"):
        """
        Proxy a log message to this Modem's logger, if one has been set.
        This is useful for applications embedding pyGSM that wish to
        show or log what's going on inside.

        The 'logger' should be a function with three arguments:
            modem:      a reference to this GsmModem instance
            msg_str:    the log message (a unicode string)
            event_type: a string contaning one of the keys
                        of GsmModem.LOG_LEVELS, indicating
                        the importance of this message.

        GsmModem.__init__ accepts an optional 'logger' kwarg, and a
        minimal (dump to STDOUT) logger is at GsmModem.debug_logger:

        >>> GsmModem("/dev/ttyUSB0", logger=GsmModem.debug_logger)
        """

        if hasattr(self, "logger"):
            self.logger(self, msg_str, event_type)


    @classmethod
    def debug_logger(cls, modem, msg_str, event_type):
        print "%8s %s" % (event_type, msg_str)


    def connect(self, reconnect=False):
        """
        Connect to the modem via pySerial, using the args and kwargs
        provided to the constructor. If 'reconnect' is True, and the
        modem is already connected, the entire serial.Serial object is
        destroyed and re-established.

        Returns self.device, or raises GsmConnectError
        """

        self._log("Connecting")

        # if no connection exists, create it
        # the reconnect flag is irrelevant
        if not hasattr(self, "device") or (self.device is None):
            try:
                with self._modem_lock:
                    self.device = serial.Serial(
                        *self.device_args,
                        **self.device_kwargs)

            # if the connection failed, re-raise the serialexception as
            # a gsm error, so the owner of this object doesn't have to
            # worry about catching anything other than gsm exceptions
            except serial.SerialException, err:
                msg = str(err)
                if msg.startswith("could not open port"):
                    pyserial_err, real_err = msg.split(":", 1)
                    raise errors.GsmConnectError(real_err.strip())

                # other (more obscure) errors don't get their own class,
                # but wrap them in a gsmerror all the same
                else:
                    raise errors.GsmError(msg)

        # the port already exists, but if we're
        # reconnecting, then kill it and recurse
        # to recreate it. this is useful when the
        # connection has died, but nobody noticed
        elif reconnect:
            self.disconnect()
            self.connect(False)

        return self.device


    def disconnect(self):
        """Disconnect from the modem."""

        self._log("Disconnecting")

        # attempt to close and destroy the device
        if hasattr(self, "device") and (self.device is None):
            with self._modem_lock:
                if self.device.isOpen():
                    self.device.close()
                    self.device = None
                    return True

        # for some reason, the device
        # couldn't be closed. it probably
        # just isn't open yet
        return False


    def boot(self, reboot=False):
        """
        (Re-)Connect to the modem and configure it in an (often vain)
        attempt to standardize the behavior of the many vendors and
        models. Should be called before reading or writing.

        This method isn't called during __init__ (since 5f41ba6d), since
        it's often useful to create GsmModem objects without writing to
        the modem. To compensate, this method returns 'self', so it can
        be easily chained onto the constructor, like so:

        >>> gsm = GsmModem(port="whatever").boot()

        This is exactly the same as:

        >>> gsm = GsmModem(port="whatever")
        >>> gsm.boot()
        """

        self._log("Booting")

        if reboot:
            self.connect(reconnect=True)
            self.command("AT+CFUN=1")

        else:
            self.connect()

        # set some sensible defaults, to make
        # the various modems more consistant
        self.command("ATE0",      raise_errors=False) # echo off
        self.command("AT+CMEE=1", raise_errors=False) # useful error messages
        self.command("AT+WIND=0", raise_errors=False) # disable notifications
        self.command("AT+CMGF=1"                    ) # switch to TEXT mode

        return self
        # enable new message notification. (most
        # handsets don't support this; no matter)
        #self.command(
        #    "AT+CNMI=2,2,0,0,0",
        #    raise_errors=False)


    def reboot(self):
        """
        Disconnect from the modem, reconnect, and reboot it (AT+CFUN=1,
        which clears all volatile state). This drops the connection to
        the network, so it's wise to call _GsmModem.wait_for_network_
        after rebooting.
        """

        self.boot(reboot=True)


    def _write(self, str_):
        """Write a string to the modem."""

        self._log(repr(str_), "write")

        try:
            self.device.write(str_)

        # if the device couldn't be written to,
        # wrap the error in something that can
        # sensibly be caught at a higher level
        except OSError, err:
            raise(errors.GsmWriteError)


    def _read(self, read_term=None, read_timeout=None):
        """
        Keep reading and buffering characters from the modem (blocking)
        until 'read_term' (which defaults to \r\n, to read a single
        "line") is hit, then return the buffer.
        """

        buffer = []

        # if a different timeout was requested just
        # for _this_ read, store and override the
        # current device setting (not thread safe!)
        if read_timeout is not None:
            old_timeout = self.device.timeout
            self.device.timeout = read_timeout

        def __reset_timeout():
            """restore the device's previous timeout
               setting, if we overrode it earlier."""
            if read_timeout is not None:
                self.device.timeout =\
                    old_timeout

        # the default terminator reads
        # until a newline is hit
        if not read_term:
            read_term = "\r\n"

        while(True):
            buf = self.device.read()
            buffer.append(buf)

            # if a timeout was hit, raise an exception including the raw data that
            # we've already read (in case the calling func was _expecting_ a timeout
            # (wouldn't it be nice if serial.Serial.read returned None for this?)
            if buf == "":
                __reset_timeout()
                raise(errors.GsmReadTimeoutError(buffer))

            # if last n characters of the buffer match the read
            # terminator, return what we've received so far
            if buffer[-len(read_term)::] == list(read_term):
                buf_str = "".join(buffer)
                __reset_timeout()

                self._log(repr(buf_str), "read")
                return buf_str


    def _wait(self, read_term=None, read_timeout=None):
        """
        Read (blocking) from the modem, one line at a time, until a
        response terminator ("OK", "ERROR", or "CMx ERROR...") is hit,
        then return a list containing the lines.
        """

        buffer = []

        # keep on looping until a response terminator
        # is encountered. these are NOT the same as the
        # "read_term" argument - only OK or ERROR is valid
        while(True):
            buf = self._read(
                read_term=read_term,
                read_timeout=read_timeout)

            buf = buf.strip()
            buffer.append(buf)

            # most commands return OK for success, but there
            # are some exceptions. we're not checking those
            # here (unlike RubyGSM), because they should be
            # handled when they're _expected_
            if buf == "OK":
                return buffer

            # some errors contain useful error codes, so raise a
            # proper error with a description from pygsm/errors.py
            m = re.match(r"^\+(CM[ES]) ERROR: (\d+)$", buf)
            if m is not None:
                type, code = m.groups()
                raise(errors.GsmModemError(type, int(code)))

            # ...some errors are not so useful
            # (at+cmee=1 should enable error codes)
            if buf == "ERROR":
                raise(errors.GsmModemError)

            # some (but not all) huawei e220s (an otherwise splendid
            # modem) return this useless and non-standard error
            if buf == "COMMAND NOT SUPPORT":
                raise(errors.GsmModemError)


    _SCTS_FMT = "%y/%m/%d,%H:%M:%S"

    def _parse_incoming_timestamp(self, timestamp):
        """
        Parse a Service Center Time Stamp (SCTS) string into a Python
        datetime object, or None if the timestamp couldn't be parsed.
        The SCTS format does not seem to be standardized, but looks
        something like: YY/MM/DD,HH:MM:SS.
        """

        # timestamps usually have trailing timezones, measured
        # in 15-minute intervals (?!), which is not handled by
        # python's datetime lib. if _this_ timezone does, chop
        # it off, and note the actual offset in minutes
        tz_pattern = r"\-(\d+)$"
        m = re.search(tz_pattern, timestamp)
        if m is not None:
            timestamp = re.sub(tz_pattern, "", timestamp)
            tz_offset = datetime.timedelta(minutes=int(m.group(0)) * 15)

        # we won't be modifying the output, but
        # still need an empty timedelta to subtract
        else: tz_offset = datetime.timedelta()

        # attempt to parse the (maybe modified) timestamp into
        # a time_struct, and convert it into a datetime object
        try:
            time_struct = time.strptime(timestamp, self._SCTS_FMT)
            dt = datetime.datetime(*time_struct[:6])

            # patch the time to represent LOCAL TIME, since
            # the datetime object doesn't seem to represent
            # timezones... at all
            return dt - tz_offset

        # if the timestamp couldn't be parsed, we've encountered
        # a format the pyGSM doesn't support. this sucks, but isn't
        # important enough to explode like RubyGSM does
        except ValueError:
            return None


    def _parse_incoming_sms(self, lines):
        """
        Parse a list of 'lines' (output of GsmModem._wait), to extract
        any incoming SMS and append them to _GsmModem.incoming_queue_.
        Returns the same lines with the incoming SMS removed. Other
        unsolicited data may remain, which must be cropped separately.
        """

        output_lines = []
        n = 0

        # iterate the lines like it's 1984
        # (because we're patching the array,
        # which is hard work for iterators)
        while n < len(lines):

            # not a CMT string? add it back into the
            # output (since we're not interested in it)
            # and move on to the next
            if lines[n][0:5] != "+CMT:":
                output_lines.append(lines[n])
                n += 1
                continue

            # since this line IS a CMT string (an incoming
            # SMS), parse it and store it to deal with later
            m = re.match(r'^\+CMT: "(.+?)",.*?,"(.+?)".*?$', lines[n])
            if m is None:

                # couldn't parse the string, so just move
                # on to the next line. TODO: log this error
                n += 1
                next

            # extract the meta-info from the CMT line,
            # and the message from the FOLLOWING line
            sender, timestamp = m.groups()
            text = lines[n+1].strip()

            # notify the network that we accepted
            # the incoming message (for read receipt)
            # BEFORE pushing it to the incoming queue
            # (to avoid really ugly race condition if
            # the message is grabbed from the queue
            # and responded to quickly, before we get
            # a chance to issue at+cnma)
            try:
                self.command("AT+CNMA")

            # Some networks don't handle notification, in which case this
            # fails. Not a big deal, so ignore.
            except errors.GsmError:
                #self.log("Receipt acknowledgement (CNMA) was rejected")
                # TODO: also log this!
                pass

            # (i'm using while/break as an alternative to catch/throw
            # here, since python doesn't have one. we might abort early
            # if this is part of a multi-part message, but not the last
            while True:

                # multi-part messages begin with ASCII 130 followed
                # by "@" (ASCII 64). TODO: more docs on this, i wrote
                # this via reverse engineering and lost my notes
                if (ord(text[0]) == 130) and (text[1] == "@"):
                    part_text = text[7:]

                    # ensure we have a place for the incoming
                    # message part to live as they are delivered
                    if sender not in self.multipart:
                        self.multipart[sender] = []

                    # append THIS PART
                    self.multipart[sender].append(part_text)

                    # abort if this is not the last part
                    if ord(text[5]) != 173:
                        break

                    # last part, so switch out the received
                    # part with the whole message, to be processed
                    # below (the sender and timestamp are the same
                    # for all parts, so no change needed there)
                    text = "".join(self.multipart[sender])
                    del self.multipart[sender]

                # store the incoming data to be picked up
                # from the attr_accessor as a tuple (this
                # is kind of ghetto, and WILL change later)
                self._add_incoming(timestamp, sender, text)

                # don't loop! the only reason that this
                # "while" exists is to jump out early
                break

            # jump over the CMT line, and the
            # text line, and continue iterating
            n += 2

        # return the lines that we weren't
        # interested in (almost all of them!)
        return output_lines


    def _add_incoming(self, timestamp, sender, text):

        # since neither message notifications nor messages
        # fetched from storage give any indication of their
        # encoding, we're going to have to guess. if the
        # text has a multiple-of-four length and starts
        # with a UTF-16 Byte Order Mark, try to decode it
        # into a unicode string
        try:
            if (len(text) % 4 == 0) and (len(text) > 0):
                if re.match('^[0-9A-F]+$', text):

                    # insert a bom if there isn't one
                    bom = text[:4].lower()
                    if bom != "fffe" and bom != "feff":
                        text = "feff" + text

                    # decode the text into a unicode string,
                    # so developers embedding pyGSM need never
                    # experience this confusion and pain
                    text = text.decode("hex").decode("utf-16")

        # oh dear. it looked like hex-encoded utf-16,
        # but wasn't. who sends a message like that?!
        except:
            pass

        # create and store the IncomingMessage object
        self._log("Adding incoming message")
        time_sent = self._parse_incoming_timestamp(timestamp)
        msg = message.IncomingMessage(self, sender, time_sent, text)
        self.incoming_queue.append(msg)
        return msg


    def command(self, cmd, read_term=None, read_timeout=None, write_term="\r", raise_errors=True):
        """
        Issue an AT command to the modem, and return the sanitized
        response. Sanitization removes status notifications, command
        echo, and incoming messages, (hopefully) leaving only the actual
        response to the command.

        If Error 515 (init or command in progress) is returned, the
        command is automatically retried up to 'GsmModem.max_retries'
        times.
        """

        # keep looping until the command
        # succeeds or we hit the limit
        retries = 0
        while retries < self.max_retries:
            try:

                # issue the command, and wait for the
                # response
                with self._modem_lock:
                    self._write(cmd + write_term)
                    lines = self._wait(
                        read_term=read_term,
                        read_timeout=read_timeout)

                # no exception was raised, so break
                # out of the enclosing WHILE loop
                break

            # Outer handler: if the command caused an error,
            # maybe wrap it and return None
            except errors.GsmError, err:

                # if GSM Error 515 (init or command in progress) was raised,
                # lock the thread for a short while, and retry. don't lock
                # the modem while we're waiting, because most commands WILL
                # work during the init period - just not _cmd_
                if getattr(err, "code", None) == 515:
                    time.sleep(self.retry_delay)
                    retries += 1
                    continue

                # if raise_errors is disabled, it doesn't matter
                # *what* went wrong - we'll just ignore it
                if not raise_errors:
                    return None

                # otherwise, allow errors to propagate upwards,
                # and hope someone is waiting to catch them
                else: raise(err)

        # if the first line of the response echoes the cmd
        # (it shouldn't, if ATE0 worked), silently drop it
        if lines[0] == cmd:
            lines.pop(0)

        # remove all blank lines and unsolicited
        # status messages. i can't seem to figure
        # out how to reliably disable them, and
        # AT+WIND=0 doesn't work on this modem
        lines = [
            line
            for line in lines
            if line      != "" or\
               line[0:6] == "+WIND:" or\
               line[0:6] == "+CREG:" or\
               line[0:7] == "+CGRED:"]

        # parse out any incoming sms that were bundled
        # with this data (to be fetched later by an app)
        lines = self._parse_incoming_sms(lines)

        # rest up for a bit (modems are
        # slow, and get confused easily)
        time.sleep(self.cmd_delay)

        return lines


    def query_list(self, cmd, prefix=None):
        """
        Issue a single AT command to the modem, checks that the last
        line of the response is "OK", and returns a list containing the
        other lines. An empty list is returned if a command fails, so
        the output of this method can always be assumed to be iterable.

        The 'prefix' argument can optionally specify a string to filter
        the output lines by. Matching lines are returned (sans prefix),
        and the rest are dropped.

        Most AT commands return a single line, which is better handled
        by GsmModem.query, which returns a single value.
        """

        # issue the command, which might return incoming
        # messages, but we'll leave them in the queue
        lines = self.command(cmd, raise_errors=False)

        # check that the query was successful
        # if not, we'll skip straight to return
        if lines is not None and lines[-1] == "OK":

            # if a prefix was provided, return all of the
            # lines (except for OK) that start with _prefix_
            if prefix is not None:
                return [
                    line[len(prefix):].strip()
                    for line in lines[:-1]
                    if line[:len(prefix)] == prefix]

            # otherwise, return all lines
            # (except for the trailing OK)
            else:
                return lines[:-1]

        # something went wrong, so return the very
        # ambiguous None. it's better than blowing up
        return None


    def query(self, cmd, prefix=None):
        """
        Issue an AT command to the modem, and returns the relevant part
        of the response. This only works for commands that return a
        single line followed by "OK", but conveniently, this covers
        almost all AT commands that I've ever needed to use. Example:

        >>> modem.query("AT+CSQ")
        "+CSQ: 20,99"

        Optionally, the 'prefix' argument can specify a string to check
        for at the beginning of the output, and strip it from the return
        value. This is useful when you want to both verify that the
        output was as expected, but ignore the prefix. For example:

        >>> modem.query("AT+CSQ", prefix="+CSQ:")
        "20,99"

        For all unexpected responses (errors, no output, or too much
        output), returns None.
        """

        lines = self.query_list(cmd, prefix)
        return lines[0] if len(lines) == 1 else None


    def _csv_str(self, out):
        """
        Many queries will return comma-separated output, which is not
        formally specified (far as I can tell), but strongly resembles
        CSV. This method splits the output of self.query into a list. No
        typecasting is performed on the elements -- they're all strings,
        as returned by the Python CSV module. For example:

        >>> modem.query("AT+COPS?", prefix="+COPS:", split_output=True)
        ["0", "0", "MTN Rwanda", "2"]

        If the string couldn't be parsed, GsmParseError is raised.
        """

        try:
            # parse the query output as if it were a single-line
            # csv file. override line terminator in case there
            # are any \r\n terminators within the output
            reader = csv.reader([out], lineterminator="\0\0")

            # attempt to return the parsed row. this will raise
            # an internal _csv.Error exception if the string is
            # badly formed, which we will wrap, below
            return list(reader)[0]

        except:
            raise errors.GsmParseError(out)


    def send_sms(self, recipient, text):
        """
        Send an SMS to 'recipient' containing 'text'. Some networks will
        automatically split long messages into multiple parts, and join
        them upon delivery -- but some will silently drop them. pyGSM
        does nothing to avoid this (for now), so try to keep 'text'
        under 160 characters.
        """

        old_mode = None
        with self._modem_lock:
            try:
                try:
                    # cast the text to a string, to check that
                    # it doesn't contain non-ascii characters
                    try:
                        text = str(text)

                    # uh-oh. unicode ahoy
                    except UnicodeEncodeError:

                        # fetch and store the current mode (so we can
                        # restore it later), and override it with UCS2
                        csmp = self.query("AT+CSMP?", "+CSMP:")
                        if csmp is not None:
                            old_mode = csmp.split(",")
                            mode = old_mode[:]
                            mode[3] = "8"

                            # enable hex mode, and set the encoding
                            # to UCS2 for the full character set
                            self.command('AT+CSCS="HEX"')
                            self.command("AT+CSMP=%s" % ",".join(mode))
                            text = text.encode("utf-16").encode("hex")

                    # initiate the sms, and give the device a second
                    # to raise an error. unfortunately, we can't just
                    # wait for the "> " prompt, because some modems
                    # will echo it FOLLOWED BY a CMS error
                    result = self.command(
                        'AT+CMGS=\"%s\"' % (recipient),
                        read_timeout=1)

                # if no error is raised within the timeout period,
                # and the text-mode prompt WAS received, send the
                # sms text, wait until it is accepted or rejected
                # (text-mode messages are terminated with ascii char 26
                # "SUBSTITUTE" (ctrl+z)), and return True (message sent)
                except errors.GsmReadTimeoutError, err:
                    if err.pending_data[0] == ">":
                        self.command(text, write_term=chr(26))
                        return True

                    # a timeout was raised, but no prompt nor
                    # error was received. i have no idea what
                    # is going on, so allow the error to propagate
                    else:
                        raise

            # for all other errors...
            # (likely CMS or CME from device)
            except Exception, err:

                # whatever went wrong, break out of the
                # message prompt. if this is missed, all
                # subsequent writes will go into the message!
                self._write(chr(27))

                # rule of thumb: pyGSM is meant to be embedded,
                # so DO NOT EVER allow exceptions to propagate
                # (obviously, this sucks. there should be an
                # option, at least, but i'm being cautious)
                return None

            finally:

                # if the mode was overridden above, (if this
                # message contained unicode), switch it back
                if old_mode is not None:
                    self.command("AT+CSMP=%s" % ",".join(old_mode))
                    self.command('AT+CSCS="GSM"')


    def hardware(self):
        """
        Return a dict of containing information about the modem. The
        contents of each value are entirely manufacturer-dependant, and
        can vary wildly between devices.
        """

        return {
            "manufacturer": self.query("AT+CGMI"),
            "model":        self.query("AT+CGMM"),
            "revision":     self.query("AT+CGMR"),
            "serial":       self.query("AT+CGSN") }


    def _get_service_center(self):

        # fetch the current service center,
        # which returns something like:
        # +CSCA: "+250788110333",145
        data = self.query("AT+CSCA?")
        if data is not None:

            # extract the service center number
            # (the first argument) from the output
            md = re.match(r'^\+CSCA:\s+"(\+?\d+)",', data)
            if md is not None:
                return md.group(1)

        # if we have not returned yet, something
        # went wrong. this modem probably doesn't
        # support AT+CSCA, so return None/unknown
        return None

    def _set_service_center(self, value):
        self.command(
            'AT+CSCA="%s"' % value,
            raise_errors=False)

    # allow the service center to be get or set like an attribute,
    # while transparently reconfiguring the modem behind the scenes
    service_center =\
        property(
            _get_service_center,
            _set_service_center,
            doc=\
        """
        Get or set the service center address currently in use by the
        modem. Returns None if the modem does not support the AT+CSCA
        command.
        """)


    @property
    def _known_networks(self):
        """
        Return a dict containing all networks known to this modem, keyed
        by their numeric ID, valued by their alphanumeric operator name.
        This is not especially useful externally, but is used internally
        to resolve operator IDs to their alphanumeric name.

        Many devices can do this internally, via the AT+WOPN command,
        but the Huawei dongle I'm on today happens not to support that,
        and I expect many others are the same.

        This method will always return a dict (even if it's empty), and
        caches its own output, since it can be quite slow and large.
        """

        # if the cache hasn't already been built, do so
        if not hasattr(self, "_known_networks_cache"):
            self._known_networks_cache = {}

            try:

                # fetch a list of ALL networks known to this modem,
                # which returns a CME error (caught below) or many
                # lines in the format:
                #   +COPN: <NumOper>, <AlphaOper>
                #   +COPN: <NumOper>, <AlphaOper>
                #   ...
                #   OK
                #
                # where <NumOper> is the numeric operator ID
                # where <AlphaOper> is long alphanumeric operator name
                lines = self.query_list("AT+COPN", "+COPN:")

                # parse each line into a two-element
                # array, and cast the result to a dict
                self._known_networks_cache =\
                    dict(map(self._csv_str, lines))

            # if anything went wrong (and many things can)
            # during this operation, we will return the empty,
            # dict to indicate that we don't know _any_ networks
            except errors.GsmError:
                pass

        return self._known_networks_cache


    _PLMN_MODES = {
        "0": "(Automatic)",
        "1": "(Manual)",
        "2": "(Deregistered)",
        "3": "(Unreadable)"
    }

    @property
    def network(self):
        """
        Return the name of the currently selected GSM network.
        """

        # fetch the current PLMN (Public Land Mobile Network)
        # setting, which should return something like:
        #   +COPS: <mode> [, <format>, <oper>]
        #
        # where <mode> is one of:
        #   0 - automatic (default)
        #   1 - manual
        #   2 - deregistered
        #   3 - set only (the network cannot be read, only set)
        #
        # where <format> is one of:
        #   0 - long alphanumeric
        #   1 - short alphanumeric
        #   2 - numeric (default)
        #
        # and <oper> is the operator identifier in the format
        # specified by <format>

        data = self.query("AT+COPS?", "+COPS:")
        if data is not None:

            # parse the csv-style output
            fields = self._csv_str(data)

            # if the operator fields weren't returned (ie, "+COPS: 0"),
            # just return a rough description of what's going on
            if len(fields) == 1:
                return self._PLMN_MODES[fields[0]]

            # if the <oper> was in long or short alphanumerics,
            # (according to <format>), return it as-is. this
            # happens when the network is unknown to the modem
            elif fields[1] in ["0", "1"]:
                return fields[2]

            # if the <oper> was numeric, we're going to
            # have to look up the PLMN string separately.
            # return if it's known, or fall through to None
            elif fields[1] == "2":
                network_id = fields[2]
                if network_id in self._known_networks:
                    return self._known_networks[network_id]

        # if we have not returned yet, something wernt
        # wrong during the query or parsing the response
        return None


    def signal_strength(self):
        """
        Return an integer between 1 and 99, representing the current
        signal strength of the GSM network, False if we don't know, or
        None if the modem can't report it.
        """

        data = self.query("AT+CSQ")
        if data is not None:

            # extract the signal strength (the
            # first argument) from the output
            md = re.match(r"^\+CSQ: (\d+),", data)

            # 99 represents "not known or not detectable". we'll
            # return False for that (so we can test it for boolean
            # equality), or an integer of the signal strength.
            if md is not None:
                csq = int(md.group(1))
                return csq if csq < 99 else False

        # the response from AT+CSQ couldn't be parsed. return
        # None, so we can test it in the same way as False, but
        # check the type without raising an exception
        return None


    def wait_for_network(self):
        """
        Block until the signal strength indicates that the device is
        active on the GSM network. It's a good idea to call this before
        trying to send or receive anything.
        """

        while True:
            csq = self.signal_strength()
            if csq: return csq
            time.sleep(1)


    def ping(self):
        """
        Send the "AT" command to the device, and return true if it is
        acknowledged. Since incoming notifications and messages are
        intercepted automatically, this is a good way to poll for new
        messages without using a worker thread like RubyGSM.
        """

        try:
            self.command("AT")
            return True

        except errors.GsmError:
            return None


    def _strip_ok(self,lines):
        """
        Strip "OK" from the end of a command response. But DON'T USE
        THIS. Parse the response properly.
        """

        if lines is not None and len(lines)>0 and \
                lines[-1]=='OK':
            lines=lines[:-1] # strip last entry
        return lines


    def _fetch_stored_messages(self):
        """
        Fetch stored unread messages, and add them to incoming queue.
        Return number fetched.
        """

        lines = self._strip_ok(self.command('AT+CMGL="%s"' % CMGL_STATUS))
        # loop through all the lines attempting to match CMGL lines (the header)
        # and then match NOT CMGL lines (the content)
        # need to seed the loop first
        num_found=0
        if len(lines)>0:
            m=CMGL_MATCHER.match(lines[0])

        while len(lines)>0:
            if m is None:
                # couldn't match OR no text data following match
                raise(errors.GsmReadError())

            # if here, we have a match AND text
            # start by popping the header (which we have stored in the 'm'
            # matcher object already)
            lines.pop(0)

            # now put the captures into independent vars
            index, status, sender, timestamp = m.groups()

            # now loop through, popping content until we get
            # the next CMGL or out of lines
            msg_buf=StringIO.StringIO()
            while len(lines)>0:
                m=CMGL_MATCHER.match(lines[0])
                if m is not None:
                    # got another header, get out
                    break
                else:
                    msg_buf.write(lines.pop(0))

            # get msg text
            msg_text=msg_buf.getvalue().strip()

            # now create message
            self._add_incoming(timestamp,sender,msg_text)
            num_found+=1

        return num_found


    def next_message(self, ping=True, fetch=True):
        """
        Returns the next waiting IncomingMessage object, or None if the
        queue is empty. The optional 'ping' and 'fetch' args control
        whether the modem is pinged (to allow new messages to be
        delivered instantly, on those modems which support it) and
        queried for unread messages in storage, which can both be
        disabled in case you're already polling in a separate thread.
        """

        # optionally ping the modem, to give it a
        # chance to deliver any waiting messages
        if ping:
            self.ping()

        # optionally check the storage for unread messages.
        # we must do this just as often as ping, because most
        # handsets don't support CNMI-style delivery
        if fetch:
            self._fetch_stored_messages()

        # abort if there are no messages waiting
        if not self.incoming_queue:
            return None

        # remove the message that has been waiting
        # longest from the queue, and return it
        return self.incoming_queue.pop(0)




if __name__ == "__main__":

    import sys, re
    if len(sys.argv) >= 2:

        # the first argument is SERIAL PORT
        # (required, since we have no autodetect yet)
        port = sys.argv[1]

        # all subsequent options are parsed as key=value
        # pairs, to be passed on to GsmModem.__init__ as
        # kwargs, to configure the serial connection
        conf = dict([
            arg.split("=", 1)
            for arg in sys.argv[2:]
            if arg.find("=") > -1
        ])

        # dump the connection settings
        print "pyGSM Demo App"
        print "  Port: %s" % (port)
        print "  Config: %r" % (conf)
        print

        # connect to the modem (this might hang
        # if the connection settings are wrong)
        print "Connecting to GSM Modem..."
        modem = GsmModem(port=port, **conf).boot()
        print "Waiting for incoming messages..."

        # check for new messages every two
        # seconds for the rest of forever
        while True:
            msg = modem.next_message()

            # we got a message! respond with
            # something useless, as an example
            if msg is not None:
                print "Got Message: %r" % msg
                msg.respond("Thanks for those %d characters!" %
                    len(msg.text))

            # no messages? wait a couple
            # of seconds and try again
            else: time.sleep(2)

    # the serial port must be provided
    # we're not auto-detecting, yet
    else:
        print "Usage: python -m pygsm.gsmmodem PORT [OPTIONS]"
