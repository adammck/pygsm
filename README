class GsmModem(__builtin__.object)
 |  pyGSM is a Python module which uses pySerial to provide a nifty
 |  interface to send and receive SMS via a GSM Modem. It was ported
 |  from RubyGSM, and provides (almost) all of the same features. It's
 |  easy to get started:
 |
 |    # create a GsmModem object:
 |    >>> modem = pygsm.GsmModem(port="/dev/ttyUSB0")
 |
 |    # harass Evan over SMS:
 |    # (try to do this before 11AM)
 |    >>> modem.send_sms(*REDACTED*, "Hey, wake up!")
 |
 |    # check for incoming SMS:
 |    >>> print modem.next_message()
 |    <pygsm.IncomingMessage from *REDACTED*: "Leave me alone!">
 |
 |  pyGSM is distributed via GitHub:
 |  http://github.com/adammck/pygsm
 |
 |  Bug reports (especially for
 |  unsupported devices) are welcome:
 |  http://github.com/adammck/pygsm/issues
 |
 |
 |
 |
 |  Methods defined here:
 |
 |
 |  __init__(self, *args, **kwargs)
 |      Create a GsmModem object. All of the arguments are passed along
 |      to serial.Serial.__init__ when GsmModem.connect is called. For
 |      all of the possible configration options, see:
 |
 |      http://pyserial.wiki.sourceforge.net/pySerial#tocpySerial10
 |
 |      Alternatively, a single 'device' kwarg can be passed, which
 |      overrides the default proxy-args-to-pySerial behavior. This is
 |      useful when testing, or wrapping the serial connection with some
 |      custom logic.
 |
 |      NOTE: The serial connection isn't created until GsmModem.connect
 |      is called. It might still fail (but should raise GsmConnectError
 |      when it does so.)
 |
 |
 |  boot(self, reboot=False)
 |      (Re-)Connect to the modem and configure it in an (often vain)
 |      attempt to standardize the behavior of the many vendors and
 |      models. Should be called before reading or writing.
 |
 |      This method isn't called during __init__ (since 5f41ba6d), since
 |      it's often useful to create GsmModem objects without writing to
 |      the modem. To compensate, this method returns 'self', so it can
 |      be easily chained onto the constructor, like so:
 |
 |        >>> gsm = GsmModem(port="whatever").boot()
 |
 |      This is exactly the same as:
 |
 |        >>> gsm = GsmModem(port="whatever")
 |        >>> gsm.boot()
 |
 |
 |  command(self, cmd, read_term=None, read_timeout=None, write_term='\r', raise_errors=True)
 |      Issue an AT command to the modem, and return the sanitized
 |      response. Sanitization removes status notifications, command
 |      echo, and incoming messages, (hopefully) leaving only the actual
 |      response to the command.
 |
 |      If Error 515 (init or command in progress) is returned, the
 |      command is automatically retried up to 'GsmModem.max_retries'
 |      times.
 |
 |
 |  connect(self, reconnect=False)
 |      Connect to the modem via pySerial, using the args and kwargs
 |      provided to the constructor. If 'reconnect' is True, and the
 |      modem is already connected, the entire serial.Serial object is
 |      destroyed and re-established.
 |
 |      Returns self.device, or raises GsmConnectError
 |
 |
 |  disconnect(self)
 |      Disconnect from the modem.
 |
 |
 |  hardware(self)
 |      Return a dict of containing information about the modem. The
 |      contents of each value are entirely manufacturer-dependant, and
 |      can vary wildly between devices.
 |
 |
 |  next_message(self, ping=True, fetch=True)
 |      Returns the next waiting IncomingMessage object, or None if the
 |      queue is empty. The optional 'ping' and 'fetch' args control
 |      whether the modem is pinged (to allow new messages to be
 |      delivered instantly, on those modems which support it) and
 |      queried for unread messages in storage, which can both be
 |      disabled in case you're already polling in a separate thread.
 |
 |
 |  ping(self)
 |      Send the "AT" command to the device, and return true if it is
 |      acknowledged. Since incoming notifications and messages are
 |      intercepted automatically, this is a good way to poll for new
 |      messages without using a worker thread like RubyGSM.
 |
 |
 |  query(self, cmd, prefix=None)
 |      Issue an AT command to the modem, and returns the relevant part
 |      of the response. This only works for commands that return a
 |      single line followed by "OK", but conveniently, this covers
 |      almost all AT commands that I've ever needed to use. Example:
 |
 |        >>> modem.query("AT+CSQ")
 |        "+CSQ: 20,99"
 |
 |      Optionally, the 'prefix' argument can specify a string to check
 |      for at the beginning of the output, and strip it from the return
 |      value. This is useful when you want to both verify that the
 |      output was as expected, but ignore the prefix. For example:
 |
 |        >>> modem.query("AT+CSQ", prefix="+CSQ:")
 |        "20,99"
 |
 |      For all unexpected responses (errors, no output, or too much
 |      output), returns None.
 |
 |
 |  query_list(self, cmd, prefix=None)
 |      Issue a single AT command to the modem, checks that the last
 |      line of the response is "OK", and returns a list containing the
 |      other lines. An empty list is returned if a command fails, so
 |      the output of this method can always be assumed to be iterable.
 |
 |      The 'prefix' argument can optionally specify a string to filter
 |      the output lines by. Matching lines are returned (sans prefix),
 |      and the rest are dropped.
 |
 |      Most AT commands return a single line, which is better handled
 |      by GsmModem.query, which returns a single value.
 |
 |
 |  reboot(self)
 |      Disconnect from the modem, reconnect, and reboot it (AT+CFUN=1,
 |      which clears all volatile state). This drops the connection to
 |      the network, so it's wise to call _GsmModem.wait_for_network_
 |      after rebooting.
 |
 |
 |  send_sms(self, recipient, text)
 |      Send an SMS to 'recipient' containing 'text'. Some networks will
 |      automatically split long messages into multiple parts, and join
 |      them upon delivery -- but some will silently drop them. pyGSM
 |      does nothing to avoid this (for now), so try to keep 'text'
 |      under 160 characters.
 |
 |
 |  signal_strength(self)
 |      Return an integer between 1 and 99, representing the current
 |      signal strength of the GSM network, False if we don't know, or
 |      None if the modem can't report it.
 |
 |
 |  wait_for_network(self)
 |      Block until the signal strength indicates that the device is
 |      active on the GSM network. It's a good idea to call this before
 |      trying to send or receive anything.
 |
 |
 |
 |
 |  Data descriptors defined here:
 |
 |
 |  network
 |      Return the name of the currently selected GSM network.
 |
 |
 |  service_center
 |      Get or set the service center address currently in use by the
 |      modem. Returns None if the modem does not support the AT+CSCA
 |      command.
