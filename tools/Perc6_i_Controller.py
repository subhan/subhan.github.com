import re
import time 
import sys
import os

ESC = chr(27)
ENTER = chr(13)
F10 = ESC + '0'
F1 = ESC + '1'
F2 = ESC + '2'
DOWN = ESC + '[B'
UP = ESC + '[A'
RIGHT = ESC+'[C'
LEFT = ESC+'[D'
TAB	= '\x09'
ENTER1 = '\x0A'
SPACE = "\x20"

def combinatations(pdisks,raids,add=[]):
	l = sorted(raids.keys())
	l = sorted(l,key=len)
	if pdisks == 1:
		add.append('r0')
		return add
	elif pdisks:
		for raid in l:
			p = raids[raid]
			if p <= pdisks:
				add.append(raid)
				pdisks -= p
			else:
				return combinatations(pdisks,raids,add)
	return add



class Perc6_i_Controller:

	def __init__(self,controller,serial):
		self.ctrl_r = chr(18)
		self.serial = serial
		self.raid = {
			'r0':1,
			'r1':2,
			'r5':3,
			'r6':4,
			'r10':4,
			'r50':6,
			'r60':8
		}
		self.ctrl_name = controller	

	def reset(self):
		print "resetting the racadm"
		self.serial.thread.kill()
		self.serial.thread.kill()
		self.serial.thread.kill()
		self.serial.conn.close()
		os.system("racadm -r %s -u root -p calvin racreset"%(self.serial.drac_ip))
		time.sleep(3*60)
		self.serial.__init__()

	def Press_Ctrl_R(self,timeout):
		print "Searching for Controller Properites option ..."
		key_sent = False
		kPress = 0
		pattern = re.compile('Press <Ctrl><R> to Run Configuration Utility')
		while timeout > 0:
			self.serial.update()
			area = self.serial.buffer.dump()
			if pattern.search(area,re.I):
				if kPress < 2:
					print "Pressed <CTRL><R>"
					self.serial.update(self.ctrl_r)
					print "Pressed <CTRL><R>"
					self.serial.update(self.ctrl_r)
				key_sent = True
				kPress += 1	
			elif key_sent and re.search(r'F1-Help', area):
				break

			#time.sleep(5)
			timeout -= 0.5

		return timeout


	def GoToControllerProperties(self):
		"""
		launcher for Controller properties
		"""
		#print "Searching for Controller Properites option ..."
		key_sent = False
		kPress = 0
		pattern = re.compile('Press <Ctrl><R> to Run Configuration Utility')
		#tsp,self.timeout = 0,5*60
		flag = self.Press_Ctrl_R(8*60)
		if not flag:
			self.reset()
			self.serial.reboot()
			flag = self.Press_Ctrl_R(8*60)
			if not flag:
				return False

		self.serial.update()
		area = self.serial.buffer.dump()
		return area

	def _filterPhysicalDisks(self,data):
		"""
		filter's the Physical disk ids from the raw list(data)
		"""
		vd = False
		if re.search("virtual.*disk","".join(data),re.I):
			vd = True

		index = -1
		for item in data:
			if re.search("Unconfigured.Physical.Disks",item):
				index = data.index(item)
				break
		else:
			no_config = self.serial.buffer.get_region(5,5,8,32)
			if re.search("no configuration present","".join(no_config),re.I):
				pdisk_info = self.serial.buffer.get_region(7,55,8,75)	
				pdCount = re.search("PD Count.*:(.*\d+).*","".join(pdisk_info))
				if pdCount:
					pdCount = pdCount.group(1).strip()
					return range(int(pdCount))		
			if vd:
				return "",False
			print "No free Physical disks are available -> FAILED"
			self.serial.conn.close()
			self.serial.thread.kill()
			self.serial.thread.kill()
			sys.exit(1)

		disks = []
		for i in range(index,len(data)):
			reObj = re.search("\d{1,2}:\d{1,2}:\d{1,2}",data[i])
			if reObj:
				disks.append(reObj.group(0))

		return disks
	
	def slice(self,size,raid):
		new_raid_info = [] 
		while int(size) > 0:
			print "setting raid size"
			self.serial.update('%s'%(size))
			self.serial.update(TAB)
			print "Virtual Disk Size : %s in Controller"%size
			self.serial.update(TAB)
			self.serial.update(TAB)
			self.serial.update(ENTER)
			self.serial.update(ENTER)
			
			print "searching for 'Add New VD' tab in the menu"
			self.serial.update()
			while True:
				time.sleep(2)
				self.serial.update(F2)
				self.serial.update()
				area = self.serial.buffer.dump()
				if re.search('Add New VD',area):
					self.serial.update(ENTER)
					break
				self.serial.update(UP)
			self.serial.update(TAB)
			size = size/2

		#add new slice VD info
		self.serial.update()
		time.sleep(3)
		self.serial.update()
		output = self.serial.buffer.dump().split('xx')
		for line in output:
			info =  re.findall("Virtual Disk:(.*),(.*)GB",line)
			if info and len(info[0]) == 2:
				info = info[0]
				lhs,rhs = info[0].strip(),info[1].strip()
				new_raid_info.append((lhs.split()[0],rhs.split()[0],raid))
		return new_raid_info

	def createSliceVd(self,raid_info,max=True):
		self.serial.reboot()
		print "System Rebooting..."
		if not self.GoToControllerProperties():
			return "Unable open Controller properites,serial communication failure",True
		#check if already virtual disks exists
		self.serial.update()
		time.sleep(5)
		self.serial.update()
		pdisks = self._filterPhysicalDisks(self.serial.buffer.get_region(6,5,50,35))
		if pdisks[0] == '':
			self.serial.update()	
			print "Already raid exists"
			print "Deleting existing raids"
			self._delete(raid_info)	
			self.serial.update()
			time.sleep(5)
			self.serial.update()
			pdisks = self._filterPhysicalDisks(self.serial.buffer.get_region(6,5,50,35))

		print "searching for 'Create New VD' tab in the menu"
		while True:
			self.serial.update(F2)
			self.serial.update()
			area = self.serial.buffer.dump()
			if re.search('Create New VD',area):
				self.serial.update(ENTER)
				break
			self.serial.update(UP)

		for i in xrange(3):
			self.serial.update()
			area = self.serial.buffer.dump()
			if re.search('RAID Level\s:\sx\s\sRAID-\d+\s x',area):
				self.serial.update(ENTER)
				print "Raid Creation Page"
				break
		raid_keys = {
			'r0':0,
			'r1':1,
			'r5':2,
			'r6':3,
			'r10':4,
			'r50':5,
			'r60':6
		}
		#select RAID Level here
		raid_level = raid_info.get('Raid Level')
		print "selecting Raid Level : %s"%raid_level
		for i in range(raid_keys[raid_level]):
			self.serial.update(DOWN)

		self.serial.update(ENTER)
		self.serial.update(DOWN)

		#select all phsical disks
		for i in range(len(pdisks)):
			self.serial.update(SPACE)
		self.serial.update(TAB)
		self.serial.update()
		self.serial.update()
		area = self.serial.buffer.dump().split('xxx')
		#RAID Size
		for line in area:
			data = re.findall('VD Size.*:(.*)GB',line)
			if data and len(data[0].strip()):
				size = float(data[0].strip())
				return self.slice(size/2,raid_level),False
			elif data:
				import pdb
				pdb.set_trace()
		else:
			return "unable to create RAID --> FAILED",True

					
	def RaidCreate(self,raid_info,max=None):
		self.serial.reboot()
		print "System Rebooting..."
		if not self.GoToControllerProperties():
			return "Unable open Controller properites,serial communication failure",True
	
		self.stripe_size = {
			'8 KB':0,
			'16 KB':1,
			'32 KB':2,
			'64 KB':3,
			'128 KB':4,
			'256 KB':5,
			'512 KB':6,
			'1 MB':7,
		}

		self.rp = {
			'No Read Ahead':0,
			'Read Ahead':1,
			'Adaptive Read Ahead':2
		}

		self.wp = {
			'Write Through':0,
			'Write Back':1
		}

		if max:
			self.serial.update()	
			#physical disks screen in Controller Properties Front Page
			pdisks = self._filterPhysicalDisks(self.serial.buffer.get_region(6,5,50,35))
			if pdisks[0] == '':
				return "Already raid exists",False

			for raid in combinatations(len(pdisks),self.raid):
				self._create({'Raid Level':raid})
			return "successfully created",False
		else:
			self._create(raid_info)
			return "successfully created",False

	def _delete(self,raid_info):
		print "searching for 'Clear Config' tab in the menu"
		while True:
			self.serial.update(F2)
			self.serial.update()
			area = self.serial.buffer.dump()
			if re.search('Clear Config',area):
				self.serial.update(ENTER)
				self.serial.update(RIGHT)
				self.serial.update(ENTER)
				break
			self.serial.update(UP)
		result = self.serial.buffer.dump()
		return result,False	

	def DeleteRaid(self,raid_info):
		self.serial.reboot()
		print "System Rebooting..."
		self.GoToControllerProperties()
		return self._delete(raid_info)

	def _create(self,raid_info):
		raid_keys = {
			'r0':0,
			'r1':1,
			'r5':2,
			'r6':3,
			'r10':4,
			'r50':5,
			'r60':6
		}
		
		print "searching for 'Create New VD' tab in the menu"
		while True:
			self.serial.update(F2)
			self.serial.update()
			area = self.serial.buffer.dump()
			if re.search('Create New VD',area):
				self.serial.update(ENTER)
				break
			self.serial.update(UP)

		for i in xrange(3):
			self.serial.update()
			area = self.serial.buffer.dump()
			if re.search('RAID Level\s:\sx\s\sRAID-\d+\s x',area):
				self.serial.update(ENTER)
				print "Raid Creation Page"
				break

		#select RAID Level here
		raid_level = raid_info.get('Raid Level')
		print "selecting Raid Level : %s"%raid_level
		for i in range(raid_keys[raid_level]):
			self.serial.update(DOWN)

		self.serial.update(ENTER)
		self.serial.update(DOWN)

		#physical disk selection
		print "selecting Physical disks"
		for i in range(self.raid[raid_level]):
			self.serial.update(SPACE)
		self.serial.update(TAB)

		#RAID Size
		print "setting raid size"
		self.serial.update('%s'%float(100))
		self.serial.update(TAB)

		#RAID Name
		print "setting raid name"
		self.serial.update('TestVD')
		self.serial.update(TAB)

		#select Advace Settings
		self.serial.update(SPACE)
	
		#strip size
		self.serial.update(DOWN)	
		self.serial.update(ENTER)	
		for i in range(self.stripe_size['64 KB']):
			self.serial.update(DOWN)
	
		self.serial.update(ENTER)

		self.serial.update(DOWN)
		self.serial.update(ENTER)	
		for i in range(self.rp['Read Ahead']):
			self.serial.update(DOWN)

		self.serial.update(ENTER)

		self.serial.update(DOWN)
		self.serial.update(ENTER)	
		for i in range(self.wp['Write Back']):
			self.serial.update(DOWN)

		self.serial.update(ENTER)
		#arel = self.serial.buffer.get_region(12,0,18,30)
		self.serial.update(TAB)
		self.serial.update(TAB)
		self.serial.update(TAB)
		self.serial.update(TAB)

		#finish RAID Creation
		self.serial.update(ENTER)
		self.serial.update(ENTER)
		print "time sleep for 15 seconds"
		time.sleep(15)	
			
	def ValidateRaid(self,raid_info):
		self.serial.reboot()
		area = self.GoToControllerProperties()
		if not area:
			return "Unable open Controller properites,serial communication failure",True
		self.serial.update()
		area = self.serial.buffer.dump()
		print "serial info : \n%s"%area
		raid = raid_info.get('Raid Level')
		if raid:
			raid_level = re.findall('RAID Level\s{0,2}:(\s\d+)\s+xx\s',area)
			if raid_level:
				raid_level = raid_level[0].strip()
				if raid.find(raid_level) >= 0:
					print "Raid Level : %s in Controller Properites --> PASS"%raid
				else:
					return """Unable to find expected Raid Level : %s in Controller Properites\n\tGot different Raid Level :%s --> FAIL"""%(raid,raid_level),True
			else:
				return "Unable to find Raid Level '%s' in Controller Properties"%raid,True

		self.serial.update(ENTER)
		self.serial.update()	
		self.serial.update()	

		#physical disk region in raid
		pdisks = self.serial.buffer.get_region(12,5,50,32)	

		self.serial.update()	
		#policy & strip size info region
		extra = self.serial.buffer.get_region(12,35,30,60)

		###################################################################### 
		#validation for the raid stripe size 
		stripe_size = raid_info.get("Stripe Size")
		if stripe_size:
			for ele in extra:
				if re.search('Element Size:.*%s'%stripe_size.replace(' ',''), ele):
					print "Stripe Size '%s' validated in Controller properties"%stripe_size
					break
			else:
				return "Unable to find Stripe Size : %s in Controller Properties"%stripe_size,True

		"""
		#validation for the Read Policy 
		rp = raid_info.get('Read Policy')
		if rp:
			for ele in extra:
				rValue = re.findall('Read Policy:x(.*)x', ele)
				if rValue and re.search(rValue[0],rp):
					print "Read Policy '%s' validated in Controller properties"%rp
					break
				elif rValue:
					return "Read Policy '%s' value not set, Still old value exists '%s'"%(rp,rValue[0]), True
			else:
				import pdb
				pdb.set_trace()
				return "Unable to find Read Policy : %s in Controller Properties"%rp,True
		"""
		###################################################################### 
				 
		self.ctrl_name = re.sub("\(.*\)","",self.ctrl_name)

		if re.search(self.ctrl_name,area):
			print "Controller available %s"%self.ctrl_name
		else:
			return "Unable to find the Controller Name : %s"%self.ctrl_name,True

		"""	
		size = raid_info.get('raid size')
		if size and re.search('Size.*:.*%s.*GB'%size,area):
			print "Virtual Disk Size : %s in Controller"%size
		"""	

		return area,False	
