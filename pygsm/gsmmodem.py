#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


# arch: pacman -S python-pyserial
# debian: apt-get install pyserial
import serial


class GsmModem(object):
    
    # override these after init, and
    # before boot. they're not sanity
    # checked, so go crazy.
    baud             = 9600
    cmd_delay        = 0.1
    device_timeout   = 10
    reset_on_failure = True
    
    
    def __init__(self, port):
        self.port = port
    
    
    def boot(self):
        """Initializes the modem. Must be called after init, but
           before doing anything that expects the modem to be ready."""
        
        # initialize the conection to the modem
        # TODO: if one already exists, close it and kill it   
        self.device = serial.Serial(self.port, self.baud, timeout=self.device_timeout)
        
        # set some sensible defaults, to make
        # the various modems more consistant
        self.command("ATE0")      # echo off
        self.command("AT+CMEE=1") # useful error messages
        self.command("AT+WIND=0") # disable notifications
        self.command("AT+CMGF=1") # switch to TEXT mode
    
    
    def _write(self, str):
        self.device.write(str)
    
    
    def _read(self, terminator=None):
        """Read from the modem (blocking) until _terminator_ is hit,
           (defaults to \n\r, which reads a single "line"), and return."""
        pass
    
    
    def wait(self):
        pass
    
    
    def command(self, cmd, read_term=None, write_term="\r"):
        self._write(cmd + write_term)
        return self._read()
    
    
    def receive(self, callback):
        pass
