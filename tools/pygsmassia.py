#!/usr/bin/env python
#coding=utf-8


from __future__ import print_function
import argparse
import time

from pygsm.gsmmodem import GsmModem


STATUS_MAP = {
    'unread': GsmModem.STATUS_RECEIVED_UNREAD,
    'read': GsmModem.STATUS_RECEIVED_READ,
    'unsent': GsmModem.STATUS_STORED_UNSENT,
    'sent': GsmModem.STATUS_STORED_SENT,
    'all': GsmModem.STATUS_ALL,
}

#args default settings
PORT = '/dev/cu.xrusbmodem14211'
MODE = 'list'
STATUS = 'read'


def cmd():
    parser = argparse.ArgumentParser()
    parser.add_argument('-P', '--port', action='store', default=PORT)
    parser.add_argument('-S', '--status', choices=['unread', 'read', 'unsent', 'sent', 'all'], type=str, default=STATUS, help='sms status, default:%(default)s')
    parser.add_argument('--debug', action='store_true', help="trun on debug mode")

    subparsers = parser.add_subparsers(title='mode', dest='mode', help='sms op mode')

    parser_list = subparsers.add_parser('read', help='read new sms')

    parser_sent = subparsers.add_parser('sent', help='read new sms')
    parser_sent.add_argument('-N', '--number', action='store', type=str, required=True, help="dest phone number")
    parser_sent.add_argument('-T', '--text', action='store', type=str, required=False, help="message text")

    parser_list = subparsers.add_parser('list', help='list sms')

    parser_del = subparsers.add_parser('del', help='delete sms')
    parser_del.add_argument('--all', action='store_true', help="delete all sms message")
    parser_del.add_argument('-I', '--index', action='store', required=False, type=int, help="sms message's index number")

    args = parser.parse_args()
    args.status = STATUS_MAP[args.status]

    return args

#----------------------------------------------------------------------
def print_info(network, hardware):
    """"""
    print('network: %s' % network)
    print('hardware info:')
    for k in hardware:
        print('  %s:\t%s' % (k, hardware[k]))

    return


if __name__ == '__main__':
    args = cmd()

    if args.debug:
        gsm = GsmModem(port=args.port, logger=GsmModem.debug_logger).boot()
    else:
        gsm = GsmModem(port=args.port).boot()

    print_info(gsm.network, gsm.hardware)

    if args.mode == 'read':
        print('reading, please input CTRL+C quit...')
        while True:
            msg = gsm.next_message()
            if msg != None:
                print('received: %s \tsender: %s' % (str(msg.received), msg.sender))
                print(msg.text)

            time.sleep(2)

    elif args.mode == 'sent':
        if args.text == None:
            text = u'测试 - test - %s' % time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            text = args.text

        gsm.send_sms(args.number, text)

    elif args.mode == 'list':
        print('\nlist:')
        msg_amount, message_list = gsm.get_message_list(args.status)
        if msg_amount == None:
            print('no message')
            exit(0)

        for msg in message_list:
            print('index: %d \tstatus: %s' % (msg['index'], msg['status']))
            print(msg['msg_text'])

    elif args.mode == 'del':
        if args.status == GsmModem.STATUS_RECEIVED_UNREAD or args.status == STATUS_ALL:
            print('!error can not delete unread message')
            exit(1)

        if args.all:
            msg_amount, message_list = gsm.get_message_list(args.status)
            for msg in message_list:
                gsm.delete_message(msg['index'])
        else:
            if args.index == None:
                print('!Error miss --index')
                exit(1)

            gsm.delete_message(args.index)



