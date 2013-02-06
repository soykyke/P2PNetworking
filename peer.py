#!/usr/bin/python2.7
# -*-coding:Utf-8 -*
import sys, traceback
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from PyQt4 import QtCore, QtGui
import threading 


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
	print 'hello'
	print peer.pid, peer.name, peer.msgid, TTL
	print 'adding', pid ,'on seen_msgs'
	peer.seen_msgs.add( (peer.msgid, peer.pid) )
	print 'seen_msgs', peer.seen_msgs
	#print "methods: ", s.system.listMethods()
	#t = threading.Thread(target=s.ping, args=(peer.pid, peer.name, peer.msgid, TTL, peer.pid, ))  
	#print 'staring thread...'
	#t.start()  
	#send_message(pid, peer.pid, peer.name, peer.msgid, TTL, peer.pid) 
	#s.ping(peer.pid, peer.name, peer.msgid, TTL, peer.pid)
	print 'starting pingmessage to', pid, 'with', peer.pid, peer.name, peer.msgid, TTL, peer.pid
	m = PingMessage(pid, peer.pid, peer.name, peer.msgid, TTL, peer.pid)
	m.start()
	peer.msgid += 1
	print 'bye hello'

class PingMessage(threading.Thread):
	def __init__(self, to, pid, name, msgid, TTL, lastPeer):
		threading.Thread.__init__(self)
		self.s = xmlrpclib.ServerProxy('http://' + to)
		self.pid= pid
		self.name = name
		self.msgid = msgid
		self.TTL = TTL
		self.lastPeer = lastPeer
	
	def run(self):
		print 'Im in run ping message'
		print 'pid', self.pid, 'name', self.name, 'msgid', self.msgid, 'TTL', self.TTL, 'lastPeer', self.lastPeer
		self.s.ping(self.pid, self.name, self.msgid, self.TTL, self.lastPeer)
	


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/', '/RPC2')

class Peer(QtCore.QThread, object):
	
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
		print "run server"
		print 'IPaddr', self.IPaddr, 'portno', self.portno
		self.server = SimpleXMLRPCServer((self.IPaddr, self.portno),requestHandler=RequestHandler, allow_none=True)
		self.server.register_instance(self)
		self.server.serve_forever()
		print "SERVER DONE"

	
	def ping(self, pid, name, msgid, TTL, lastPeer):
		print "ping"
		TTL -= 1
		if (msgid, pid) in self.seen_msgs: return
		if TTL > 0:
			print 'adding', pid ,'on seen_msgs'
			self.seen_msgs.add( (msgid, pid) )
			print 'seen_msgs', self.seen_msgs
			for p,n in self.plist:
				print p, lastPeer
				if p == lastPeer: continue
				print 'doing pings to my list', p,n
				print 'starting pingmessage to', p, 'with', pid, name, msgid, TTL, self.pid
				m = PingMessage(p, pid, name, msgid, TTL, self.pid)
				m.start()  
		
		print 'adding to my plist'		
		self.plist.add( (pid, name) )
		print 'plist', self.plist
		print 'call to pong', pid
		s = xmlrpclib.ServerProxy('http://' + pid)
		s.pong(self.pid, self.name)
		print 'bye ping'
		return True
	
	def pong(self, pid, name):
		print 'pong'
		print 'pid', pid, 'name', name
		print 'adding to plist...'
		self.plist.add( (pid, name) )
		print 'plist', self.plist
		print 'bye pong'
		return True

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
