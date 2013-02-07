#(python peer.py superinit 10 localhost 9000 &)

for i in `seq $1`
do
	#echo $((9000+$i))
	(python peer.py init 10 $i localhost $((9000+$i)) , hello localhost:9000 &)
done
