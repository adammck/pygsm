#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from pygsm import GsmModem
import serial, time


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
            msg = self.modem.next_message()
            if msg is not None:
                self.incoming(msg)
            
            # no messages? wait a couple of seconds
            # (let's not blow up the modem), and retry
            time.sleep(2)
            

gsm = GsmModem(port="/dev/ttyUSB0", baudrate=115200, xonxoff=1, rtscts=1)
gsm.boot()


print "Modem Hardware: %r" % (gsm.hardware())
print "Signal Strength: %r" % (gsm.wait_for_network())

app = CountLettersApp(gsm)
app.serve_forever()
