# Alpine Linux with OpenJDK JRE
# FROM openjdk:11-jre-alpine
FROM alpine:3.10.1
RUN apk --no-cache add openjdk11
MAINTAINER Golem Tech <tech@golem.network>
RUN apk add jq
WORKDIR /
COPY scripts/ /golem/scripts/
RUN chmod +x /golem/scripts/job.sh
