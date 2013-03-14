set datafile separator " "
#unset key
set key noenhanced
set key left top
set style data lines
#set grid
set xlabel 'Number of walkers'
set ylabel '% of successful lookups'
set xtics (2,3,4,5,10,20,30,50)
set title "Percentage of successful lookups with different number of walkers"
set style data linespoints

set term postscript enhanced color
set output "graph-W-vs-success.eps"
plot 'graph-W-vs-success.dat' using 1:2 title '30 peers network', \
     'graph-W-vs-success.dat' using 1:3 title '70 peers network'
