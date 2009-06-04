#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from pygsm import GsmModem


class ReverseApp:
    def __init__(modem):
        modem.receive(self.incoming)
        self.modem = modem

    def incoming(caller, datetime, message):
        self.modem.send(caller, "Thanks for that message")


gsm = GsmModem("/dev/ttyUSB0")
ReverseApp(gsm)
