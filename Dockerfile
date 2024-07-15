FROM python:3.10

WORKDIR /src

# Download and install docker client using Docker's convenience script
RUN apt-get update && \
    apt-get -y install apt-transport-https \
         ca-certificates \
         curl \
         gnupg2 \
         software-properties-common && \
    curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    rm get-docker.sh

# Install additional packages
RUN apt-get -y install knot-dnsutils net-tools

COPY requirements.txt /src
RUN pip install -r requirements.txt

COPY istream_player istream_player
COPY scripts scripts
COPY setup.py .

RUN pip install .

ENTRYPOINT ["python3", "/src/istream_player/main.py", "-h"]
