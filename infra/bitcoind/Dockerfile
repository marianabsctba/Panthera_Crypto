FROM debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc

# Versão e hash fixos: o binário só entra se bater com o SHA256SUMS publicado pelo projeto.
ARG VERSAO=32.1
ARG SHA256=61545c17c3120fb7412f896d248b11993af04ec8817aad3649c55b2afb044963

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
 && curl -fsSLo /tmp/bitcoin.tar.gz "https://bitcoincore.org/bin/bitcoin-core-${VERSAO}/bitcoin-${VERSAO}-x86_64-linux-gnu.tar.gz" \
 && echo "${SHA256}  /tmp/bitcoin.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/bitcoin.tar.gz -C /tmp \
 && install -m 0755 /tmp/bitcoin-${VERSAO}/bin/bitcoind /tmp/bitcoin-${VERSAO}/bin/bitcoin-cli /usr/local/bin/ \
 && rm -rf /tmp/bitcoin* \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 1000 bitcoin

USER bitcoin
RUN mkdir -p /home/bitcoin/.bitcoin
ENTRYPOINT ["bitcoind", "-printtoconsole"]
