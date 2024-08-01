FROM alpine:3.20 AS build-infoedit
WORKDIR /app
RUN apk add --no-cache build-base boost-dev git
RUN git clone https://github.com/NDN-Routing/infoedit.git . && \
    make && \
    make install DESTDIR=/build

FROM python:3.10-alpine
WORKDIR /app
# Runtime dependencies
RUN apk add --no-cache libgcc libstdc++ boost-program_options jq bash
# Build dependencies (for pip install)
RUN apk add --no-cache gcc python3-dev musl-dev linux-headers
COPY --from=ghcr.io/usnistgov/ndntdump:latest /ndntdump /usr/local/bin/
COPY --from=build-infoedit /build/usr/local/bin/infoconv /usr/local/bin/
COPY --from=build-infoedit /build/usr/local/bin/infoedit /usr/local/bin/
COPY scheduler.py .
COPY requirements.txt .
# temp
COPY nlsr.conf . 
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT ["sleep", "infinity"]