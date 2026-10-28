FROM alpine:3.20

RUN apk add --no-cache nftables iproute2

COPY entrypoint.sh /usr/local/bin/egress-guard
COPY healthcheck.sh /usr/local/bin/egress-guard-healthcheck
RUN chmod 0755 /usr/local/bin/egress-guard \
    /usr/local/bin/egress-guard-healthcheck

ENTRYPOINT ["/usr/local/bin/egress-guard"]
CMD ["sleep", "infinity"]
