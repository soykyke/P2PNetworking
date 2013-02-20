# -*-coding:Utf-8 -*
import sys, traceback, time
import xmlrpc
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import threading
from queue import Queue
from datetime import datetime, timedelta

TTL = 2
TimeOutAlive = timedelta(seconds = 5)
TimeToDiscoveryMissingPeers =  10


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
	print('{:4} {:6} {:20} {:3}'.format('', 'name', 'address', 'nmax'))
	#for i,(pid,name,nmax) in enumerate(sorted(peer.plist, key=lambda x_y: int(x_y[1][1:]))):
	# print('{:3}) {:6} {:20} {:3}'.format(i+1, name, pid, nmax))
	for k,v in peer.plist.items(): # Changed
		print (k,v) # Changed

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
			dest, msgtype, msgargs = self.msgQ.get() # Blocking read
			s = xmlrpc.client.ServerProxy('http://' + dest)
			try:
				getattr(s, msgtype)(*msgargs)
			except Exception as e:
				print('Error:', e)
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
		print("Peer list size:", len(self.peer.plist))
		with self.peer.plock:
			for pid, value in self.peer.plist.items():
				if (value[3] == True): 
					del self.peer.plist[pid] 
				# remove from nlist too
				if (datetime.now() > TimeOutAlive + value[2]):
					self.peer.out.send_msg(dest=pid, msgtype='send_alive', msgargs=(self.peer.pid,))
					self.peer.plist[pid][3] = True

	def run(self):
		while self.loop:
			self.mechanism()
			time.sleep(TimeToDiscoveryMissingPeers)

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
		
		# Server thread
		self.inp = Server(self)
		self.inp.start()
		
		# Client thread
		self.out = Client(self)
		self.out.start()

		# Still Alive thread
		self.still_alive = Still_alive(self) # Changed
		self.still_alive.start() # Changed
		
		self.plock = threading.RLock() # Changed
		
	
	def ping(self, sourcepid, name, nmax, msgid, TTL, senderpid):
		if (msgid, sourcepid) in self.seen_msgs: return
		self.seen_msgs.add( (msgid, sourcepid) )
		TTL -= 1
		if TTL > 0:	# We don't forward the message if TTL = 0
			for p,(n,m) in self.plist.items(): # Changed
				# Don't forward back to the sender
				if p == senderpid: continue
				# Forward ping
				self.out.send_msg(dest=p, msgtype='ping', msgargs=(sourcepid, name, nmax, msgid, TTL, self.pid))
		with self.plock: # Changed
			self.plist[sourcepid] = [name, nmax, datetime.now(), False] # Changed
			
		self.out.send_msg(dest=sourcepid, msgtype='pong', msgargs=(self.pid, self.name, self.nmax))
		
	def pong(self, pid, name, nmax):
		with self.plock: # Changed
			self.plist[pid] = [name, nmax, datetime.now(), False] # Changed

	def send_alive(self, sourcepid): # Changed
		print ("I received a still alive petition from", sourcepid)
		self.plist[sourcepid][2] = datetime.now()
		self.plist[sourcepid][3] = False
		print ("I'm sending a alive msg to", sourcepid)
		self.out.send_msg(dest=sourcepid, msgtype='receive_alive', msgargs=(self.pid,))
		
	def receive_alive(self, sourcepid): # Changed
		print ("I received a I'm alive from", sourcepid)	
		self.plist[sourcepid][2] = datetime.now()
		self.plist[sourcepid][3] = False
	
	def stop(self):
		self.inp.stop()


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
