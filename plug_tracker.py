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

sys.path.append('/opt/repos/mypylib')
from mypylib import setup_logging


def is_between(start_time, end_time, current_time):
  if start_time <= end_time:
    return start_time <= current_time <= end_time
  return current_time >= start_time or current_time <= end_time


def seconds_until_next(end_time, current_time):
  current_datetime = datetime.combine(datetime.today(), current_time)
  if current_time <= end_time:
    next_timestamp = datetime.combine(current_datetime.date(), end_time)
  else:
    next_timestamp = datetime.combine(
        current_datetime.date() + timedelta(days=1), end_time)
  return int((next_timestamp - current_datetime).total_seconds()) + 60


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


def setup_socket(ip):
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.settimeout(1)
  sock.connect((ip, SMARTPLUG_PORT))
  return sock


def query_smartplug(sock):
  sock.send(COMMANDS['sysinfo'])
  str_data = sock.recv(2048)
  decrypted = decrypt(str_data[4:])
  data = json.loads(decrypted)
  relay_state = data['system']['get_sysinfo']['relay_state']
  return relay_state


def set_state(ip, desired_state):
  logging.info('Connecting to follower smartplug (%s).', ip)
  sock = setup_socket(ip)
  logging.info('Setting follower smartplug (%s) state to %d.', ip, desired_state)
  sock.send(COMMANDS['state'][desired_state])
  sock.close()
  logging.info('Done.')


setup_logging('/var/log/cron/plug_tracker.log')
# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMANDS = {
    'state': {
      0: encrypt('{"system":{"set_relay_state":{"state":0}}}'),
      1: encrypt('{"system":{"set_relay_state":{"state":1}}}'),
    },
    'sysinfo': encrypt('{"system":{"get_sysinfo":null}}'),
}

SMARTPLUG_PORT = 9999

parser = argparse.ArgumentParser()
parser.add_argument('-b', '--ignore_start', required=False, default='',
                    help='Ignore leader changes starting at this HH:MM.')
parser.add_argument('-e', '--ignore_stop', required=False, default='',
                    help='Ignore leader changes ending at this HH:MM.')
parser.add_argument('-f', '--follower', required=True,
                    help='Smartplug hostname or IP address acting as follower.')
parser.add_argument('-l', '--leader', required=True,
                    help='Smartplug hostname or IP address acting as leader.')
args = parser.parse_args()

if not (args.ignore_start and args.ignore_stop):
  parser.error('If specifying an ignore start or stop, both must be provided.')

parse_time = lambda time_str: datetime.strptime(time_str, '%H:%M').time()
ignore_start = parse_time(args.ignore_start)
ignore_stop = parse_time(args.ignore_stop)

while True:
  try:
    sock = setup_socket(args.leader)
  except:
    logging.error('Could not connect to leader smartplug (%s)', args.leader)
    time.sleep(1)
    continue
  logging.info('Connected to leader smartplug (%s)', args.leader)
  break

prev_state = -1
while True:
  current_time = datetime.now().time()
  if is_between(ignore_start, ignore_stop, current_time):
    seconds_until_ignore_end = seconds_until_next(ignore_stop, current_time)
    logging.info('Current time is between %s and %s. Entering ignore mode.',
                 args.ignore_start, args.ignore_stop)
    logging.info('Closing leader smartplug (%s) socket.', args.leader)
    try:
      sock.close()
    except:
      logging.error('Error closing socket.')
    logging.info('Sleeping %d seconds until ignore period is over.',
                 seconds_until_ignore_end)
    time.sleep(seconds_until_ignore_end)
    logging.info('Ignore period is over, resuming operations.')

  try:
    relay_state = query_smartplug(sock)
  except:
    sock = setup_socket(args.leader)
    logging.info('Reconnected to leader smartplug (%s)', args.leader)
    continue
  if relay_state != prev_state and prev_state != -1:
    logging.info('Leader smartplug (%s) state changed to %d', args.leader,
                 relay_state)
    set_state(args.follower, relay_state)
  prev_state = relay_state
  time.sleep(1)

sys.exit()
