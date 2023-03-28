'''
Usage
https://pynet.twb-tech.com/blog/netmiko-read-timeout.html
1. Create a new folder and copy cisco-Config-Push.py
into it.

2. Create a file named device-inventory-<site>.
Example
device-inventory-test

Place the information for each switch in the file. Format is
<IP Address>,hp_procurve,<hostname>,<username>,<password>
Example
192.168.10.52,hp_procurve,ANTO-IDF1,mhubbard,7Snb7*BF^8

3. Create a file named AUSD-config-file.txt and place the
configuration commands for the switches in it.

4. Execute
python3 cisco-Config-Push.py -s test


The script will read the device-inventory-<sitename> file and
execute the contents of the <hostname>-config-file.txt for each switch.

For each switch in the inventory file the config commands that were
executed will be saved to 01_<hostname>-config-output.txt.

Use this file as an audit trail for the configuration commands.

The script will also create file with a show running configuration
01_<hostname>-running-config.txt

---Error Handling ---
The connect handler is wrapped in a try/except block.
If a time out occurs when connecting to a switch it is trapped
but the  script halts.
'''

__author__ = "Michael Hubbard"
__author_email__ = "mhubbard@vectorusa.com"
__copyright__ = ""
__license__ = "Unlicense"

from datetime import datetime
from netmiko import ConnectHandler
from netmiko import exceptions
from paramiko.ssh_exception import SSHException
import os
import argparse
import sys
import json
import re
import logging

#  logging.basicConfig(filename="test.txt", level=logging.DEBUG) # It will
#  log all reads and writes on the SSH channel
#  logger = logging.getLogger("netmiko")

def remove_empty_lines(filename):
    if not os.path.isfile(filename):
        print("{} does not exist ".format(filename))
        return
    with open(filename) as filehandle:
        lines = filehandle.readlines()

    with open(filename, 'w') as filehandle:
        lines = filter(lambda x: x.strip(), lines)
        filehandle.writelines(lines)


parser = argparse.ArgumentParser()
parser.add_argument("-s", "--site", help="Site name - ex. MVMS")
args = parser.parse_args()
site = args.site

if site is None:
    print('-s site name is a required argument')
    sys.exit()
else:
    dev_inv_file = 'device-inventory-' + site

# check if site's device inventory file exists
if not os.path.isfile(dev_inv_file):
    print("{} doesn't exist ".format(dev_inv_file))
    sys.exit()

remove_empty_lines(dev_inv_file)

with open(dev_inv_file) as devices_file:
    fabric = devices_file.readlines()

print('-' * (len(dev_inv_file) + 23))
print(f'Reading devices from: {dev_inv_file}')
print('-' * (len(dev_inv_file) + 23))
uptime = []
for line in fabric:
    line = line.strip("\n")
    ipaddr = line.split(",")[0]
    vendor = line.split(",")[1]
    hostname = line.split(",")[2]
    username = line.split(",")[3]
    password = line.split(",")[4]
    if vendor.lower() == "cisco_ios":
        now = datetime.now()
        date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
        print((str(date_time) +
              " Connecting to Switch {}".format(hostname)))
        try:
            net_connect = ConnectHandler(device_type=vendor,
                                         ip=ipaddr,
                                         username=username,
                                         password=password,
                                         )
        except (EOFError, SSHException):
            print(f'Could not connect to {hostname}, remove it'
                  ' from the device inventory file')
            break
        print(f'Configuring {hostname}')
        #  all switches use the same config file
        #  cfg_file = hostname + "-config-file.txt"
        cfg_file = 'AUSD' + "-config-file.txt"
        print()
        print(net_connect.find_prompt())
        # Use textFSM to create a json object with interface stats
        output = net_connect.send_command("show interfaces",
                                          use_textfsm=True)

        # Use textFSM to create a json object with uptime
        output_ver = net_connect.send_command("show version",
                                          use_textfsm=True)
        #  Send commands from cfg_file for human readable output
        output_text = net_connect.send_config_from_file(cfg_file,
                                                        read_timeout=200)
        #  print(output_text)  # print the output as plain text on screen

        #  Write the plain text output to disk
        int_report = "01_" + hostname + "-config-output.txt"
        with open(int_report, 'w') as file:
            file.write(output_text)
        print()

        output_text = net_connect.send_command("show running",
                                               read_timeout=50)
        #  Write the running config to disk
        int_report = "01_" + hostname + "-running-config.txt"
        with open(int_report, 'w') as file:
            file.write(output_text)
        print()

        #  Write the JSON interface data to a file
        int_report = "01_" + hostname + "-config-json.txt"
        with open(int_report, 'w') as file:
            output = json.dumps(output, indent=2)
            file.write(output)

        #  Write the JSON uptime data to a file
        int_report = "01_" + hostname + "-uptime-json.txt"
        with open(int_report, 'w') as file:
            output_ver = json.dumps(output_ver, indent=2)
            file.write(output_ver)

        ports = []
        count = 0
        #  Create a regex to match any port with [0-8]/0/[0-9]{1,2}
        #  This will match all ports with a 0 as the module number

        regexpattern = re.compile(r'G*[0-8]/0/[0-9]{1,2}')

        # count number of interfaces
        interfaces = json.loads(output)
        for interface in interfaces:
            a = re.findall(regexpattern, interface['interface'])
            if len(a):
                count += 1
        print(f'Number of interfaces, {count}')
        net_connect.disconnect()
        print('-' * (len(hostname) + 39))
        print(f'Successfully created config files for {hostname}')
        print('-' * (len(hostname) + 39))
    uptime = uptime + json.loads(output_ver)
    #  Write the JSON uptime data to a file
    int_report = site + "-uptime-json.txt"
    with open(int_report, 'w') as file:
        output_ver = json.dumps(uptime, indent=2)
        file.write(output_ver)
    #  print(f'Uptime: {uptime}')
