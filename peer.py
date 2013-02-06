#!/usr/bin/python2.7
# -*-coding:Utf-8 -*
import sys, traceback
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from PyQt4 import QtCore, QtGui


TTL = 50


def sum_handler(a,b):
	a = int(a)
	b = int(b)
	print a+b

def prod_handler(a,b):
	b = int(b)
	print a*b

def init(neighbouringCapacity, pid, IPaddr, portno):
	global peer
	peer = Peer(neighbouringCapacity, pid, IPaddr, portno)
	peer.start()

def superinit(neighbouringCapacity, IPaddr, portno):
	global peer
	peer = SuperPeer(neighbouringCapacity, IPaddr, portno)
	peer.start()

def whoami():
	print "name:", peer.name, "pid:", peer.pid

def plist():
	print peer.neighbouringCapacity
	print peer.plist

def hello(pid):
	print peer.pid, peer.name, peer.msgid, TTL
	s = xmlrpclib.ServerProxy('http://' + pid)
	#print "methods: ", s.system.listMethods()
	s.ping(peer.pid, peer.name, peer.msgid, TTL)
	peer.msgid += 1
	print 'bye hello'




# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/', '/RPC2')

class Peer(QtCore.QThread, object):
	#inherits of a SimpleXMLRPCServer (this way, one IP adress is allocated to the Peer)
	#Peer Class
		#Attributes:
			#name (short, unique name)
			#adress (IP adress+port)
			#neighbouringCapacity (max number of neighbours)
			#knownPeersList
			
	#peersCounter = 0 #usage of a counter to name the peer
	#portCounter = 8000
	
	def __init__(self, neighbouringCapacity, name, IPaddr, portno):
		#Class constructor
		QtCore.QThread.__init__(self)
		
		self.neighbouringCapacity = neighbouringCapacity
		self.name = "P"+str(name)
		self.IPaddr = IPaddr
		self.portno = int(portno)
		self.pid = IPaddr + ':' + portno
		self.plist = set()		# A set of tuples (pid, name)
		self.msgid = 0
		self.seen_msgs = set()	# A set of tuples (msgid, source-pid)
	
	def run(self):
		print "run"
		self.server = SimpleXMLRPCServer((self.IPaddr, self.portno), requestHandler=RequestHandler)
		#########################################################################################################
		#self=SimpleXMLRPCServer(self,("localhost", 8000),requestHandler=RequestHandler)
		#########################################################################################################
		#super(Peer, self).__init__(()
		#SimpleXMLRPCServer.__init__(self,(self.IPaddr, self.portno), requestHandler=RequestHandler)
		
		#print Peer.ping
		#self.register_introspection_functions()
		self.server.register_instance(self)
		self.server.serve_forever()
		print "SERVER DONE"
		#self.register_function(Peer.ping)
		#self.register_function(Peer.pong)
		
		
		#if Peer.peersCounter==0:
		#	self.name="InitialSeed"
		#else:	
		#	self.name="P"+str(Peer.peersCounter)
		
		#self.neighbouringCapacity=neighbouringCapacity
		#self.knownPeersList=list()
		#self.adress="localhost:8000"
		
		#Peer.peersCounter=peersCounter+1
		#Peer.peersCounter+=1
		#Peer.portCounter+=1
	
	def ping(self, pid, name, msgid, TTL):
		print "ping"
		TTL -= 1
		if (msgid, pid) in self.seen_msgs: return
		if TTL > 0:
			self.seen_msgs.add( (msgid, pid) )
			for p,n in self.plist:
				s = xmlrpclib.ServerProxy('http://' + p)
				s.ping(pid, msgid, TTL)
		self.plist.add( (pid, name) )
		s = xmlrpclib.ServerProxy('http://' + pid)
		s.pong(self.pid, self.name)
	
	def pong(self, pid, name):
		self.plist.add( (pid, name) )

class SuperPeer(Peer):
	def __init__(self, neighbouringCapacity, IPaddr, portno):
		super(SuperPeer, self).__init__(neighbouringCapacity, 0, IPaddr, portno)



if __name__=='__main__':

	print "Starting..."
	
	commands = {
		# cmd name : [ cmd_handler, arg_tuple, 'Description' ]
		'superinit':	[ superinit, (), '' ],
		'init':			[ init, (), '' ],
		'whoami':		[ whoami, (), '' ],
		'plist':		[ plist, (), '' ],
		'hello':		[ hello, (), '' ],
		'sum':			[ sum_handler, (), 'Sums 100 to whatever interger you pass to it' ],
		'prod':			[ prod_handler, (100,), 'Sums 100 to whatever interger you pass to it' ],
	}
	
	def usage():
		print '='*23 + ':'
		print 'Usage\n' + '='*23 + ':'
		for c,specs in sorted(commands.iteritems(), key=lambda (k,v): k):
			print '{:23}: {}'.format(c, specs[2])
		print '='*23 + ':'
	
	def execute_command(c):
		#print c
		if c[0] in commands:
			commands[c[0]][0](*(commands[c[0]][1] + c[1:]))
		else:
			print 'Error: command "%s" not found.' % c
	
	# If arguments are passed to command line, execute right away
	if len(sys.argv) > 1:
		try:
			c = tuple(sys.argv[1:])
			execute_command(c)
		except Exception as e:
			print 'Error:', e
			traceback.print_exc()
	
	#else:
	# Read command input
	while True:
		try:
			c = tuple(raw_input('PEER >> ').split())
			if c[0] == 'exit': break
			elif c[0] == '': continue
			elif c[0] == 'help' or c[0] == 'usage' or c[0] == '?':
				usage()
				continue
			execute_command(c)
		except EOFError:
			break
		except Exception as e:
			print 'Error:', e
			traceback.print_exc()
			continue


	print "Exiting..."
