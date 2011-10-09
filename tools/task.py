#!/usr/bin/env python2

import sys

def bootUSC():
	from maser_rc import serial_rc
	b = serial_rc()
	while True:
		result = b.Boot_To_USC(1)
		if result:
			print 'USC screen successfully opened'
			break
	sys.exit(1)
	#b.t.close()

def bootDiag():
	try:
		from serial_rc import serial_rc
		b = serial_rc()
		b.reboot()
		device_num = 1
		while True:
			val = b.change_boot_order(device_num)
			device_num += 1
			if val == '1':
				print "Diags successfully run on all Boot Devices"
	except KeyboardInterrupt:
		b.thread.kill()

def BmcSetUp():
	try:
		from serial_rc import serial_rc 
		b = serial_rc()
		b.do_bmc_setup()
	except KeyboardInterrupt:
		b.thread.kill()

def pressEsc():
	import sys
	from serial_rc import serial_rc
	b = serial_rc()
	import pdb
	pdb.set_trace()
	print "executing command....."
	b.update(chr(27))	
	sys.exit(1)
if __name__ == "__main__":
	#bootDiag()
	#BmcSetUp()
	#bootUSC()
	pressEsc()
	
