#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
# see LICENSE file (it's BSD)


import unittest
import pygsm


class TestIncomingMessage(unittest.TestCase):
    def testRespond(self):
        """
        Check that the IncomingMessage calls send_sms (with the correct
        arguments) when .respond is called.
        """

        caller   = "123"
        in_text  = "alpha"
        out_text = "beta"

        # this mock pygsm.gsmmodem does nothing, except note
        # down the parameters which .send_sms is called with
        class MockGsmModem(object):
            def __init__(self):
                self.sent_sms = []

            def send_sms(self, recipient, text):
                self.sent_sms.append({
                    "recipient": recipient,
                    "text": text
                })

        mock_gsm = MockGsmModem()

        # simulate an incoming message, and a respond to it
        msg = pygsm.message.IncomingMessage(mock_gsm, caller, None, in_text)
        msg.respond(out_text)

        # check that MockDevice.send_sms was called with
        # the correct args by IncomingMessage.respond
        self.assertEqual(mock_gsm.sent_sms[0]["recipient"], caller)
        self.assertEqual(mock_gsm.sent_sms[0]["text"], out_text)


if __name__ == "__main__":
    unittest.main()
