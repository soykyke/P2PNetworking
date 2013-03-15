P2PNetworking
=============

## Basic Usage

To launch a peer use:

	python3 peer.py 10 init 3 -1 localhost 9000

The command signature is:

	python3 peer.py MAX-NB init NMAX NAME IPADDR PORTNO

This command inits the peer and opens up a shell.

To see the list of possible commands type a question mark to the shell:

	P-1>> ?

## Launching a lot of peers automatically

To launch 30 peers automatically, given that there is a peer on port 9000,
use this command:

	python3 init_peers.py 30 1 10 9001 9000

The command signature is:

	python3 init_peers.py NUM-OF-PEERS MIN-NB MAX-NB START-PORTNO KNOWN-PEER-PORTNO
