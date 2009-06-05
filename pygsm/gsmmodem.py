#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


import re, time

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
    
    
    def __init__(self, port_or_device):
        
        # accept an existing serial port object,
        # for modems which require non-default
        # parameters or init strings (rather than
        # wrapping all those calls opaquely here)
        if isinstance(port_or_device, serial.Serial):
            self.device = port_or_device
        
        # otherwise, assume that the single argument
        # is a string containing the serial port that
        # we should connect to
        else:
            self.port = port
    
    
    def boot(self):
        """Initializes the modem. Must be called after init, but
           before doing anything that expects the modem to be ready."""
        
        # create the conection to the modem,
        # if it hasn't already been done
        if not self.device:
            self.device = serial.Serial(self.port)
        
        # set some sensible defaults, to make
        # the various modems more consistant
        self.command("AT+CFUN=1") # reset the modem
        self.command("ATE0")      # echo off
        self.command("AT+CMEE=1") # useful error messages
        self.command("AT+WIND=0") # disable notifications
        self.command("AT+CMGF=1") # switch to TEXT mode
    
    
    def _write(self, str):
        """Write a string to the modem."""
        print "WRITE: %r" % str
        self.device.write(str)
    
    
    def _read(self, read_term=None):
        """Read from the modem (blocking) until _terminator_ is hit,
           (defaults to \r\n, which reads a single "line"), and return."""
        buffer = []
        
        if not read_term:
            read_term = "\r\n"
        
        while(True):
            buf = self.device.read()
            print "READ: %r" % buf
            buffer.append(buf)
            
            if(buffer[-len(read_term)::]==list(read_term)):
                buf_str = "".join(buffer).strip()
                print "_Read: %r" % buf_str
                return buf_str
    
    
    def wait(self, read_term=None):
        print "Waiting for response"
        buffer = []
        
        while(True):
            buf = self._read(read_term)
            buffer.append(buf)
            
            if(buf=="OK"):
                return buffer
    
    
    def command(self, cmd, read_term=None, write_term="\r"):
        print "Command: %r" % cmd
        
        # TODO: lock the modem
        self._write(cmd + write_term)
        out = self.wait()

        # rest up for a bit (modems are
        # slow, and get confused easily)
        time.sleep(self.cmd_delay)
        
        print "Output: %s" % out
        return out
    
    
    def query(self, cmd):
	    print "Query: %r" % cmd
	    out = self.command(cmd)
	    
	    # the only valid response to a "query" is a
	    # single line followed by "OK". if all looks
	    # well, return just the single line
	    if(len(out) == 2) and (out[-1] == "OK"):
	        return out[0]
	    
	    # something went wrong, so return the very
	    # ambiguous None. it's better than blowing up
	    return None
    
    
    def receive(self, callback):
        pass
