#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from pygsm import GsmModem
import serial


class ReverseApp(object):
    def __init__(self, modem):
        modem.receive(self.incoming)
        self.modem = modem

    def incoming(self, caller, datetime, message):
        self.modem.send(caller, "Thanks for that message")


serial = serial.Serial(port="/dev/ttyUSB0", baudrate=115200, xonxoff=1, rtscts=1)
gsm = GsmModem(serial)
gsm.boot()

print "Modem Hardware: %r" % (gsm.hardware())
print "Signal Strength: %r" % (gsm.signal_strength())
