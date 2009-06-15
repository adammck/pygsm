#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


import time


class MockDevice(object):

    print_traffic = False
    echo = True


    def __init__(self):
        self.buf_read = []
        self.buf_write = []


    def _debug(self, str):
        """If self.print_traffic is True, prints
           _str_ to STDOUT. Otherwise, does nothing."""

        if self.print_traffic:
            print str


    def read(self, size=1):
        """Reads and returns _size_ characters from the read buffer, which
           represents the output of the "serial port" of this "modem". This
           method is a very rough port of Serial.write."""

        read = ""

        # keep on reading until we have _size_
        # number of characters/bytes
        while len(read) < size:
            if len(self.buf_read):
                read += self.buf_read.pop(0)

            # wait until some data
            # is available to read
            else:
                time.sleep(0.1)

        self._debug("READ (%d): %r" % (size, read))
        return read


    def write(self, str):
        """Appends _str_ to the write buffer, which represents input to this "modem".
           If _str_ ends with a GSM command terminator (\r), the contents of the write
           buffer are passed on to self._process."""

        self._debug("WRITE: %r" % (str))

        # push each character
        # to the write buffer
        for char in str:
            self.buf_write.append(char)

            # if character echo is currently ON, also
            # push this character back to read buffer
            if self.echo:
                self.buf_read.append(char)

        # if the last character is a terminator, process
        # the current contents of the buffer, and clear it.
        # TODO: this doesn't work if "AT\rAT\rAT\r" if passed.
        if self.buf_write[-1] == "\r":
            self._process("".join(self.buf_write))
            self.buf_write = []

        return True


    def _process(self, cmd):
        """Receives a command, and passes it on to self.process, which should be defined
           by subclasses to respond to the command(s) which their testcase is interested
           in, and return True or False when done. If the call succeeds, this method will
           call self._ok -- otherwise, calls self._error."""

        self._debug("CMD: %r" % (cmd))

        # we can probably ignore whitespace,
        # even though a modem never would
        cmd = cmd.strip()

        # attempt to hand off this
        # command to the subclass
        if hasattr(self, "process"):
            if self.process(cmd):
                return self._ok()

        # this modem has no "process" method,
        # or it was called and failed. either
        # way, report an unknown error
        return self._error()


    def _output(self, str):
        """Insert a GSM response into the read buffer, with leading and
           trailing terminators (\r\n). This spews whitespace everywhere,
           but is (curiously) how most modems work."""

        self.buf_read.extend(["\r", "\n", str, "\r", "\n"])
        return True


    def _ok(self):
        """Insert a GSM "OK" string into the read buffer.
           This should be called when a command succeeds."""

        self._output("OK")
        return True


    def _error(self):
        """Insert a GSM "ERROR" string into the read buffer.
           This should be called when a command fails."""

        self._output("ERROR")
        return False
