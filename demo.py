#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from pygsm import GsmModem


class ReverseApp(object):
    def __init__(self, modem):
        modem.receive(self.incoming)
        self.modem = modem

    def incoming(self, caller, datetime, message):
        self.modem.send(caller, "Thanks for that message")


gsm = GsmModem("/dev/ttyUSB0")
gsm.boot()
ReverseApp(gsm)
