import sys, traceback, time
import xmlrpc
import socket
import pydot
import math
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import threading
from queue import Queue
from datetime import datetime, timedelta

TTL = 2
TimeOutAlive = timedelta(seconds = 5)
TimeToDiscoveryMissingPeers =  2
Nlist_Manager_SleepTime = 10


########################################################################
# COMMAND HANDLERS
########################################################################
# Note: It is assumed that either "init" or "superinit" is called first,
#       and then the local Peer will be in the "peer" global variable.
########################################################################
def init(nmax, name, IPaddr, portno):
	global peer
	peer = Peer(nmax, name, IPaddr, portno)

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

def nlist(*peers):
	with peer.plock:
		peer_names = list(peers) if peers else None
		if not peer_names:
			# No arguments passed: just print out my neighbours
			nlist_dot_graph([ (peer.pid, peer.name, peer.nmax, [ (p,peer.plist[p][0],peer.plist[p][1]) for p in peer.nlist ]) ])
		else:
			peer.nlist_waited_answers = 0
			peer.nlist_answers = []
			
			# Send request message to every peer in my neighbour list
			# First, find the correct peer by its name
			for name in peer_names:
				if name == peer.name:
					# Send request message to myself (trick to have my neighbours too)
					peer.out.send_msg(dest=peer.pid, msgname='get_neighbours', msgargs=(peer.pid, peer.name, peer.nmax, len(peer.nlist)))
					peer.nlist_waited_answers += 1
					continue
				
				for p,(n,m,l,d,s,r) in peer.plist.items():
					if n==name:
						peer.out.send_msg(dest=p, msgname='get_neighbours', msgargs=(peer.pid, peer.name, peer.nmax, len(peer.nlist)))
						peer.nlist_waited_answers += 1
						break
				else:
					pass # The requested peer name does not exist!

def plist():
	print("Peer max neighbour capacity:", peer.nmax)
	print("Peer list size:", len(peer.plist))
	print('{:4} {:6} {:16} {:4} {:19} {:10} {:9} {:9}'.format('', 'name', 'address', 'nmax', 'last heard', 'sent alive', 'rejects', 'in nlist'))
	for i,(pid,(name,nmax,l,date,alivesent,rejects)) in enumerate(sorted(peer.plist.items(), key=lambda i: i[1][1])): # Changed
		print('{:3}) {:6} {:16} {:4} {:%Y-%m-%d %H:%M:%S} {:10} {:9} {:9}'.format(i+1, name, pid, nmax, date, alivesent, rejects, 'Y' if pid in peer.nlist else ' '))

def hello(pid):
	peer.seen_msgs.add( (peer.msgid, peer.pid) )
	peer.out.send_msg(dest=pid, msgname='ping', msgargs=(peer.pid, peer.name, peer.nmax, len(peer.nlist), peer.msgid, TTL, peer.pid))
	peer.msgid += 1
########################################################################


def nlist_dot_graph(nlist_answers):
	"""
	Prints the dot graph out of the nlist_answers.
	"""
	print(nlist_answers)
	graph = pydot.Dot("nlist", graph_type='graph')
	
	nodes = set()
	edges = set()
	
	for pid, name, nmax, nlist in nlist_answers:
		nodes.add( (pid,name,nmax) )
		for p,n,m in nlist:
			nodes.add( (p,n,m) )
			edges.add( ((pid,name,nmax),(p,n,m)) )
	
	printed_edges = set()
	for pid,name,nmax in sorted(nodes, key=lambda x: -x[2]):
		graph.add_node(pydot.Node('%s(%d)'%(name,nmax), style='filled', fillcolor='0.000 0.000 %.3f'%(1.-((nmax-3.)/float(MAX_NB))), fontcolor='white' if (nmax)/float(MAX_NB) >= 0.8 else 'black'))
	for ((p1,n1,m1),(p2,n2,m2)) in edges:
		if ((p2,n2,m2),(p1,n1,m1)) in edges and not ((p2,n2,m2),(p1,n1,m1)) in printed_edges and not ((p1,n1,m1),(p2,n2,m2)) in printed_edges:
			graph.add_edge(pydot.Edge('%s(%d)'%(n1,m1), '%s(%d)'%(n2,m2)))
			printed_edges.add( ((p1,n1,m1),(p2,n2,m2)) )
			printed_edges.add( ((p2,n2,m2),(p1,n1,m1)) )
	
	graph.write('nlist.dot')
	#graph.write_png('nlist.png', prog='fdp')
	graph.write_png('nlist.png', prog='dot')






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
	
	def send_msg(self, dest, msgname, msgargs):
		self.msgQ.put( (dest, msgname, msgargs) )
	
	def stop(self):
		self.msgQ.put( (self.peer.pid, 'stop', ()) )
	
	def run(self):
		while True:
			dest, msgname, msgargs = self.msgQ.get() # Read from msgQ is blocking
			s = xmlrpc.client.ServerProxy('http://' + dest)
			try:
				getattr(s, msgname).__call__(*msgargs)
			except socket.error:
				print ("ERROR CONNECTION REFUSED")
				with self.peer.plock:
					if dest in self.peer.plist:
						del self.peer.plist[dest]
					if dest in self.peer.nlist:
						del self.peer.nlist[dest]
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
			if msgname == 'stop': break
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

class Still_alive(threading.Thread):
	"""
	Thread for mechanism for discovering missing peers, and adjusting peer list accordingly
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
		with self.peer.plock:
			for pid, value in self.peer.plist.copy().items():
				if (value[4] == True):
					del self.peer.plist[pid] 
					del self.peer.nlist[pid]
				elif (datetime.now() > TimeOutAlive + value[3]):
					self.peer.out.send_msg(dest=pid, msgname='send_alive', msgargs=(self.peer.pid, self.peer.name, self.peer.nmax, len(self.peer.nlist)))
					self.peer.plist[pid][4] = True

	def run(self):
		while self.loop:
			self.mechanism()
			time.sleep(TimeToDiscoveryMissingPeers)
		self.log("Still Alive Done!")

class Nlist_Manager(threading.Thread):
	"""
	Thread for managing the Peer's neighborhood. It tries to fill up
	the Peer's capacity.
	"""
	def __init__(self, peer):
		threading.Thread.__init__(self)
		self.loop = True
		self.peer = peer

	def log(self, *msg):
		print("[%s]" % self.peer.name, *msg)
	
	def stop(self):
		self.loop = False
	
	def check_nbs(self):
		with self.peer.plock:
			for pid in self.peer.nlist:
				self.peer.out.send_msg(dest=pid, msgname='still_my_nb', msgargs=(self.peer.pid, self.peer.name, self.peer.nmax, len(self.peer.nlist)))
	
	def manage(self):
		assert set(self.peer.nlist) <= set(self.peer.plist)
		print(self.peer.name, self.peer.nmax, self.peer.nlist)
		def P_i(nmax, l, nmax_i, refused_i):
			"""
			"probability" (kind of) of the i-th peer to be selected for neighboring
			"""
			return (((nmax-l)/float(nmax)*(nmax_i/float(MAX_NB))) + ((l)/float(nmax)*(1.-(nmax_i/float(MAX_NB))))) / \
					(math.sqrt(refused_i)+1.)
			#		((refused_i)+1.)
			#		(math.log(refused_i+1, 2)+1.)
			#		((refused_i/2.)+1.)
		
		with self.peer.plock:
			if len(self.peer.nlist) >= self.peer.nmax: return # <--- SURE?
			
			for pid, values in sorted(self.peer.plist.items(), key=lambda k_v: -P_i(self.peer.nmax, len(self.peer.nlist), k_v[1][1], k_v[1][5])):
			#for pid, values in sorted(self.peer.plist.items(), key=lambda k_v: -P_i((MAX_NB*len(self.peer.nlist)+1), (sum(self.peer.plist[pid][1] for pid in self.peer.nlist)/(len(self.peer.nlist)+1)), k_v[1][1], k_v[1][5])):
			#for pid, values in sorted(self.peer.plist.items(), key=lambda k_v: -(k_v[1][1]-k_v[1][5])):
				if pid not in peer.nlist:
					self.peer.out.send_msg(dest=pid, msgname='be_my_nb', msgargs=(self.peer.pid, self.peer.name, self.peer.nmax, len(self.peer.nlist)))
					self.peer.nb_asked_pid = pid
					break

	def run(self):
		while self.loop:
			self.check_nbs()
			self.manage()
			time.sleep(0.1 + float(Nlist_Manager_SleepTime)*(len(self.peer.nlist)/float(self.peer.nmax)))
		self.log("Nlist Manager Done!")	

class Peer(object):
	
	def __init__(self, nmax, name, IPaddr, portno):
		assert int(nmax) <= MAX_NB
		self.nmax = int(nmax)
		self.name = 'P' + str(name)
		self.IPaddr = IPaddr
		self.portno = int(portno)
		self.pid = IPaddr + ':' + portno
		self.plist = {}
		self.nlist = {}
		self.msgid = 0			# Id of last message sent by this peer
		self.seen_msgs = set()	# A set of tuples (msgid, source-pid)
		self.plock = threading.RLock()
		
		# Server thread
		self.inp = Server(self)
		self.inp.start()
		
		# Client thread
		self.out = Client(self)
		self.out.start()

		# Still Alive thread
		self.still_alive = Still_alive(self)
		self.still_alive.start()
		
		# Nlist_Manager thread
		self.nlist_manager = Nlist_Manager(self)
		self.nlist_manager.start()
	
	def __update_timer__(self, sourcepid, name, nmax, l):
		with self.plock:
			if sourcepid in self.plist:
				self.plist[sourcepid][3] = datetime.now()
				self.plist[sourcepid][4] = False
			elif sourcepid != self.pid:
				self.plist[sourcepid] = [name, nmax, l, datetime.now(), False, 0]
	
	def __accept_nb__(self, pid):
		with self.plock:
			self.nlist[pid] = True
			self.out.send_msg(dest=pid, msgname='accept_nb', msgargs=(self.pid, self.name, self.nmax, len(self.nlist)))
			self.nb_asked_pid = None # <- Trial
	
	def __reject_nb__(self, pid):
		with self.plock:
			if pid in self.nlist: del self.nlist[pid]
			self.out.send_msg(dest=pid, msgname='reject_nb', msgargs=(self.pid, self.name, self.nmax, len(self.nlist)))
	
	####################################################################
	# Incoming message handlers
	####################################################################
	def ping(self, sourcepid, name, nmax, l, msgid, TTL, senderpid):
		self.__update_timer__(sourcepid, name, nmax, l)
		if (msgid, sourcepid) in self.seen_msgs: return
		self.seen_msgs.add( (msgid, sourcepid) )
		with self.plock:
			TTL -= 1
			if TTL > 0:	# We don't forward the message if TTL = 0
				for p in self.plist.keys():
					# Don't forward back to the sender
					if p == senderpid: continue
					# Forward ping
					self.out.send_msg(dest=p, msgname='ping', msgargs=(sourcepid, name, nmax, l, msgid, TTL, self.pid))
				self.plist[sourcepid] = [name, int(nmax), int(l), datetime.now(), False, 0]
			self.out.send_msg(dest=sourcepid, msgname='pong', msgargs=(self.pid, self.name, self.nmax, len(self.nlist)))
	
	def pong(self, sourcepid, name, nmax, l):
		self.__update_timer__(sourcepid, name, nmax, l)
		with self.plock:
			self.plist[sourcepid] = [name, int(nmax), int(l), datetime.now(), False, 0]

	def send_alive(self, sourcepid, name, nmax, l):
		self.__update_timer__(sourcepid, name, nmax, l)
		self.out.send_msg(dest=sourcepid, msgname='receive_alive', msgargs=(self.pid, self.name, self.nmax, len(self.nlist)))
		
	def receive_alive(self, sourcepid, name, nmax, l):
		self.__update_timer__(sourcepid, name, nmax, l)
	
	def be_my_nb(self, senderpid, sendername, sendernmax, senderl):
		self.__update_timer__(senderpid, sendername, sendernmax, senderl)
		with self.plock:
			H = 0
			if len(self.nlist) < self.nmax:
				# ACCEPT
				self.__accept_nb__(senderpid)
				return
			
			# Consider your neighbours whose nmax is <= the sender's nmax
			subset = [ pid for pid in self.nlist if self.plist[pid][1] <= sendernmax ]
			if len(subset) == 0:
				# REJECT
				self.__reject_nb__(senderpid)
				return
			
			# Candidate Z is the highest degree neighbour from subset
			Z = max(subset, key=lambda pid: self.plist[pid][1])
			
			if sendernmax > max(self.plist[pid][1] for pid in self.nlist) or self.plist[Z][2] > senderl + H:
				# ACCEPT AND DROP Z
				del self.nlist[Z] # <-- Drop Z (no notification sent to Z)
				self.__accept_nb__(senderpid)
			else:
				# REJECT
				self.__reject_nb__(senderpid)
	
	def accept_nb(self, senderpid, name, nmax, l):
		self.__update_timer__(senderpid, name, nmax, l)
		with self.plock:
			if senderpid == self.nb_asked_pid and len(self.nlist) < self.nmax:
			#if len(self.nlist) < self.nmax:
				self.nlist[senderpid] = True
	
	def reject_nb(self, senderpid, name, nmax, l):
		self.__update_timer__(senderpid, name, nmax, l)
		with self.plock:
			self.plist[senderpid][5] = (self.plist[senderpid][5] + 1) % 50
			# Note: "% 50" above is to let reconsider again a peer who rejected us
	
	def still_my_nb(self, senderpid, name, nmax, l):
		self.__update_timer__(senderpid, name, nmax, l)
		with self.plock:
			if senderpid in self.nlist:
				self.out.send_msg(dest=senderpid, msgname='yes_still_my_nb', msgargs=(self.pid, self.name, self.nmax, len(self.nlist)))
			else:
				self.out.send_msg(dest=senderpid, msgname='no_still_my_nb', msgargs=(self.pid, self.name, self.nmax, len(self.nlist)))
	
	def yes_still_my_nb(self, sourcepid, name, nmax, l):
		self.__update_timer__(sourcepid, name, nmax, l)
	
	def no_still_my_nb(self, sourcepid, name, nmax, l):
		self.__update_timer__(sourcepid, name, nmax, l)
		with self.plock:
			if sourcepid in self.nlist:
				del self.nlist[sourcepid]
	
	def get_neighbours(self, senderpid, name, nmax, l):
		self.__update_timer__(senderpid, name, nmax, l)
		"""
		Another peer has asked me my neighbour list.
		"""
		with self.plock:
			self.out.send_msg(
				dest=senderpid,
				msgname='send_neighbours',
				msgargs=(self.pid, self.name, self.nmax, len(self.nlist), [ (p,self.plist[p][0],self.plist[p][1]) for p in self.nlist ])
			)
	
	def send_neighbours(self, senderpid, name, nmax, l, nlist):
		self.__update_timer__(senderpid, name, nmax, l)
		"""
		One of the peers I requested the nlist to has finally replied me back.
		"""
		with self.plock:
			assert len(self.nlist_answers) < self.nlist_waited_answers
			self.nlist_answers.append( (senderpid,name,nmax,nlist) )
			if len(self.nlist_answers) == self.nlist_waited_answers:
				nlist_dot_graph(self.nlist_answers)
	
	def stop(self):
		self.inp.stop()
		self.still_alive.stop()
		self.nlist_manager.stop()


class SuperPeer(Peer):
	def __init__(self, nmax, IPaddr, portno):
		super(SuperPeer, self).__init__(nmax, -1, IPaddr, portno)





if __name__=='__main__':
	print("Starting...")
	
	global MAX_NB
	MAX_NB = int(sys.argv[1])
	
	commands = {
		# cmd name : 	[ cmd_handler, (arg_tuple,), 'Description' ]
		'superinit':	[ superinit, (), 'Initialize the super peer. Must be called only once!' ],
		'init':			[ init, (), 'Initialize a peer (not the super peer). Must be called only once!' ],
		'whoami':		[ whoami, (), 'Prints the peer''s identity.' ],
		'seen':			[ seenmsgs, (), 'Prints the messages seen by this peer.' ],
		'wait':			[ wait, (), 'It blocks the shell. You''ll need to kill the peer to exit.' ],
		'stop':			[ stop, (), 'Stops all the peer activities and exits the shell.' ],
		
		'hello':		[ hello, (), 'Enters an existing network, via a known peer.' ],
		'plist':		[ plist, (), 'Prints the list of know peers.' ],
		'nlist':		[ nlist, (), 'Prints the list of neighbours of the given peers.' ],
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
	if len(sys.argv) > 2:
		try:
			c = tuple(sys.argv[2:])
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
