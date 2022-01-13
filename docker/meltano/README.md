Enter docker container with tap: 
- EODHistoricalData: `docker run --rm -v "$(pwd)/tap-eodhistoricaldata:/tap-eodhistoricaldata" --entrypoint /bin/bash -w /tap-eodhistoricaldata -it $(docker build -q .)`
- Polygon: `docker run --rm -v "$(pwd)/tap-polygon:/tap-polygon" --entrypoint /bin/bash -w /tap-polygon -it $(docker build -q .)`