#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
# see LICENSE file (it's BSD)


import unittest
import pygsm

from mock.device import MockDevice, MockSenderDevice


class TestGsmModem(unittest.TestCase):

    def testWritesNothingDuringInit(self):
        """Nothing is written to the modem during __init__"""

        device = MockDevice()
        gsm = pygsm.GsmModem(device=device)
        self.assertEqual(device.buf_write, [])


    def testKnownOperatorkName(self):
        """Long operator names are returned as-is."""

        class MockCopsDevice(MockDevice):
            def process(self, cmd):

                # return a valid +COPS response for AT+COPS?, but error
                # for other commands (except built-in MockDevice stuff)
                if cmd == "AT+COPS?":
                    return self._respond('+COPS: 0,0,"MOCK-NETWORK",0')

                return False

        device = MockCopsDevice()
        gsm = pygsm.GsmModem(device=device)
        self.assertEqual(gsm.network, "MOCK-NETWORK")


    def testUnknownOperatorName(self):
        """Unknown or missing operator names return a status string."""

        class MockCopsDevice(MockDevice):
            def process(self, cmd):

                # return a valid +COPS response for AT+COPS?, but error
                # for other commands (except built-in MockDevice stuff)
                if cmd == "AT+COPS?":
                    return self._respond('+COPS: 0')

                return False

        device = MockCopsDevice()
        gsm = pygsm.GsmModem(device=device)
        self.assertEqual(gsm.network, "(Automatic)")


    def testSendSms(self):
        """Checks that the GsmModem accepts outgoing SMS,
           when the text is within ASCII chars 22 - 126."""

        # this device is much more complicated than
        # most, so is tucked away in mock.device
        device = MockSenderDevice()
        gsm = pygsm.GsmModem(device=device).boot()

        # send an sms, and check that it arrived safely
        gsm.send_sms("1234", "Test Message")
        self.assertEqual(device.sent_messages[0]["recipient"], "1234")
        self.assertEqual(device.sent_messages[0]["text"], "Test Message")


    def testRetryCommands(self):
        """Checks that the GsmModem automatically retries
           commands that fail with a CMS 515 error, and does
           not retry those that fail with other errors."""

        class MockBusyDevice(MockDevice):
            def __init__(self):
                MockDevice.__init__(self)
                self.last_cmd = None
                self.retried = []

            # this command is special (and totally made up)
            # it does not return 515 errors like the others
            def at_test(self, one):
                return True

            def process(self, cmd):

                # if this is the first time we've seen
                # this command, return a BUSY error to
                # (hopefully) prompt a retry
                if self.last_cmd != cmd:
                    self._output("+CMS ERROR: 515")
                    self.last_cmd = cmd
                    return None

                # the second time, note that this command was
                # retried, then fail. kind of anticlimatic
                self.retried.append(cmd)
                return False

        device = MockBusyDevice()
        gsm = pygsm.GsmModem(device=device)
        n = len(device.retried)

        # override the usual retry delay, to run the tests fast
        gsm.retry_delay = 0.01

        # boot the modem, and make sure that
        # some commands were retried (i won't
        # check _exactly_ how many, since we
        # change the boot sequence often)
        gsm.boot()
        self.assert_(len(device.retried) > n)

        # try the special AT+TEST command, which doesn't
        # fail - the number of retries shouldn't change
        n = len(device.retried)
        gsm.command("AT+TEST=1")
        self.assertEqual(len(device.retried), n)


    def testEchoOff(self):
        """Checks that GsmModem disables echo at some point
           during boot, to simplify logging and processing."""

        class MockEchoDevice(MockDevice):
            def process(self, cmd):

                # raise and error for any
                # cmd other than ECHO OFF
                if cmd != "ATE0":
                    return False

                self.echo = False
                return True

        device = MockEchoDevice()
        gsm = pygsm.GsmModem(device=device).boot()
        self.assertEqual(device.echo, False)


    def testUsefulErrors(self):
        """Checks that GsmModem attempts to enable useful errors
           during boot, to make the errors raised useful to humans.
           Many modems don't support this, but it's very useful."""

        class MockUsefulErrorsDevice(MockDevice):
            def __init__(self):
                MockDevice.__init__(self)
                self.useful_errors = False

            def at_cmee(self, error_mode):
                if error_mode == "1":
                    self.useful_errors = True 
                    return True

                elif error_mode == "0":
                    self.useful_errors = False
                    return True

                # invalid mode
                return False

        device = MockUsefulErrorsDevice()
        gsm = pygsm.GsmModem(device=device).boot()
        self.assertEqual(device.useful_errors, True)


if __name__ == "__main__":
    unittest.main()
