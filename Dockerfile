FROM ubuntu:16.04

USER root

WORKDIR /var/lib/

RUN mkdir -p cvp-sanity-checks/

COPY . cvp-sanity-checks/

RUN apt-get update && \
    apt-get install -y python-pip git curl wget vim inetutils-ping && \
    python -m pip install --upgrade pip && \
    pip install -r cvp-sanity-checks/requirements.txt && \
    apt-get -y autoremove; apt-get -y clean

RUN rm -rf /root/.cache && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/* && \
    rm -rf /var/tmp/*

ENTRYPOINT ["/bin/bash"]
