import socket 
import sys
import time
import re
import logging, string
from threading import Thread

logging.basicConfig(level=logging.INFO)

import ANSI

ESC = chr(27)
ENTER = chr(13)
F1 = ESC + '1'
F2 = ESC + '2'
F10 = ESC + '0'
DOWN = ESC + '[B'
UP = ESC + '[A'

#buffer class
class StringBuffer:
	strBuff = ''
	def write(self,input):
		self.strBuff += input

	def __str__(self):
		temp = self.strBuff
		self.strBuff = ""
		return temp

	def __repr__(self):
		temp = self.strBuff
		self.strBuff = ""
		return temp

def read_args(term,buff):
	while True:
		data = term.recv(1024)
		buff.write(data)


class serial_rc(object):
	Rows = 26
	Cols = 80
	def get_bios_version(self):
		self.update()
		pattern = re.compile('BIOS Version(:?)+\s?((?:\w*\S?)+)')
		results = re.search(pattern, self.buffer.dump())
		if results:
			return results.groups()[1]    
	def __init__(self,port=0):
		self.buffer = ANSI.ANSI(self.Rows, self.Cols)
		self.record = file('record.txt', 'wb')

		self.conn = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		self.conn.connect(('10.94.32.118',623))

		self.buff = StringBuffer() 
		self.t = Thread(target=read_args,args=(self.conn,self.buff)) 
		self.t.start()

		#output = self.conn.recv(1024)
		self.conn.send("3\r\n")
		time.sleep(1)
		self.conn.send("10.94.132.104\r\n")
		time.sleep(1)
		self.conn.send("root\r\n")
		time.sleep(1)
		self.conn.send("calvin\r\n")
		time.sleep(1)
		self.conn.send("\r\n")
		time.sleep(1)

		logging.debug('Connected to serial port 0')

	def _write(self, input):
		if input[0] == chr(27):
			logging.debug('Sending data <ESC>%s' % input[1:])
		else:
			logging.debug('Sending data %s' % input)
		self.conn.send(input+ '\r\n')

	def _read(self):
		#if len(output) > 0:
		#    logging.debug('Recieved %i bytes' % len(output))
		return str(self.buff)

	def update(self, input=None, reads=2):
		if input:
			self._write(input)
		while reads > 0:
			reads = reads - 1
			output = self._read()
			self.record.write(output)
			self.record.flush()
			self.buffer.write(output)
			time.sleep(0.1)

	def process_help(self, diffedScreen):
		#UGH...removes the box and blank lines
		lines = diffedScreen.split('\n')
		lines = [l[1:-1] for l in lines]
		lines = [l.strip() for l in lines]
		lines = [l for l in lines if l != '']
		lines = lines[1:-1]
		return " ".join(lines)

	def do_setup(self):
		logging.info('Looking for BIOS Setup prompt...')
		while True:
			self.update()
			area = "\n".join(self.buffer.get_region(2, 60, 2, 80))
			if re.search('F2.*=.*Setup', area):
				logging.info('Found prompt, sending F2')
				self.update(F2)
			elif re.search('Entering System Setup', area):
				logging.info('Entering System Setup')
				while True:
					self.update()
					area = "\n".join(self.buffer.get_region(23, 60, self.Cols, 77))
					if re.search('F1.{0,4}Help', area):
						logging.info('Setup screen is fully drawn')
						return 0

	def do_bmc_setup(self):
		logging.info('Looking for BMC Setup prompt...')
		key_sent = False
		pattern = re.compile('Press <Ctrl-E> for Remote Access Setup')
		while True:
			self.update()
			area = self.buffer.dump()
			if pattern.search(area):
				logging.info('Found prompt, sending Ctrl+E')
				self.update(chr(5))
				key_sent = True
			elif key_sent and re.search('F1=Help', area):
				logging.info('Setup screen is fully drawn')
				return 0

	def get_screenshot(self):
		return self.buffer.pretty()

	def reboot(self):
		logging.info('Sending Ctrl+Alt+Del')
		rebootCmd = ESC + 'R'+ ESC + 'r' + ESC + 'R'
		self._write(rebootCmd)
		#time.sleep(2)
		#self._write(rebootCmd)

	def get_asset_tag(self):
		self.update()
		pattern = re.compile('Asset Tag: (\w*)')
		results = re.search(pattern, self.buffer.dump())
		if results:
			return results.groups()[0]

	def get_service_tag(self):
		self.update()
		pattern = re.compile('Service Tag: (\w*)')
		results = re.search(pattern, self.buffer.dump())
		if results:
			return results.groups()[0]
		
	def get_system_id(self):
		self.update()
		pattern = re.compile('PowerEdge (\w*)')
		results = re.search(pattern, self.buffer.dump())
		if results:
			return ('PowerEdge %s' %results.groups()[0])

	def get_help_text(self):
		before = self.buffer.pretty()
		b.update(F1, 5)
		after = self.buffer.pretty()
		b.update(F1, 5)

		diffedScreen = self.diff_screens(before, after)
		help = self.process_help(diffedScreen)
		return help

	def get_popup_menu(self):
		before = self.buffer.pretty()
		b.update(' ', 5)
		after = self.buffer.pretty()
		self.update(ESC, 5)
		diff = self.diff_screens(before, after)
		pattern = re.compile('((?:[A-Z]\w*\s?)+)\.+\s?((?:\S+\s?)+)')
		results = pattern.findall(diff)

		return results

	def find_box(self, screen0, screen1):
		rows0 = [row for row in screen0.split('\n') if row != '']
		rows1 = [row for row in screen1.split('\n') if row != '']
		
		# Grab the columns
		cols0 = ["".join(column) for column in map(None, *rows0)]
		cols1 = ["".join(column) for column in map(None, *rows1)]
		
		# Isolate the row numbers that changed
		diff_rows = [row[0] for row in enumerate(zip(rows0, rows1)) if row[1][0] != row[1][1]]

		# Isolate the columns that changed
		diff_cols = [col[0] for col in enumerate(zip(cols0, cols1)) if col[1][0] != col[1][1]]

		import pdb
		pdb.set_trace()
		return (diff_cols[0], diff_rows[0], diff_cols[-1], diff_rows[-1])


	def diff_screens(self, screen0, screen1):
		"""
		Take two screens and isolate the areas that changed
		"""
		# Split the rows into lists for processing
		rows0 = [row for row in screen0.split('\n') if row != '']
		rows1 = [row for row in screen1.split('\n') if row != '']
		
		# Grab the columns
		cols0 = ["".join(column) for column in map(None, *rows0)]
		cols1 = ["".join(column) for column in map(None, *rows1)]
		
		# Isolate the row numbers that changed
		diff_rows = [row[0] for row in enumerate(zip(rows0, rows1)) if row[1][0] != row[1][1]]

		# Isolate the columns that changed
		diff_cols = [col[1] for col in zip(cols0, cols1) if col[0] != col[1]]

		# Transpose the columns
		diff_cols = ["".join(column) for column in map(None, *diff_cols)]

		# Put it back into a string and return
		return '\n'.join(diff_cols[diff_rows[0]:diff_rows[-1]+1])

	def get_option(self, start, end):
		pattern = re.compile('((?:[A-Z]\w*\s?)+)\.+\s?((?:\S+\s?)+)')
		text = self.buffer.get_region(start[0], start[1], end[0], end[1])
		text = "\n".join(text)
		print text
		results = pattern.findall(text)
		if results:
			results = [(x.strip(),y.strip()) for x,y in  results]
		try:
			return (results[0][0], results[0][1])
		except IndexError:
			return text.strip()
		except:
			print "Unexpected error:", sys.exc_info()[0]
			raise
			 
	def find_boot_order(self, x0=2, y0=None, x1=78, y1=None, boot_seq=0):
		old_result = -1
		self.update(DOWN, 2)
		line = self.buffer.get_cursor_pos()[0]        
		self.update(UP, 2)
		line=line-1
		set=0
		while True:
			text = self.buffer.get_region(line, x0, line, x1)
			text = "\n".join(text)
			tem_str1 = text.strip('x')
			tem_str= tem_str1.rstrip('a ')
			if old_result == line:
				raise StopIteration
			elif tem_str.find('<ENTER>') != -1:
				if tem_str.find('Boot Sequence') != -1:
					boot_seq=1              
				before = self.buffer.pretty()
				self.update(' ', 5)
				after = self.buffer.pretty()
				coords = self.find_box(before, after)
				for option in self.find_boot_order(coords[0],coords[1],coords[2],coords[3], boot_seq):
					yield option             
				if boot_seq==1:
					yield 2
				self.update(ESC, 5)
			else:
				if set == 1:
					self.update(' ', 5)
					yield 1
				if boot_seq == 1 and tem_str.find('*') != -1:
					self.update(' ', 5)
					set=1
				old_result = line
				yield 0              
			self.update(DOWN, 2)
			line = self.buffer.get_cursor_pos()[0]

	def boot_usc(self,device_num = 1):
		logging.info('Looking for USC Setup prompt...')
		while True:
			self.update()
			area = "\n".join(self.buffer.get_region(2, 60, 2, 100))

			if re.search('F10.*=.*System Services', area):
				logging.info('Found prompt, sending F10')
				self.update(F10)

			if re.search('ering System Services',area):
				return 

	def boot_diag(self,device_num = 1):
		logging.info('Looking for BIOS Setup prompt...')
		while True:
			self.update()
			area = "\n".join(self.buffer.get_region(0, 60, 1, 80))
			if re.search('F2.*=.*Setup', area):
				logging.info('Found F2 prompt')
				break
		while True:
			self.update()
			area = self.buffer.dump()
			if re.search('No boot device', area):
				logging.warning('No boot device available')
				log_name=('logs\Log_Device_%d.txt' % device_num)
				f=file(log_name,'w')
				area = 'No boot device available'
				f.write(area)
				f.close()              
				print 
				break
			if re.search('PXE Environment', area):
				logging.info('Boot into PXE')
				self.update('4', 2)
				self.update(ENTER, 2)
			if re.search('Enter option', area):
				logging.info('Customer Diagnostics loaded')
				self.update(DOWN, 2)
				self.update('4', 2)
				logging.info('Extended diags Running')
				self.run_cmd('ddgui /b /olog.txt /clk /np')
				self.get_logs(device_num)
				print 
				break

	def run_cmd(self, cmd=''):
		pattern = re.compile('(\S*\s*)')
		res = pattern.findall(cmd)
		for s in res:
			self.update(s)
		self.update(ENTER)

	def save_bios(self):
		while True:
			before = self.buffer.pretty()
			self.update(ESC, 5)
			after = self.buffer.pretty()
			diffedScreen = self.diff_screens(before, after)
			help = self.process_help(diffedScreen)
			if help.find('Save Changes and Exit') != -1:
				self.update(' ', 5)
				logging.info('BIOS Settings got Saved')
				return    

	def change_boot_order(self, device_num = 1):
		self.boot_diag(device_num)
		self.reboot()
		self.do_setup()
		for opt in self.find_boot_order():
			if opt == 1:
				self.save_bios()              
				return '0'
			if opt == 2:
				return '1'

	def Boot_To_USC(self, device_num = 1):
		self.reboot()
		self.boot_usc(device_num)
		while True:
			self.update()
			area = "\n".join(self.buffer.get_region(60, 50, 25, 15))
			if re.search("ystem_services.*startup.nsh.*endif.*", area):
				logging.info('Launching USC GUI')
				self.update("Launcher.efi /n")
				logging.info('Setup screen is fully drawn')
				return True

		return False

	def get_logs(self, device_num = 1):
		while True:
			self.update(ENTER)
			area = self.buffer.dump()
			if re.search('Diag ',area):
				logging.info('Capturing the diagnostics logs')      
				self.run_cmd('type log.txt /p')
				area=self.buffer.dump()
				log_name=('logs\Log_Device_%d.txt' % device_num)
				f=file(log_name,'w')               
				while True:
					area = "\n".join(self.buffer.get_region(24,0,25,80))                                      
					if re.search('Strike a key',area):
						area= "\n".join(self.buffer.get_region(0,0,23,80))
						f.write(area)
						f.write("\n")
						f.write("\n")                       
						self.update()                       
						self.update(ENTER)
					else:
						area = "\n".join(self.buffer.get_region(0,0,24,80))                   
						f.write(area)
						f.close()
						self.update()
						logging.info('Finished capturing logs')
						return 0

 
