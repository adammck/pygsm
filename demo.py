#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
# see LICENSE file (it's BSD)


import time
from pygsm import GsmModem


class CountLettersApp(object):
    def __init__(self, modem):
        self.modem = modem

    def incoming(self, msg):
        msg.respond("Thanks for those %d characters!" %\
            len(msg.text))

    def serve_forever(self):
        while True:
            print "Checking for message..."
            msg = self.modem.next_message()

            if msg is not None:
                print "Got Message: %r" % (msg)
                self.incoming(msg)

            time.sleep(2)


# all arguments to GsmModem.__init__ are optional, and passed straight
# along to pySerial. for many devices, this will be enough:
gsm = GsmModem(
    port="/dev/ttyUSB0",
    logger=GsmModem.debug_logger).boot()


print "Waiting for network..."
s = gsm.wait_for_network()


# start the demo app
app = CountLettersApp(gsm)
app.serve_forever()
