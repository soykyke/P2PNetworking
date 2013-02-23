import random
import math
import sys

NUM_PEERS = int(sys.argv[1])
MIN_NB = int(sys.argv[2])
MAX_NB = int(sys.argv[3])

lista = [ random.expovariate(1) for i in range(NUM_PEERS) ]
listafinal = [ round((i/max(lista)*(MAX_NB-MIN_NB))+MIN_NB) for i in lista ]

print (sorted(listafinal))
print (max(listafinal))

#import numpy as np
#import matplotlib.pyplot as plt

#x = listafinal
#y = range(len(listafinal))
#plt.plot(y, x)
#plt.show()


