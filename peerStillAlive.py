# -*-coding:Utf-8 -*
import sys, traceback, time
import xmlrpc
import socket
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import threading
from queue import Queue
from datetime import datetime, timedelta

TTL = 2
TimeOutAlive = timedelta(seconds = 10)
TimeToDiscoveryMissingPeers =  5


########################################################################
# COMMAND HANDLERS
########################################################################
# Note: They all assume either "init" or "superinit" is called first,
#       and then the local Peer will be in the "peer" global variable.
########################################################################
def init(nmax, pid, IPaddr, portno):
	global peer
	peer = Peer(nmax, pid, IPaddr, portno)

def superinit(nmax, IPaddr, portno):
	global peer
	peer = SuperPeer(nmax, IPaddr, portno)

def whoami():
	print("{:10}: {}".format("name", peer.name))
	print("{:10}: {}".format("pid", peer.pid))

def seenmsgs():
	print("seen messages:", peer.seen_msgs)

def wait():
	peer.out.join()
	peer.inp.join()

def stop():
	peer.out.stop()
	peer.out.join()
	peer.inp.join()
	sys.exit(0)

def plist():
	print("Peer max neighbour capacity:", peer.nmax)
	print("Peer list size:", len(peer.plist))
	print('{:4} {:6} {:16} {:3} {:18} {:10}'.format('', 'name', 'address', 'nmax', 'last heard', 'sent alive'))
	for i,(pid,(name,nmax,date,alivesent)) in enumerate(sorted(peer.plist.items(), key=lambda i: i[1][1])): # Changed
		print('{:3}) {:6} {:16} {:3} {:%Y-%m-%d %H:%M:%S} {:10}'.format(i+1, name, pid, nmax, date, alivesent))

def hello(pid):
	#print(peer.pid, peer.name, peer.msgid, TTL)
	peer.seen_msgs.add( (peer.msgid, peer.pid) )
	peer.out.send_msg(dest=pid, msgtype='ping', msgargs=(peer.pid, peer.name, peer.nmax, peer.msgid, TTL, peer.pid))
	peer.msgid += 1
	#peer.out.send_msg(dest=pid, msgtype='send_alive', msgargs=(peer.pid,))
########################################################################



class Client(threading.Thread):
	"""
	Thread for outgoing messages (client side of the peer)
	"""
	def __init__(self, peer):
		threading.Thread.__init__(self)
		self.msgQ = Queue() # A synchronized (mutex) queue
		self.peer = peer
	
	def log(self, *msg):
		print("[%s]" % self.peer.name, *msg)
	
	def send_msg(self, dest, msgtype, msgargs):
		self.msgQ.put( (dest, msgtype, msgargs) )
	
	def stop(self):
		self.msgQ.put( (self.peer.pid, 'stop', ()) )
	
	def run(self):
		while True:
			dest, msgtype, msgargs = self.msgQ.get() # Read from msgQ is blocking
			s = xmlrpc.client.ServerProxy('http://' + dest)
			try:
				getattr(s, msgtype).__call__(*msgargs)
			except socket.error:
				print ("ERROR CONNECTION REFUSED")
				with self.peer.plock:
					if dest in self.peer.plist: del self.peer.plist[dest]
				pass
			except xmlrpc.client.Error as err:
				print("ERROR!")
				print("An error occurred")
				print("Fault code: %d" % err.faultCode)
				print("Fault string: %s" % err.faultString)
				traceback.print_exc()
			except xmlrpc.client.Fault as err:
				print("ERROR!")
				print("A fault occurred")
				print("Fault code: %d" % err.faultCode)
				print("Fault string: %s" % err.faultString)
				traceback.print_exc()
			except Exception as err:
				print("ERROR!")
				print("An exception occurred")
				print('Exception:', err)
				traceback.print_exc()
			if msgtype == 'stop': break
		self.log("Client Done!")

class Server(threading.Thread):
	"""
	Thread for incoming messages (server side of the peer)
	"""
	def __init__(self, peer):
		threading.Thread.__init__(self)
		self.loop = True
		self.peer = peer
		try:
			self.server = SimpleXMLRPCServer((peer.IPaddr, peer.portno), allow_none=True)
			self.server.register_instance(self.peer)
		except Exception as e:
			print(e)
			sys.exit(0)
	
	def log(self, *msg):
		print("[%s]" % self.peer.name, *msg)
	
	def stop(self):
		self.server.server_close()
		self.loop = False
	
	def run(self):
		while self.loop:
			#self.log("xmlrpc server is handling a request...")
			self.server.handle_request()
		self.log("Server Done!")

class Still_alive(threading.Thread): # Change
	"""
	Thread for mechanism for discovering missing peers, and adjusting neighbourhood accordingly
	"""
	def __init__(self, peer):
		threading.Thread.__init__(self)
		self.loop = True
		self.peer = peer

	def log(self, *msg):
		print("[%s]" % self.peer.name, *msg)
	
	def stop(self):
		self.loop = False

	def mechanism(self):
		print("Mechanish discory missing peers:")
		print("Peer list size before StillAlive:", len(self.peer.plist))
		with self.peer.plock:
			for pid, value in self.peer.plist.copy().items():
				if (value[3] == True): 
					del self.peer.plist[pid] 
				# remove from nlist too
				elif (datetime.now() > TimeOutAlive + value[2]):
					self.peer.out.send_msg(dest=pid, msgtype='send_alive', msgargs=(self.peer.pid,))
					self.peer.plist[pid][3] = True
		print("Peer list size after StillAlive:", len(self.peer.plist))

	def run(self):
		while self.loop:
			self.mechanism()
			time.sleep(TimeToDiscoveryMissingPeers)
			print ("HI STILL ALIVE")

		self.log("Still Alive Done!")	

class Peer(object):
	
	def __init__(self, nmax, name, IPaddr, portno):
		self.nmax = nmax
		self.name = 'P' + str(name)
		self.IPaddr = IPaddr
		self.portno = int(portno)
		self.pid = IPaddr + ':' + portno
		self.plist = {}	  	    # Changed
		self.msgid = 0			# Id of last message sent by this peer
		self.seen_msgs = set()	# A set of tuples (msgid, source-pid)
		self.plock = threading.RLock() # Changed
		
		# Server thread
		self.inp = Server(self)
		self.inp.start()
		
		# Client thread
		self.out = Client(self)
		self.out.start()

		# Still Alive thread
		self.still_alive = Still_alive(self) # Changed
		self.still_alive.start() # Changed
	
	def __update_timer__(self, sourcepid):
		with self.plock:
			if sourcepid in self.plist:
				self.plist[sourcepid][2] = datetime.now()
				self.plist[sourcepid][3] = False
			#else:
			#	self.plist[sourcepid] = ['NAME', -10, datetime.now(), False] # Changed
			#	#raise Exception("Peer not in Plist?? What to do?")
	
	def ping(self, sourcepid, name, nmax, msgid, TTL, senderpid):
		self.__update_timer__(sourcepid)
		print ('PING=','sourcepid', sourcepid, 'name', name, 'nmax', nmax, 'msgid', msgid, 'TTL', TTL, 'senderpid', senderpid)
		if (msgid, sourcepid) in self.seen_msgs: return
		self.seen_msgs.add( (msgid, sourcepid) )
		TTL -= 1
		if TTL > 0:	# We don't forward the message if TTL = 0
			with self.plock:
				for p in self.plist.keys(): # Changed
					# Don't forward back to the sender
					if p == senderpid: continue
					# Forward ping
					self.out.send_msg(dest=p, msgtype='ping', msgargs=(sourcepid, name, nmax, msgid, TTL, self.pid))
				print ('PING=','Adding sourcepid to PLIST', sourcepid)
				self.plist[sourcepid] = [name, int(nmax), datetime.now(), False] # Changed
			
		self.out.send_msg(dest=sourcepid, msgtype='pong', msgargs=(self.pid, self.name, self.nmax))
		
	def pong(self, sourcepid, name, nmax):
		self.__update_timer__(sourcepid)
		print ('PONG=', 'sourcepid', sourcepid, 'name', name, 'nmax', nmax)
		with self.plock: # Changed
			print ('PONG=','Adding sourcepid to PLIST', sourcepid)
			self.plist[sourcepid] = [name, int(nmax), datetime.now(), False] # Changed

	def send_alive(self, sourcepid): # Changed
		self.__update_timer__(sourcepid)
		print ("I received a still alive petition from", sourcepid)
		print ("I'm sending a alive msg to", sourcepid)
		self.out.send_msg(dest=sourcepid, msgtype='receive_alive', msgargs=(self.pid,))
		
	def receive_alive(self, sourcepid): # Changed
		self.__update_timer__(sourcepid)
		print ("I received a I'm alive from", sourcepid)
	
	def stop(self):
		self.inp.stop()
		self.still_alive.stop() # Changed


class SuperPeer(Peer):
	def __init__(self, nmax, IPaddr, portno):
		super(SuperPeer, self).__init__(nmax, 0, IPaddr, portno)





if __name__=='__main__':
	print("Starting...")
	
	commands = {
		# cmd name : 	[ cmd_handler, (arg_tuple,), 'Description' ]
		'superinit':	[ superinit, (), 'Initialize the super peer. Must be called only once!' ],
		'init':			[ init, (), 'Initialize a peer (not the super peer). Must be called only once!' ],
		'whoami':		[ whoami, (), 'Prints the peer''s identity' ],
		'seen':			[ seenmsgs, (), 'Prints the messages seen by this peer' ],
		'wait':			[ wait, (), 'It stops the peer until you kill it' ],
		'stop':			[ stop, (), 'Stops the peer' ],
		
		'hello':		[ hello, (), 'Enters an existing network, via a known peer' ],
		'plist':		[ plist, (), 'Prints the list of know peers' ],
	}
	
	def usage():
		print('='*20 + ':')
		print('Usage\n' + '='*20 + ':')
		for c,specs in sorted(iter(commands.items()), key=lambda k_v: k_v[0]):
			print('{:23}: {}'.format(c, specs[2]))
		print('='*20 + ':')
	
	def execute_command(c):
		if c[0] in commands:
			commands[c[0]][0](*(commands[c[0]][1] + c[1:]))
		else:
			print('Error: command "%s" not found.' % c)
	
	# If arguments are passed to command line, execute commands right away
	if len(sys.argv) > 1:
		try:
			c = tuple(sys.argv[1:])
			command = []
			for w in c:
				if w != ',': command.append(w)
				else:
					execute_command(tuple(command))
					command = []
			execute_command(tuple(command))
		except Exception as e:
			print('Error:', e)
			traceback.print_exc()
	
	# Shell loop
	while True:
		try:
			c = input((peer.name if 'peer' in globals() else 'NO-PEER') + '>> ').split()
			if not c: continue
			elif c[0] == 'exit': break
			elif c[0] == 'help' or c[0] == 'usage' or c[0] == '?':
				usage()
				continue
			execute_command(tuple(c))
		except EOFError:
			break
		except Exception as e:
			print('Error:', e)
			traceback.print_exc()
			continue
	
	print("Exiting...")
	stop()
