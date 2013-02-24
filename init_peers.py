import random
import math
import sys
import subprocess

PEER_SCRIPT = 'peerStillAlive.py'

NUM_PEERS = int(sys.argv[1])
MIN_NB = int(sys.argv[2])
MAX_NB = int(sys.argv[3])
START_PORTNO = int(sys.argv[4])
KNOWNPEER_PORTNO = int(sys.argv[5])

lista = [ random.expovariate(1) for i in range(NUM_PEERS+1) ]
listafinal = [ round((i/max(lista)*(MAX_NB-MIN_NB))+MIN_NB) for i in lista ]

print (sorted(listafinal))
print (max(listafinal))

#import numpy as np
#import matplotlib.pyplot as plt

#x = listafinal
#y = range(len(listafinal))
#plt.plot(y, x)
#plt.show()

for i,maxn in enumerate(listafinal):
	subprocess.Popen(['python3', PEER_SCRIPT, repr(MAX_NB),
		'init', repr(maxn), repr(i), 'localhost', repr(START_PORTNO+i), ',', 
		'hello', 'localhost:%d' % (KNOWNPEER_PORTNO), ',',
		'wait'], shell=False)
