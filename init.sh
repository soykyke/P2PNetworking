
# Instructions:
# ./init.sh <n-of-peers-to-launch> <starting-portno> <know-peer-portno> <global-max-neighbouring>

#Advice for global-max-neighbouring ($4) = 10

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#Implementation of Zipf's Law, with a value of s=2-2.5
#frequency f(k,s,N) being the frequency of the elements of rank k. (NB: N=n-of-peers-to-launch)
#f(k,s,N)=1/(k^s)*1/(sum i=1..N 1/i^s) (NB:sum i=1..N 1/i^s = Nth generalized harmonic number)
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#~~Determination of Nth Generalized harmonic number~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
s=$(echo 'scale=3; 2.0/1.0' | bc -l)
echo "Zipf's law power: $s"

harmonicNumber=$(echo 'scale=3; 0/1.0' | bc -l)
#echo $harmonicNumber

for j in `seq $1`
do

c=$(echo "scale=3; 1 / (e($s*l($j)))" | bc -l)
#echo $c
harmonicNumber=$(echo "$c+$harmonicNumber" |bc -l)

done
echo "Nth generalized harmonic number: $harmonicNumber"
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

sumofN=0

for k in `seq $4`
do
frequency=$(echo "scale=3; (1 / (e($s*l($k)))) * (1 / $harmonicNumber)" | bc -l)
echo "frequency of class $k: $frequency"
N=$(python -c "from math import floor; print floor($frequency*$1)")

#if N+sumofN<=10 on add N de la classe
#if N+sumofN>10 on add 10-SumofN de la class (si SumofN<=k-1)

if [ $(python -c "print int($sumofN)") -lt $1 ]
then
	if [ $(python -c "print int($sumofN+$N)") -le $1 ]
	then
		echo "$N peers added to class $k"
		#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		for i in `seq $N`
		do
			echo $(($2+$i))
			(python3 peer.py init $k $(python -c "print int($sumofN+$i)") localhost $(python -c "print int($2+$i+$sumofN)") , hello localhost:$3 , wait &)
		done
		#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		sumofN=$(python -c "print($sumofN+$N)")
		echo "Total number of peers generated: $sumofN"
	else
		echo "$(($1-$N)) added to classe $k"
		sumofN=$1
	fi
fi
done

if [ $(python -c "print int($1-$sumofN)") -gt 0 ]
then
	additional=$(python -c "print int($1-$sumofN)")
	echo "additional $additional peers added to class $k"
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	for i in `seq $additional`
	do
			(python3 peer.py init $k $(python -c "print int($sumofN+$i)") localhost $(python -c "print int($2+$i+$sumofN)") , hello localhost:$3 , wait &)
	done
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
fi




#for i in `seq $1`
#do
#	#echo $(($2+$i))
#	(python3 peer.py init $i $i localhost $(($2+$i)) , hello localhost:$3 , wait &)
#done
