#!/usr/bin/python2.7
# -*-coding:Utf-8 -*
import sys, traceback
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

def sum_handler(a,b):
	b = int(b)
	print a+b

def prod_handler(a,b):
	b = int(b)
	print a*b


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

class Peer(SimpleXMLRPCServer):
	#inherits of a SimpleXMLRPCServer (this way, one IP adress is allocated to the Peer)
	#Peer Class
		#Attributes:
			#name (short, unique name)
			#adress (IP adress+port)
			#neighbouringCapacity (max number of neighbours)
			#knownPeersList
			
	peersCounter = 0 #usage of a counter to name the peer
	portCounter = 8000
	
	def __init__(self,neighbouringCapacity=10):
		#Class constructor
		
		#########################################################################################################
		#self=SimpleXMLRPCServer(self,("localhost", 8000),requestHandler=RequestHandler)
		#########################################################################################################
		#super(Peer).__init__(self,("localhost", 8000),requestHandler=RequestHandler)
		SimpleXMLRPCServer.__init__(self,("localhost", Peer.portCounter),requestHandler=RequestHandler)
		
		if Peer.peersCounter==0:
			self.name="InitialSeed"
		else:	
			self.name="P"+str(Peer.peersCounter)
		
		self.neighbouringCapacity=neighbouringCapacity
		self.knownPeersList=list()
		self.adress="localhost:8000"
		
		#Peer.peersCounter=peersCounter+1
		Peer.peersCounter+=1
		Peer.portCounter+=1




if __name__=='__main__':

	print "Starting..."
	
	commands = {
		# cmd name : [ cmd_handler, arg_tuple, 'Description' ]
		'sum':			[ sum_handler, (100,), 'Sums 100 to whatever interger you pass to it' ],
		'prod':			[ prod_handler, (100,), 'Sums 100 to whatever interger you pass to it' ],
	}
	
	def usage():
		print '='*23 + ':'
		print 'Usage\n' + '='*23 + ':'
		for c,specs in sorted(commands.iteritems(), key=lambda (k,v): k):
			print '{:23}: {}'.format(c, specs[2])
		print '='*23 + ':'
	
	def execute_command(c):
		if c[0] in commands:
			commands[c[0]][0](*(commands[c[0]][1] + c[1:]))
		else:
			print 'Error: command "%s" not found.' % c
	
	# If arguments are passed to command line, execute right away
	if len(sys.argv) > 1:
		try:
			c = " ".join(sys.argv[1:])
			execute_command(c)
		except Exception as e:
			print 'Error:', e
			traceback.print_exc()
	
	else:
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
