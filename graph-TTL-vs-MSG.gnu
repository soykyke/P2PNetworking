set datafile separator " "
#unset key
set key noenhanced
set key left top
set style data lines
#set grid
set xlabel 'TTL'
set ylabel 'number of messages'
set xtics (2,3,4,5,10,50)
set title "Number of messages for different TTL values"
set style data linespoints
set logscale x

set term postscript enhanced color
set output "graph-TTL-vs-MSG.eps"
plot 'graph-TTL-vs-MSG.dat' using 1:2 title 'Flooding -- 30 peers network', \
     'graph-TTL-vs-MSG.dat' using 1:3 title '10-walkers -- 30 peers network'
#     'graph-TTL-vs-MSG.dat' using 1:3 title '2-walkers -- 30 peers network', \
#     'graph-TTL-vs-MSG.dat' using 1:5 title '2-walkers -- 70 peers network'

