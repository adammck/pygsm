#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from pygsm import GsmModem
import time


class CountLettersApp(object):
    def __init__(self, modem):
        self.modem = modem

    def incoming(self, msg):
        msg.respond("Thanks for those %d characters!" %\
            len(msg.text))

    def serve_forever(self):
        """Block forever, polling the modem for new messages every
           two seconds. When a message is received, pass it on to
           the _incoming_ message for handling."""

        while True:

            # poll the modem
            print "Checking for message..."
            msg = self.modem.next_message()
            if msg is not None:
                print "Got Message: %r" % (msg)
                self.incoming(msg)

            # no messages? wait a couple of seconds
            # (let's not blow up the modem), and retry
            time.sleep(2)


# connect to my multitech MTCBA-G-U-F4 modem,
# which requires more configuration than most
gsm = GsmModem(
    port="/dev/ttyUSB0",
    baudrate=115200,
    xonxoff=0,
    rtscts=1)

# all arguments to GsmModem.__init__ are optional,
# and passed straight on to pySerial. for many
# devices, this will be enough:
#gsm = GsmModem(port="/dev/ttyUSB0")

# start the demo app
app = CountLettersApp(gsm)
app.serve_forever()
