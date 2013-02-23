import random
import math
	

max = 0
lista = []
for i in range(50):
	r = random.expovariate(1)
	lista.append(r)
	#print (r)
	if r > max:
		max = r
		
print ("HOOOLA")
listafinal = []
for i in lista:
	#print (i)
	a = 10*i/max
	listafinal.append(a)

lista.sort()
listafinal.sort()

listafinaldiscrete = []
for i in listafinal:
	c = int(i)
	if i%0.1 > 0.5:
		c+=2
	if c == 0:
		c = 1
	listafinaldiscrete.append(c)

	

print ("max",max)

for i in listafinaldiscrete:
	print (i)

import numpy as np
import matplotlib.pyplot as plt

x = listafinal
y = range(len(listafinal))
plt.plot(y, x)
plt.show()


