# SNAP ego-Facebook dataset

The ingestion CLI downloads `facebook_combined.txt.gz` from the official SNAP
dataset endpoint on first use and checks its SHA-256 before opening a Neo4j
write transaction. The downloaded archive is cached at this path locally, but
is excluded from Git and Docker build contexts.

- Source: [SNAP social circles: Facebook](https://snap.stanford.edu/data/ego-Facebook.html)
- Download: <https://snap.stanford.edu/data/facebook_combined.txt.gz>
- Citation: J. McAuley and J. Leskovec, “Learning to Discover Social Circles in Ego Networks,” NIPS, 2012.
- Expected SHA-256: `125e84db872eeba443d270c70315c256b0af43a502fcfe51f50621166ad035d7`
- Expected graph: 4,039 users and 88,234 undirected edges.

The SNAP dataset page describes the data and requests citation, but does not
state a dataset-specific redistribution license. SNAP's separate BSD license
page describes the SNAP software, not an explicit license for this dataset.
To avoid assuming that the software license grants data redistribution rights,
this project fetches the archive directly from SNAP when needed and verifies
the pinned digest before use. The hash establishes file integrity; it is not a
license grant.
