FROM apache/tika:3.0.0.0-full

USER root

RUN DEBIAN_FRONTEND=noninteractive \
    apt-get update \
    && apt-get install --yes --no-install-recommends tesseract-ocr-por

USER $UID_GID