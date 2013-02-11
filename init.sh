
# Instructions:
# ./init.sh <n-of-peers-to-launch> <starting-portno> <know-peer-portno>

for i in `seq $1`
do
	#echo $(($2+$i))
	(python3 peer.py init $i $i localhost $(($2+$i)) , hello localhost:$3 , wait &)
done
