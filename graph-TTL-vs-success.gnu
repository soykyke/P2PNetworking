set datafile separator " "
#unset key
set key noenhanced
set key left top
set style data lines
#set grid
set xlabel 'TTL'
set ylabel '% of successful lookups'
set xtics (2,3,4,5)
set title "Percentage of successful lookups with different TTL values"
set style data linespoints

set term postscript enhanced color
set output "graph-TTL-vs-success.eps"
plot 'graph-TTL-vs-success.dat' using 1:2 title 'Flooding -- 30 peers network', \
     'graph-TTL-vs-success.dat' using 1:4 title 'Flooding -- 70 peers network', \
     'graph-TTL-vs-success.dat' using 1:3 title '2-walkers -- 30 peers network', \
     'graph-TTL-vs-success.dat' using 1:5 title '2-walkers -- 70 peers network'

