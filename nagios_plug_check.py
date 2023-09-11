#!/usr/bin/python3
# Copied and modified from https://github.com/softScheck/tplink-smartplug

import argparse
import json
import logging
import socket
import sys
import time
from datetime import datetime, timedelta
from struct import pack

def encrypt(string):
  key = 171
  result = pack('>I', len(string))
  for i in string:
    a = key ^ ord(i)
    key = a
    result += bytes([a])
  return result


def decrypt(string):
  key = 171
  result = ''
  for i in string:
    a = key ^ i
    key = i
    result += chr(a)
  return result


def query_smartplug(sock):
  sock.send(COMMANDS['sysinfo'])
  str_data = sock.recv(2048)
  decrypted = decrypt(str_data[4:])
  data = json.loads(decrypted)
  relay_state = data['system']['get_sysinfo']['relay_state']
  return relay_state


def setup_socket(ip):
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.settimeout(1)
  sock.connect((ip, SMARTPLUG_PORT))
  return sock


# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMANDS = {
    'sysinfo': encrypt('{"system":{"get_sysinfo":null}}'),
}

SMARTPLUG_PORT = 9999

STATES = ['off', 'on']

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--smartplug', required=True,
                    help='Smartplug hostname or IP address.')
parser.add_argument('--on', action='store_true', default=False,
                    help='Alert if plug is not ON.')
parser.add_argument('--off', action='store_true', default=False,
                    help='Alert if plug is not OFF.')
parser.add_argument('-v', '--verbose', action='store_true', default=False,
                    help='Show debugging output.')
args = parser.parse_args()

loglevel = logging.DEBUG if args.verbose else logging.ERROR
logging.basicConfig(
    format='%(levelname).1s%(asctime)s %(lineno)d]  %(message)s',
    level=loglevel, datefmt='%H:%M:%S')

if not (args.on or args.off):
  parser.error('Specify --on or --off.')

try:
  sock = setup_socket(args.smartplug)
except (ConnectionRefusedError, TimeoutError):
  print(f'UNKNOWN: smartplug {args.smartplug} is UNREACHABLE')
  sys.exit(3)

logging.debug('Connected to smartplug (%s)', args.smartplug)
relay_state = query_smartplug(sock)
relay_state_str = STATES[relay_state].upper()
logging.debug('State is "%s"', relay_state_str)
status_str = f'smartplug {args.smartplug} is {relay_state_str}'

for status in ((args.on, 0), (args.off, 1)):
  if status[0] and relay_state == status[1]:
    print(f'CRITICAL: {status_str}')
    sys.exit(2)
print(f'OK: {status_str}')
sys.exit(0)
