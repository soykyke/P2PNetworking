set datafile separator " "
#unset key
set key noenhanced
set key left top
set style data lines
#set grid
set xlabel 'Number of walkers'
set ylabel 'Number of messages'
set xtics (2,3,4,5,10,20,30,50)
set title "Number of messages for different number of walkers"
set style data linespoints
#set logscale x

set term postscript enhanced color
set output "graph-W-vs-MSG.eps"
plot 'graph-W-vs-MSG.dat' using 1:2 title 'TTL=5, 30 peers network'
