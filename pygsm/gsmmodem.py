#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


import re, time
import errors, message

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
        
        # to cache parts of multi-part messages
        # until the last part is delivered
        self.multipart = {}

        # to store unhandled incoming messages
        self.incoming_queue = []
    
    
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
        
        # enable new message notification
        self.command("AT+CNMI=2,2,0,0,0")
    
    
    def _write(self, str):
        """Write a string to the modem."""
        try:
            print "WRITE: %r" % str
            self.device.write(str)
        
        # if the device couldn't be written to,
        # wrap the error in something that can
        # sensibly be caught at a higher level
        except OSError, err:
            raise(errors.GsmWriteError)
    
    
    def _read(self, read_term=None, read_timeout=None):
        """Read from the modem (blocking) until _terminator_ is hit,
           (defaults to \r\n, which reads a single "line"), and return."""
        buffer = []
        
        # if a different timeout was requested just
        # for _this_ read, store and override the
        # current device setting (not thread safe!)
        if read_timeout is not None:
            old_timeout = self.device.timeout
            self.device.timeout = read_timeout
        
        def __reset_timeout():
            """restore the device's previous timeout
               setting, if we overrode it earlier."""
            if read_timeout is not None:
                self.device.timeout =\
                    old_timeout
        
        # the default terminator reads
        # until a newline is hit
        if not read_term:
            read_term = "\r\n"
        
        while(True):
            buf = self.device.read()
            print "READ: %r" % buf
            buffer.append(buf)
            
            # if a timeout was hit, raise an exception including the raw data that
            # we've already read (in case the calling func was _expecting_ a timeout
            # (wouldn't it be nice if serial.Serial.read returned None for this?)
            if buf == "":
                __reset_timeout()
                print "_Read Timeout: %r" % (buffer)
                raise(errors.GsmReadTimeoutError(buffer))
            
            # if last n characters of the buffer match the read
            # terminator, return what we've received so far
            if buffer[-len(read_term)::] == list(read_term):
                buf_str = "".join(buffer).strip()
                print "_Read: %r" % buf_str
                
                __reset_timeout()
                return buf_str
    
    
    def _wait(self, read_term=None, read_timeout=None):
        """Read from the modem (blocking) one line at a time until a response
           terminator ("OK", "ERROR", or "CMx ERROR...") is hit, then return
           a list containing the lines."""
        print "Waiting for response"
        buffer = []
        
        # keep on looping until a command terminator
        # is encountered. these are NOT the same as the
        # "read_term" argument - only OK or ERROR is valid
        while(True):
            buf = self._read(
                read_term=read_term,
                read_timeout=read_timeout)
            
            buffer.append(buf)
            
            # most commands return OK for success, but there
            # are some exceptions. we're not checking those
            # here (unlike RubyGSM), because they should be
            # handled when they're _expected_
            if buf == "OK":
                return buffer
            
            # some errors contain useful error codes, so raise a
            # proper error with a description from pygsm/errors.py
            m = re.match(r"^\+(CM[ES]) ERROR: (\d+)$", buf)
            if m is not None:
                type, code = m.groups()
                raise(errors.GsmModemError(type, int(code)))
            
            # ...some errors are not so useful
            # (at+cmee=1 should enable error codes)
            if buf == "ERROR":
                raise(errors.GsmModemError)
    
    
    INCOMING_FMT = "%y/%m/%d,%H:%M:%S%Z"
    
    def _parse_incoming_timestamp(self, timestamp):
        pattern = r"\-(\d+)$"
        m = re.match(pattern, timestamp)
        if m is not None:
            try:
                timestamp = re.sub(pattern, "", timestamp)
                t = time.strptime(timestamp, self.INCOMING_FMT)
                t.timezone = int(m.groups(0)) * 900
                print "Parsed timestamp %r into %r" % (timestamp, t)
                return t
            
            # it's no big deal if the timestamp
            # couldn't be parsed, so ignore it
            except ValueError:
                print "Couldn't parse timestamp: %r" % timestamp
                pass
        
        # fall back to None
        return None
	
	
    def _parse_incoming_sms(self, lines):
        print "_parse: %r" % (lines)
        output_lines = []
        n = 0
        
        # iterate the lines like it's 1984
        # (because we're patching the array,
        # which is hard work for iterators)
        while n < len(lines):
            
            # not a CMT string? add it back into the
            # output (since we're not interested in it)
            # and move on to the next
            if lines[n][0:5] != "+CMT:":
                output_lines.append(lines[n])
                n += 1
                continue
            
            # since this line IS a CMT string (an incoming
            # SMS), parse it and store it to deal with later
            m = re.match(r'^\+CMT: "(.+?)",.*?,"(.+?)".*?$', lines[n])
            if m is None:
                
                # couldn't parse the string, so just move
                # on to the next line. TODO: log this error
                n += 1
                next
            
            # extract the meta-info from the CMT line,
            # and the message from the FOLLOWING line
            sender, timestamp = m.groups()
            text = lines[n+1].strip()

            # notify the network that we accepted
            # the incoming message (for read receipt)
            # BEFORE pushing it to the incoming queue
            # (to avoid really ugly race condition if
            # the message is grabbed from the queue
            # and responded to quickly, before we get
            # a chance to issue at+cnma)
            try:
                self.command("AT+CNMA")

            # not terribly important if it
            # fails, even though it shouldn't
            except errors.GsmError:
                
                #self.log("Receipt acknowledgement (CNMA) was rejected")
                # TODO: also log this!
                pass
            
            # (i'm using while/break as an alternative to catch/throw
            # here, since python doesn't have one. we might abort early
            # if this is part of a multi-part message, but not the last
            while True:
                
                # multi-part messages begin with ASCII 130 followed
                # by "@" (ASCII 64). TODO: more docs on this, i wrote
                # this via reverse engineering and lost my notes
                if (ord(text[0]) == 130) and (text[1] == "@"):
                    part_text = text[7:]

                    # ensure we have a place for the incoming
                    # message part to live as they are delivered
                    if sender not in self.multipart:
                        self.multipart[sender] = []

                    # append THIS PART
                    self.multipart[sender].append(part_text)

                    # abort if this is not the last part
                    if ord(text[5]) != 173:
                        break

                    # last part, so switch out the received
                    # part with the whole message, to be processed
                    # below (the sender and timestamp are the same
                    # for all parts, so no change needed there)
                    text = "".join(self.multipart[sender])
                    del self.multipart[sender]

                # store the incoming data to be picked up
                # from the attr_accessor as a tuple (this
                # is kind of ghetto, and WILL change later)
                sent = self._parse_incoming_timestamp(timestamp)
                msg = message.IncomingMessage(self, sender, sent, text)
                self.incoming_queue.append(msg)
                
                # don't loop! the only reason that this
                # "while" exists is to jump out early
                break
            
            # jump over the CMT line, and the
            # text line, and continue iterating
            n += 2
        
        # return the lines that we weren't
        # interested in (almost all of them!)
        print "_parsed: %r" % (output_lines)
        return output_lines


    def command(self, cmd, read_term=None, read_timeout=None, write_term="\r"):
        """Issue a single AT command to the modem, and return the sanitized
           response. Sanitization removes status notifications, command echo,
           and incoming messages, (hopefully) leaving only the actual response
           from the command."""
        print "Command: %r" % cmd
        
        # TODO: lock the modem
        self._write(cmd + write_term)
        lines = self._wait(
            read_term=read_term,
            read_timeout=read_timeout)
        
        # if the first line of the response echoes the cmd
        # (it shouldn't, if ATE0 worked), silently drop it
        if lines[0] == cmd:
            lines.pop(0)
        
        # remove all blank lines and unsolicited
        # status messages. i can't seem to figure
        # out how to reliably disable them, and
        # AT+WIND=0 doesn't work on this modem
        lines = [
            line
            for line in lines
            if line      != "" or\
               line[0:6] == "+WIND:" or\
               line[0:6] == "+CREG:" or\
               line[0:7] == "+CGRED:"]
        
        # parse out any incoming sms that were bundled
        # with this data (to be fetched later by an app)
        lines = self._parse_incoming_sms(lines)
        
        # rest up for a bit (modems are
        # slow, and get confused easily)
        time.sleep(self.cmd_delay)
        
        print "Output: %s" % lines
        return lines
    
    
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
    
    
    def send_sms(self, recipient, text):
        print "MSG to %r: %r" % (recipient, text)
        
        # TODO: lock the modem
        
        try:
            try:
            
                # initiate the sms, and give the device a second
                # to raise an error. unfortunately, we can't just
                # wait for the "> " prompt, because some modems
                # will echo it FOLLOWED BY a CMS error
                self.command(
                    "AT+CMGS=\"%s\"\r" % (recipient),
                    read_timeout=1)
            
            # if no error is raised within the timeout period,
            # and the text-mode prompt WAS received, send the
            # sms text, wait until it is accepted or rejected
            # (text-mode messages are terminated with ascii char 26
            # "SUBSTITUTE" (ctrl+z)), and return True (message sent)
            except errors.GsmReadTimeoutError, err:
                if err.pending_data[0] == ">":
                    self.command(text, write_term=chr(26))
                    return True
                
                # a timeout was raised, but no prompt nor
                # error was received. i have no idea what
                # is going on, so allow the error to propagate
                else: raise
        
        # for all other errors...
        # (likely CMS or CME from device)
        except:
            
            # whatever went wrong, break out of the
            # message prompt. if this is missed, all
            # subsequent writes will go into the message!
            self._write(chr(27))
            
            # rule of thumb: pygsm is meant to be embedded,
            # so DO NOT EVER allow exceptions to propagate
            # (obviously, this sucks. there should be an
            # option, at least, but i'm being cautious)
            return None
    
    
    def receive(self, callback):
        pass
    
    
    def hardware(self):
        """Returns a dict of containing information about the physical
           modem. The contents of each value are entirely manufacturer
           dependant, and vary wildly between devices."""
        
        return {
            "manufacturer": self.query("AT+CGMI"),
            "model":        self.query("AT+CGMM"),
            "revision":     self.query("AT+CGMR"),
            "serial":       self.query("AT+CGSN") }


    def signal_strength(self):
        """Returns an integer between 1 and 99, representing the current
           signal strength of the GSM network, False if we don't know, or
           None if the modem can't report it."""
        
        data = self.query("AT+CSQ")
        md = re.match(r"^\+CSQ: (\d+),", data)
        
        # 99 represents "not known or not detectable". we'll
        # return False for that (so we can test it for boolean
        # equality), or an integer of the signal strength.
        if md is not None:
            csq = int(md.group(1))
            return csq if csq < 99 else False
        
        # the response from AT+CSQ couldn't be parsed. return
        # None, so we can test it in the same way as False, but
        # check the type without raising an exception
        return None
    
    
    def wait_for_network(self):
        """Blocks until the signal strength indicates that the
           device is active on the GSM network. It's a good idea
           to call this before trying to send or receive anything."""
        
        while True:
            csq = self.signal_strength()
            if csq: return csq
            time.sleep(1)
    
    
    def ping(self):
        """Sends the "AT" command to the device, and returns true
           if it is acknowledged. Since incoming notifications and
           messages are intercepted automatically, this is a good
           way to poll for new messages without using a worker
           thread like RubyGSM."""
        try:
            self.query("AT")
            return True
            
        except errors.GsmError:
            return None
