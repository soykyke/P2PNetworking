#!/usr/bin/python2.7
# -*-coding:Utf-8 -*

#we import the correct library (enables communication between peers)
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

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
		
peer=Peer()
#peer.serve_forever()
print("\n"+peer.name)
nextPeer=Peer()
print(nextPeer.name)
