import sys, traceback, time

import xmlrpc
import socket
import pydot
import math
import random
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
from subprocess import check_output
import threading
from queue import Queue
from datetime import datetime, timedelta

DEFAULT_TTL = 4
DEFAULT_K = 3
TimeOutAlive = timedelta(seconds = 5)
TimeToDiscoveryMissingPeers =  2
Nlist_Manager_SleepTime = 5

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
					peer.out.send_msg(dest=peer.pid, msgname='get_neighbours', msgargs=())
					peer.nlist_waited_answers += 1
					continue
				
				for p,(n,m,l,d,s,r) in peer.plist.items():
					if n==name:
						peer.out.send_msg(dest=p, msgname='get_neighbours', msgargs=())
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

def hello(pid, TTL=DEFAULT_TTL):
	peer.seen_msgs.add( (peer.msgid, peer.pid) )
	peer.out.send_msg(dest=pid, msgname='ping', msgargs=(peer.pid, peer.name, peer.nmax, len(peer.nlist), peer.msgid, TTL))
	peer.msgid += 1
	
def find(lookingfor, TTL=DEFAULT_TTL):
	TTL = int(TTL)
	peer.seen_msgs.add( (peer.msgid, peer.pid) )
	# If I have the item? 
	if lookingfor == peer.name:
		print ("I already have the item!!!")
		return
	# See first if one of my neighbour have the item
	if peer.nlist:
		with peer.plock:
			for pid in peer.nlist:
				if (peer.plist[pid][0] == lookingfor) :
					print ('Your neighbour %s has what you are looking for' % (pid))
					peer.founditems[lookingfor] = pid
					break
			else:
			
				path = []
				path.append(peer.name)
				for pid in peer.nlist.keys():
					print ("Sending find message to", pid, "looking for", lookingfor)
					# Increasing the number of sent messages
					with peer.plock:
						peer.num_msg_find_outgoing += 1
						### TODO: The following line must be adjusted
						peer.bytescount_outgoing += sys.getsizeof(peer.pid) + sys.getsizeof(peer.name) + sys.getsizeof(peer.nmax) + sys.getsizeof(len(peer.nlist)) + sys.getsizeof(peer.msgid)+ sys.getsizeof(TTL) + sys.getsizeof(1)+ sys.getsizeof(peer.pid) + sys.getsizeof(lookingfor)
					peer.out.send_msg(dest=pid, msgname='find', msgargs=(peer.pid, peer.name, peer.nmax, len(peer.nlist), peer.msgid, TTL, 1, lookingfor, path))
				peer.msgid += 1
	else:
		print ("Don't have neighbours :(")
		
def get(lookingfor):
	if lookingfor == peer.name:
		print ("I already have the item!!!")
		return
	if lookingfor in peer.founditems:
		print ("Sending to %s" % (peer.founditems[lookingfor]))
		peer.out.send_msg(dest=peer.founditems[lookingfor], msgname='get', msgargs=(lookingfor,))
	else:
		print ("We dont know who have the item", lookingfor, "so you have to find it before get it, using find command.")
		
def kfind(lookingfor, TTL=DEFAULT_TTL, K=DEFAULT_K):
	TTL = int(TTL)
	K = int(K)
	peer.seen_msgs.add( (peer.msgid, peer.pid) )
	# If I have the item? 
	if lookingfor == peer.name:
		print ("I already have the item!!!")
		return
	# See first if one of my neighbour have the item
	if peer.nlist:
		with peer.plock:
			for pid in peer.nlist:
				if (peer.plist[pid][0] == lookingfor) :
					print ('Your neighbour %s has what you are looking for' % (pid))
					peer.founditems[lookingfor] = pid
					break
					
			else:
				
				path = []
				path.append(peer.name)

				with peer.plock:
					print ("Im creating", K, "zombies")
					for idwalker in range(1, K+1):
						print ("Zombie", idwalker)
						peer.num_msg_find_outgoing += 1
						peer.bytescount_outgoing += sys.getsizeof(peer.pid) + sys.getsizeof(peer.name) + sys.getsizeof(peer.nmax) + sys.getsizeof(len(peer.nlist)) + sys.getsizeof(peer.msgid)+ sys.getsizeof(TTL) + sys.getsizeof(1)+ sys.getsizeof(peer.pid) + sys.getsizeof(lookingfor)
						
						print ("I am adding the missing elements of klist regarding the active neighbours on nlist")						
						
						for pid in peer.nlist:
							print ("I'm treating with the neighbour",pid)
							
							if ((pid, lookingfor)) in peer.klist.keys():
								print ("I have this item:", (pid, lookingfor), "with value", peer.klist[(pid, lookingfor)], "on klist")
										
							else:
								peer.klist[(pid, lookingfor)] = 0
								print ("I dont have this item:", (pid, lookingfor), "on klist so im adding with value", peer.klist[(pid, lookingfor)])
								
						print ("klist",peer.klist)
						
						print ("Now I'm choosing only items that have looked for", lookingfor)
						candidates = {}
						for (pid,k),numbers in peer.klist.items():
							if lookingfor == k:
								candidates[pid] = numbers
						print ("Candidates to send the k-Walker")
						print (candidates)
						
						p = min(candidates, key=candidates.get)
						
						# POSSIBLE IMPROVEMENT: IF WE HAVE MORE THAN 1 MIN PID, DISCARD THE LAST SENDER (IF IT IS INSIDE)
						
						peer.klist[(p, lookingfor)] += 1
						print ("I have choose", p, "to send the kwalker. So, I added 1 to its number of sent msgs:", peer.klist[(p, lookingfor)])
						
						print ("I am sending a random k-walker to", p)

						peer.out.send_msg(dest=p, msgname='kfind', msgargs=(peer.pid, peer.name, peer.nmax, len(peer.nlist), peer.msgid, TTL, 1, lookingfor, idwalker, 1, path))
	

				print ("Im exiting of kfind")
	else:
		print ("Don't have neighbours :(")
	
	
		
def report():
	print ("--- Incoming ---")
	print ("Incoming messages:", peer.num_msg_find_incoming)
	print ("Bytes incoming to this Peer:",peer.bytescount_incoming)
	print ("--- Outgoing ---")
	print ("Outgoing messages:", peer.num_msg_find_outgoing)
	print ("Bytes outgoing from this Peer:",peer.bytescount_outgoing)
	print ("--- Total ---")
	print ("Incoming and outgoing messages:", peer.num_msg_find_incoming + peer.num_msg_find_outgoing)
	print ("Bytes transferred through this Peer:",peer.bytescount_incoming + peer.bytescount_outgoing)

def totreport(*peers):
	with peer.plock:
		peer.totreport_waited_answers = 0
		peer.totreport_answers = []
		peer_names = list(peers) if peers else [ p[0] for p in peer.plist.values() ] + [ peer.name ]
		for name in peer_names:
			if name == peer.name:
				# Send request message to myself (trick to have my neighbours too)
				peer.out.send_msg(dest=peer.pid, msgname='get_report', msgargs=())
				peer.totreport_waited_answers += 1
				continue
			
			for p,(n,m,l,d,s,r) in peer.plist.items():
				if n==name:
					peer.out.send_msg(dest=p, msgname='get_report', msgargs=())
					peer.totreport_waited_answers += 1
					break
			else:
				pass # The requested peer name does not exist!

def restart_report():
	print ("Restarting measurements of report...")
	with peer.lock_num_msg_find_incoming:
		peer.num_msg_find_incoming = 0
		peer.bytescount_incoming  = 0
		print ("Incoming measurements restarted")
	with peer.plock:
		peer.num_msg_find_outgoing = 0
		peer.bytescount_outgoing  = 0
		print ("Outgoing measurements restarted")
########################################################################


def total_report(answers):
	tot_nmsgs_in = 0
	tot_nmsgs_out = 0
	tot_bytes_in = 0
	tot_bytes_out = 0
	for pid, name, nmax, nmsgs_in, nmsgs_out, nbytes_in, nbytes_out in answers:
		tot_nmsgs_in += nmsgs_in
		tot_nmsgs_out += nmsgs_out
		tot_bytes_in += nbytes_in
		tot_bytes_out += nbytes_out
	print ("TOTAL REPORT:\ntot_nmsgs_in=%d\ntot_nmsgs_out=%d\ntot_bytes_in=%d\ntot_bytes_out=%d\n" % (tot_nmsgs_in,tot_nmsgs_out,tot_bytes_in,tot_bytes_out))

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
		graph.add_node(pydot.Node('%s(%d)'%(name,nmax), encode='utf-8', style='filled', fillcolor='0.000 0.000 %.3f'%(1.-((nmax-3.)/float(MAX_NB))), fontcolor='white' if (nmax)/float(MAX_NB) >= 0.8 else 'black'))
	for ((p1,n1,m1),(p2,n2,m2)) in edges:
		if ((p2,n2,m2),(p1,n1,m1)) in edges and not ((p2,n2,m2),(p1,n1,m1)) in printed_edges and not ((p1,n1,m1),(p2,n2,m2)) in printed_edges:
			graph.add_edge(pydot.Edge('%s(%d)'%(n1,m1), '%s(%d)'%(n2,m2)))
			printed_edges.add( ((p1,n1,m1),(p2,n2,m2)) )
			printed_edges.add( ((p2,n2,m2),(p1,n1,m1)) )
	
	#graph.write('nlistEnrique.dot')
	graph.write('nlist.dot')
	png_data = check_output([ 'dot', '-Tpng', 'nlist.dot' ], shell=False)
	png_file = open('nlist.png', 'wb')
	png_file.write(png_data)
	png_file.close()
	#graph.write_png('nlist.png', prog='dot')
	#graph.write_pdf('nlist.pdf', prog='dot')
	#graph.write_jpg('nlist.jpg', prog='dot')
	#graph.write_png("name", prog='dot')






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
	
	def send_msg(self, dest, msgname, msgargs, track=False):
		self.msgQ.put( (dest, msgname, msgargs) )
		if track:
			with self.peer.plock:
				self.peer.num_msg_find_outgoing += 1
				self.peer.bytescount_outgoing += sys.getsizeof(msgargs)   # <--- TODO: avoid the path
	
	def stop(self):
		self.msgQ.put( (self.peer.pid, 'stop', ()) )
	
	def run(self):
		while True:
			dest, msgname, msgargs = self.msgQ.get() # Read from msgQ is blocking
			s = xmlrpc.client.ServerProxy('http://' + dest)
			try:
				getattr(s, msgname).__call__(self.peer.pid, self.peer.name, self.peer.nmax, len(self.peer.nlist), *msgargs)
			except socket.error:
				print ("ERROR CONNECTION REFUSED")
				self.peer.__remove_peer__(dest)
				#~ with self.peer.plock:
					#~ if dest in self.peer.plist:
						#~ del self.peer.plist[dest]
					#~ if dest in self.peer.nlist:
						#~ del self.peer.nlist[dest]
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
			self.server = SimpleXMLRPCServer((peer.IPaddr, peer.portno), allow_none=True, logRequests = False) # we change this for not show unnecessary messages
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
	
	#~ def check_nbs(self):
		#~ with self.peer.plock:
			#~ for pid in self.peer.nlist:
				#~ self.peer.out.send_msg(dest=pid, msgname='still_my_nb', msgargs=(self.peer.pid, self.peer.name, self.peer.nmax, len(self.peer.nlist)))
	
	def check_unlistened_peers(self):
		with self.peer.plock:
			for pid, value in self.peer.plist.copy().items():
				if (value[4] == True):
					self.peer.__remove_peer__(pid)
					#del self.peer.plist[pid] 
					#if pid in self.peer.nlist:
					#	del self.peer.nlist[pid]
				elif (datetime.now() > TimeOutAlive + value[3]):
					self.peer.out.send_msg(dest=pid, msgname='send_alive', msgargs=())
					self.peer.plist[pid][4] = True

	def run(self):
		while self.loop:
			#self.check_nbs()
			self.check_unlistened_peers()
			time.sleep(TimeToDiscoveryMissingPeers)
		self.log("Still Alive Done!")


def PEER_SCORE(nmax, l, nmax_i):
	"""
	"Probability" (kind of) of the i-th peer to be selected for neighboring.
	It's a number between 0 and 1 (inclusive).
	"""
	return (((nmax-l)/float(nmax)*(nmax_i/float(MAX_NB))) + ((l)/float(nmax)*(1.-(nmax_i/float(MAX_NB)))))
	#		(math.sqrt(refused_i)+1.)
	#		((refused_i)+1.)
	#		(math.log(refused_i+1, 2)+1.)
	#		((refused_i/2.)+1.)

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
				self.peer.out.send_msg(dest=pid, msgname='still_my_nb', msgargs=())
	
	def manage(self):
		assert set(self.peer.nlist) <= set(self.peer.plist)
		#print(self.peer.name, self.peer.nmax, self.peer.nlist)
		
		with self.peer.plock:
			if len(self.peer.nlist) >= self.peer.nmax: return # <--- SURE?
			
			for pid, values in sorted(self.peer.plist.items(), key=lambda k_v: -PEER_SCORE(self.peer.nmax, len(self.peer.nlist), k_v[1][1])/(math.sqrt(k_v[1][5])+1.)):
			#for pid, values in sorted(self.peer.plist.items(), key=lambda k_v: -P_i((MAX_NB*len(self.peer.nlist)+1), (sum(self.peer.plist[pid][1] for pid in self.peer.nlist)/(len(self.peer.nlist)+1)), k_v[1][1], k_v[1][5])):
			#for pid, values in sorted(self.peer.plist.items(), key=lambda k_v: -(k_v[1][1]-k_v[1][5])):
				if pid not in self.peer.nlist:
					self.peer.out.send_msg(dest=pid, msgname='be_my_nb', msgargs=())
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
		self.klist = {}			# Dictionary for maintain state for kwalkers
		self.founditems = {} 	# Dictionary for found items
		self.msgid = 0			# Id of last message sent by this peer
		self.seen_msgs = set()	# A set of tuples (msgid, source-pid)
		self.plock = threading.RLock()
		#self.plock = threading.RLock()
		#self.plock = threading.RLock()
		self.num_msg_find_incoming = 0
		self.num_msg_find_outgoing = 0
		self.bytescount_incoming = 0
		self.bytescount_outgoing = 0
		
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
			self.out.send_msg(dest=pid, msgname='accept_nb', msgargs=())
			self.nb_asked_pid = None # <- Trial
	
	def __reject_nb__(self, pid):
		with self.plock:
			if pid in self.nlist:
				del self.nlist[pid]
			self.out.send_msg(dest=pid, msgname='reject_nb', msgargs=())
	
	def __remove_peer__(self, pid):
		"""
		Removes the peer 'pid' both from plist and nlist. Useful, for istance,
		when the peer 'pid' is down or unresponsive for a long time.
		"""
		with self.plock:
			if pid in self.plist:
				del self.plist[pid]
			if pid in self.nlist:
				del self.nlist[pid]
			for msgid, p in self.seen_msgs.copy():
				if p == pid:
					self.seen_msgs -= set([ (msgid, p) ])
	
	####################################################################
	# Incoming message handlers
	####################################################################
	def ping(self, senderpid, sendername, sendernmax, senderl, sourcepid, sourcename, sourcenmax, sourcel, msgid, TTL):
		self.__update_timer__(senderpid, sendername, sendernmax, senderl) # *1 We update here
		#self.__update_timer__(sourcepid, name, nmax, l) # *1 We update here
		# Maybe we have to update here also the senderpid?
		if (msgid, sourcepid) in self.seen_msgs: return
		self.seen_msgs.add( (msgid, sourcepid) )
		# Little modification to optimize the code
		TTL -= 1
		if TTL > 0:	# We don't forward the message if TTL = 0
			with self.plock:
				for p in self.plist.keys():
					# Don't forward back to the sender
					if p == senderpid: continue
					# Forward ping
					self.out.send_msg(dest=p, msgname='ping', msgargs=(sourcepid, sourcename, sourcenmax, sourcel, msgid, TTL))
		self.out.send_msg(dest=sourcepid, msgname='pong', msgargs=())
		
		# Something strange this maybe :S
		#with self.plock:
		#	TTL -= 1
		#	if TTL > 0:	# We don't forward the message if TTL = 0
		#		for p in self.plist.keys():
		#			# Don't forward back to the sender
		#			if p == senderpid: continue
		#			# Forward ping
		#			self.out.send_msg(dest=p, msgname='ping', msgargs=(sourcepid, name, nmax, l, msgid, TTL, self.pid))
		#	self.out.send_msg(dest=sourcepid, msgname='pong', msgargs=(self.pid, self.name, self.nmax, len(self.nlist)))
	
	def pong(self, sourcepid, name, nmax, l):
		self.__update_timer__(sourcepid, name, nmax, l)
	
	
	def find(self, senderpid, sendername, sendernmax, senderl, sourcepid, sourcename, sourcenmax, sourcel, msgid, TTL, count_this_msg, lookingfor, path = []):
		self.__update_timer__(senderpid, sendername, sendernmax, senderl)
		msg_size_bytes = sum([ sys.getsizeof(x) for x in [ e[1] for e in locals().items() if e[0] != 'path' ] ])
		
		# Increasing the number of received messages and the counting of incoming total bytes
		with self.plock:
			self.num_msg_find_incoming += 1
			self.bytescount_incoming += msg_size_bytes
			#self.bytescount_incoming += sys.getsizeof(sourcepid) + sys.getsizeof(name) + sys.getsizeof(nmax) + sys.getsizeof(l) + sys.getsizeof(msgid)+ sys.getsizeof(TTL) + sys.getsizeof(count_this_msg)+ sys.getsizeof(senderpid) + sys.getsizeof(lookingfor)
		print ("Im in find function looking for", lookingfor)
		
		#self.__update_timer__(sourcepid, name, nmax, l)
		
		print ("MSGID,SOURCEIP",(msgid, sourcepid))
		if ((msgid, sourcepid) in self.seen_msgs):
			print ("I already saw this message, so I do nothing more here")
		else:
			print ("I didn´t see this message before so lets do something with it")
			
		if (msgid, sourcepid) in self.seen_msgs: return
		self.seen_msgs.add( (msgid, sourcepid) )
		
		path.append(self.name)
		
		print ("Im looking if I have the file that", sourcename, "is looking for")
		TTL -= 1
		if (lookingfor == self.name):
			print ("##I have the file so Im sending a response to", sourcename)
			self.out.send_msg(dest=sourcepid, msgname='found', msgargs=(count_this_msg, path), track=True)
			
			# Increasing the number of sent messages
			#with self.plock:
			#	self.num_msg_find_outgoing += 1
				#self.bytescount_incoming += msg_size_bytes
				#self.bytescount_outgoing += sys.getsizeof(self.pid) + sys.getsizeof(self.name) + sys.getsizeof(self.nmax) + sys.getsizeof(len(self.nlist)) + sys.getsizeof(count_this_msg)
		elif TTL > 0:	# We don't forward the message if TTL = 0
			print ("I don't have the file, so im going to send the search through all my neigbours")
			for pid in self.nlist:
				if (self.plist[pid][0] == lookingfor):
					print ("One of my neighbours have the file! I only forward the find message to him")
					self.out.send_msg(dest=pid, msgname='find', msgargs=(sourcepid, sourcename, sourcenmax, sourcel, msgid, TTL, count_this_msg+1, lookingfor, path), track=True)
					# Increasing the number of sent messages
					#with self.plock:
						#self.bytescount_outgoing += sys.getsizeof(sourcepid) + sys.getsizeof(name) + sys.getsizeof(nmax) + sys.getsizeof(l) + sys.getsizeof(msgid)+ sys.getsizeof(TTL) + sys.getsizeof(count_this_msg + 1)+ sys.getsizeof(senderpid) + sys.getsizeof(lookingfor)
					#	self.bytescount_outgoing += msg_size_bytes
					#	self.num_msg_find_outgoing += 1
					break
			else:
				
				with self.plock:						
					for p in self.nlist.keys():
						# Don't forward back to the sender
						if p == senderpid: continue
						# Forward ping
						self.out.send_msg(dest=p, msgname='find', msgargs=(sourcepid, sourcename, sourcenmax, sourcel, msgid, TTL, count_this_msg+1, lookingfor, path), track=True)
						# Increasing the number of sent messages
						#with self.plock:
							#self.bytescount_outgoing += sys.getsizeof(sourcepid) + sys.getsizeof(name) + sys.getsizeof(nmax) + sys.getsizeof(l) + sys.getsizeof(msgid)+ sys.getsizeof(TTL) + sys.getsizeof(count_this_msg + 1)+ sys.getsizeof(senderpid) + sys.getsizeof(lookingfor)
						#	self.bytescount_outgoing += msg_size_bytes
						#	self.num_msg_find_outgoing += 1
		else:
			print ("Seems that TTL is 0, then I don´t spread the search anymore")
	
	def found(self, pid, name, nmax, l, count_this_msg, path = []):
		self.__update_timer__(pid, name, nmax, l)
		msg_size_bytes = sum([ sys.getsizeof(x) for x in [ e[1] for e in locals().items() if e[0] != 'path' ] ])
		
		# Increasing the number of received messages and the counting of incoming total bytes
		with self.plock:
			self.num_msg_find_incoming += 1
			#self.bytescount_incoming += sys.getsizeof(pid) + sys.getsizeof(name) + sys.getsizeof(nmax) + sys.getsizeof(l) + sys.getsizeof(count_this_msg)
			self.bytescount_outgoing += msg_size_bytes
		print ("Im in found function")
		self.__update_timer__(pid, name, nmax, l)
		self.founditems[name] = pid
		path.append(self.name)
		print ("I found the peer", pid, "with name", name, "and", count_this_msg,"steps.")
		print ("------ FINAL PATH ------")
		for index, item in enumerate(path):
			print (index,item)
	
	#Kwalker		
	def kfind(self, senderpid, sendername, sendernmax, senderl, sourcepid, sourcename, sourcenmax, sourcel, msgid, TTL, count_this_msg, lookingfor, idwalker, hops, path = []):
		self.__update_timer__(senderpid, sendername, sendernmax, senderl)
		msg_size_bytes = sum([ sys.getsizeof(x) for x in [ e[1] for e in locals().items() if e[0] != 'path' ] ])
		
		print ("--------------------kfind WALKER", idwalker,"TTL",  TTL, "HOP NUMBER", hops, "--------------------")
		# Increasing the number of received messages and the counting of incoming total bytes
		with self.plock:
			self.num_msg_find_incoming += 1
			self.bytescount_incoming += msg_size_bytes
			#self.bytescount_incoming += sys.getsizeof(sourcepid) + sys.getsizeof(name) + sys.getsizeof(nmax) + sys.getsizeof(l) + sys.getsizeof(msgid)+ sys.getsizeof(TTL) + sys.getsizeof(count_this_msg)+ sys.getsizeof(senderpid) + sys.getsizeof(lookingfor)
		print ("Im in kfind function looking for", lookingfor)
		
		path.append(self.name)
		
		print ("------ ACTUAL PATH OF KWALKER ------ ")
		for index, item in enumerate(path):
			print (index,item)
		
		#s = '->'.join(path)
		#print (s)
		
		print ("Im looking if I have the file that", sourcename, "is looking for")
		
		TTL -= 1
		if (lookingfor == self.name):
			print ("##I have the file so Im sending a response to", sourcename)
			self.out.send_msg(dest=sourcepid, msgname='found', msgargs=(count_this_msg, path), track=True)
			
			# Increasing the number of sent messages
			#with self.plock:
			#	self.num_msg_find_outgoing += 1
				#self.bytescount_incoming += msg_size_bytes
				#self.bytescount_outgoing += sys.getsizeof(self.pid) + sys.getsizeof(self.name) + sys.getsizeof(self.nmax) + sys.getsizeof(len(self.nlist)) + sys.getsizeof(count_this_msg)
		elif TTL > 0: # We don't forward the message if TTL = 0
			#if (hops%MAX_HOPS == 0):
				######## WE HAVE TO MAKE THIS WITH ACTIVE WAITING AND BLOCKING
			#	self.out.send_msg(dest=sourcepid, msgname='checkHops', msgargs=(self.pid, lookingfor), track=True)
				######## UNTIL WE DONT HAVE A RESPONSE FROM sourcepid WE CANT CONTINUE

			print ("I don't have the file, so im going to send the search through all my neigbours")
			for pid in self.nlist:
				if (self.plist[pid][0] == lookingfor):
					print ("One of my neighbours have the file! I only forward the kfind message to him")
					self.out.send_msg(dest=pid, msgname='kfind', msgargs=(sourcepid, sourcename, sourcenmax, sourcel, msgid, TTL, count_this_msg+1, lookingfor, idwalker, hops + 1, path), track=True)
					# Increasing the number of sent messages
					#with self.plock:
						#self.bytescount_outgoing += sys.getsizeof(sourcepid) + sys.getsizeof(name) + sys.getsizeof(nmax) + sys.getsizeof(l) + sys.getsizeof(msgid)+ sys.getsizeof(TTL) + sys.getsizeof(count_this_msg + 1)+ sys.getsizeof(senderpid) + sys.getsizeof(lookingfor)
					#	self.bytescount_outgoing += msg_size_bytes
					#	self.num_msg_find_outgoing += 1
					break
			else:
		
				with self.plock:
					
					print ("I am adding the missing elements of klist regarding the active neighbours on nlist")						
					
					for pid in self.nlist:
						print ("I'm treating with the neighbour",pid)
						
						if ((pid, lookingfor)) in self.klist.keys():
							print ("I have this item:", (pid, lookingfor), "with value", self.klist[(pid, lookingfor)], "on klist")
									
						else:
							self.klist[(pid, lookingfor)] = 0
							print ("I dont have this item:", (pid, lookingfor), "on klist so im adding with value", self.klist[(pid, lookingfor)])
							
					print ("klist",self.klist)
					
					print ("Now I'm choosing only items that have looked for", lookingfor)
					candidates = {}
					for (pid,k),numbers in self.klist.items():
						if lookingfor == k:
							candidates[pid] = numbers
					print ("Candidates to send the k-Walker")
					print (candidates)
					
					min_pid = min(candidates, key=candidates.get)
					# Convert P into a list with the peers with the minimun values
					min_candidates = [ pid for pid, n in candidates.items() if n==candidates[min_pid] ]
					if len(min_candidates) > 1 and senderpid in min_candidates:
						min_candidates.remove(senderpid)
					p = min_candidates[0]
					# Now I am discarting 
					# POSSIBLE IMPROVEMENT: IF WE HAVE MORE THAN 1 MIN PID, DISCARD THE LAST SENDER (IF IT IS INSIDE)
					
					self.klist[(p, lookingfor)] += 1
					print ("I have choose", p, "to send the kwalker. So, I added 1 to its number of sent msgs:", self.klist[(p, lookingfor)])
					
					print ("I am sending a random k-walker to", p)
					self.out.send_msg(dest=p, msgname='kfind', msgargs=(sourcepid, sourcename, sourcenmax, sourcel, msgid, TTL, count_this_msg+1, lookingfor, idwalker, hops + 1, path), track=True)
	
		else:
			print ("Seems that TTL is 0, then I don´t spread the search anymore")
		print ("--------------------EXITING kfind WALKER", idwalker,"TTL", TTL, "--------------------")
	
	def get(self, sourcepid, name, nmax, l, lookingfor):
		self.__update_timer__(sourcepid, name, nmax, l)
		print ("The peer", sourcepid, "is requesting me the item", lookingfor)
		if lookingfor == self.name:
			print ("I have the item so im sending to him")
			itemrequested = self.name
			peer.out.send_msg(dest=sourcepid, msgname='got', msgargs=(itemrequested,))
		
		else:
			print ("I dont have the item!!")
			
	def got(self, sourcepid, name, nmax, l, itemrequested):
		self.__update_timer__(sourcepid, name, nmax, l)
		print ("Now I have the item", itemrequested, "from", sourcepid)

	def send_alive(self, sourcepid, name, nmax, l):
		self.__update_timer__(sourcepid, name, nmax, l)
		self.out.send_msg(dest=sourcepid, msgname='receive_alive', msgargs=())
		
	def receive_alive(self, sourcepid, name, nmax, l):
		self.__update_timer__(sourcepid, name, nmax, l)
	
	def be_my_nb(self, senderpid, sendername, sendernmax, senderl):
		self.__update_timer__(senderpid, sendername, sendernmax, senderl)
		#~ with self.plock:
			#~ if len(self.nlist) < self.nmax:
				#~ # ACCEPT
				#~ self.__accept_nb__(senderpid)
				#~ return
			#~ 
			#~ peer_score = PEER_SCORE(self.nmax, len(self.nlist), sendernmax)
			#~ assert peer_score >= 0 and peer_score <= 1
			#~ print (peer_score)
			#~ if random.random() <= peer_score:
				#~ # SUBSTITUTE
				#~ #Z = min(self.nlist, key=lambda pid: PEER_SCORE(self.nmax, len(self.nlist), self.plist[pid][1]))
				#~ #Z = random.choice(self.nlist)
				#~ Z = sorted(self.nlist, key=lambda pid: PEER_SCORE(self.nmax, len(self.nlist), self.plist[pid][1]))[len(self.nlist)//2]
				#~ del self.nlist[Z]
				#~ self.__accept_nb__(senderpid)
			#~ else:
				#~ # REJECT
				#~ self.__reject_nb__(senderpid)
		#~ return
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
				self.out.send_msg(dest=senderpid, msgname='yes_still_my_nb', msgargs=())
			else:
				self.out.send_msg(dest=senderpid, msgname='no_still_my_nb', msgargs=())
	
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
				msgargs=([ (p,self.plist[p][0],self.plist[p][1]) for p in self.nlist ],)
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
	
	def get_report(self, senderpid, name, nmax, l):
		self.__update_timer__(senderpid, name, nmax, l)
		"""
		Another peer has asked me my reports.
		"""
		with self.plock:
			self.out.send_msg(
				dest=senderpid,
				msgname='send_report',
				msgargs=(self.num_msg_find_incoming, self.num_msg_find_outgoing, self.bytescount_incoming, self.bytescount_outgoing)
			)
	
	def send_report(self, senderpid, name, nmax, l, nmsg_in, nmsg_out, nbytes_in, nbytes_out):
		self.__update_timer__(senderpid, name, nmax, l)
		"""
		One of the peers I requested the report to has finally replied me back.
		"""
		with self.plock:
			assert len(self.totreport_answers) < self.totreport_waited_answers
			self.totreport_answers.append( (senderpid,name,nmax,nmsg_in,nmsg_out,nbytes_in,nbytes_out) )
			if len(self.totreport_answers) == self.totreport_waited_answers:
				total_report(self.totreport_answers)
	
	def stop(self, senderpid, sendername, sendernmax, senderl):
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
		'plist':		[ plist, (), '_Prints the list of know peers.' ],
		'nlist':		[ nlist, (), 'Prints the list of neighbours of the given peers.' ],
		'find':			[ find, (), 'Look for a file in the neighbourhood.' ],
		'report': 		[ report, (), 'Show the incoming and outgoing number of messages for find.'],
		'totreport':	[ totreport, (), ''],
		'restart_report':[ restart_report, (), 'Restart the measurements of the report.'],
		'get':			[ get, (), 'Request a item to a peer'],
		'kfind':		[ kfind, (), 'Look for a file with zombie style.']
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
