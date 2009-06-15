#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


import unittest
import pygsm

from mock.device import MockDevice


class TestIncomingMessage(unittest.TestCase):
    def testEchoOff(self):
        """Checks that GsmModem disables echo at some point
           during boot, to simplify logging and processing."""

        class MockEchoDevice(MockDevice):
            def process(self, cmd):
                if cmd == "ATE0":
                    self.echo = False
                    return True

        device = MockEchoDevice()
        gsm = pygsm.GsmModem(device=device)
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
        gsm = pygsm.GsmModem(device=device)
        self.assertEqual(device.useful_errors, True)


if __name__ == "__main__":
    unittest.main()
