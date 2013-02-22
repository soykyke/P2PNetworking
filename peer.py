# -*-coding:Utf-8 -*
import sys, traceback, time
import xmlrpc
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import threading
from queue import Queue
import pydot

TTL = 2


########################################################################
# COMMAND HANDLERS
########################################################################
# Note: They all assume either "init" or "superinit" is called first,
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
	peer_names = list(peers) if peers else None
	if not peer_names:
		nlist_dot_graph([ (peer.pid, peer.name, peer.nmax, [ (p,n,m) for p,n,m in peer.nlist ]) ])
	else:
		peer.nlist_waited_answers = 0
		peer.nlist_answers = []
		
		# Send request message to every peer in my neighbour list
		# First, find the correct peer by its name
		for name in peer_names:
			if name == peer.name:
				# Send request message to myself (trick to have my neighbours too)
				peer.out.send_msg(dest=peer.pid, msgname='get_neighbours', msgargs=(peer.pid,))
				peer.nlist_waited_answers += 1
				continue
			
			for p,n,m in peer.plist:
				if n==name:
					peer.out.send_msg(dest=p, msgname='get_neighbours', msgargs=(peer.pid,))
					peer.nlist_waited_answers += 1
					break
			else:
				pass # The requested peer name does not exist!

def plist():
	print("Peer max neighbour capacity:", peer.nmax)
	print("Peer list size:", len(peer.plist))
	print('{:4} {:6} {:20} {:3}'.format('', 'name', 'address', 'nmax'))
	for i,(pid,name,nmax) in enumerate(sorted(peer.plist, key=lambda x_y: int(x_y[1][1:]))):
		print('{:3}) {:6} {:20} {:3}'.format(i+1, name, pid, nmax))

def hello(pid):
	peer.seen_msgs.add( (peer.msgid, peer.pid) )
	peer.out.send_msg(dest=pid, msgname='ping', msgargs=(peer.pid, peer.name, peer.nmax, peer.msgid, TTL, peer.pid))
	peer.msgid += 1
########################################################################


def nlist_dot_graph(nlist_answers):
	"""
	Prints the dot graph out of the nlist_answers
	"""
	print(nlist_answers)
	graph = pydot.Dot("nlist", graph_type='graph')
	
	added_nodes = set()
	added_edges = set()
	for pid, name, nmax, nlist in nlist_answers:
		graph.add_node(pydot.Node('%s(%d)'%(name,nmax)))
		added_nodes.add(pid)
		for p,n,m in nlist:
			if (pid,p) not in added_edges and (p,pid) not in added_edges:
				graph.add_node(pydot.Node('%s(%d)'%(n,m)))
				graph.add_edge(pydot.Edge('%s(%d)'%(name,nmax), '%s(%d)'%(n,m)))
				added_nodes.add(p)
				added_edges.add( (pid,p) )
	
	graph.write('nlist.dot')
	graph.write_png('nlist.png', prog='fdp')



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
			dest, msgname, msgargs = self.msgQ.get() # Blocking read
			s = xmlrpc.client.ServerProxy('http://' + dest)
			getattr(s, msgname)(*msgargs)
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


class Peer(object):
	
	def __init__(self, nmax, name, IPaddr, portno):
		self.nmax = int(nmax)
		self.name = 'P' + str(name)
		self.IPaddr = IPaddr
		self.portno = int(portno)
		self.pid = IPaddr + ':' + portno
		self.plist = set()		# A set of tuples (pid, name, nmax)
		self.nlist = self.plist		# A set of tuples (pid, name, nmax)	# <---- CHANGE HERE LATER
		self.msgid = 0			# Id of last message sent by this peer
		self.seen_msgs = set()	# A set of tuples (msgid, source-pid)
		
		# Server thread
		self.inp = Server(self)
		self.inp.start()
		
		# Client thread
		self.out = Client(self)
		self.out.start()
	
	####################################################################
	# Incoming message handlers
	####################################################################
	def ping(self, sourcepid, name, nmax, msgid, TTL, senderpid):
		if (msgid, sourcepid) in self.seen_msgs: return
		self.seen_msgs.add( (msgid, sourcepid) )
		TTL -= 1
		if TTL > 0:	# We don't forward the message if TTL = 0
			for p,n,m in self.plist:
				# Don't forward back to the sender
				if p == senderpid: continue
				# Forward ping
				self.out.send_msg(dest=p, msgname='ping', msgargs=(sourcepid, name, nmax, msgid, TTL, self.pid))
		self.plist.add( (sourcepid, name, nmax) )
		self.out.send_msg(dest=sourcepid, msgname='pong', msgargs=(self.pid, self.name, self.nmax))
	
	def pong(self, pid, name, nmax):
		self.plist.add( (pid, name, nmax) )
	
	def get_neighbours(self, senderpid):
		"""
		Another peer has asked me my neighbour list.
		"""
		self.out.send_msg(
			dest=senderpid,
			msgname='send_neighbours',
			msgargs=(self.pid, self.name, self.nmax, [ (p,name,nmax) for p,name,nmax in self.nlist ])
		)
	
	def send_neighbours(self, pid, name, nmax, nlist):
		"""
		One of the peers I requested the nlist to has finally replied me back.
		"""
		assert len(self.nlist_answers) < self.nlist_waited_answers
		self.nlist_answers.append( (pid,name,nmax,nlist) )
		if len(self.nlist_answers) == self.nlist_waited_answers:
			nlist_dot_graph(self.nlist_answers)
	
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
		'nlist':		[ nlist, (), 'Prints the list of neighbours of the given peers' ],
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
