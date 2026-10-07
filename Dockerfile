FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1

RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl lib32gcc-s1 lib32stdc++6 \
        build-essential python3 python3-dev python3-pip redis-server git \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir redis hiredis requests pyzmq numpy scipy

# SteamCMD + Quake Live dedicated server (app 349090, anonymous login)
RUN mkdir -p /opt/steamcmd && curl -sSL https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz \
        | tar -xz -C /opt/steamcmd
RUN /opt/steamcmd/steamcmd.sh +force_install_dir /ql +login anonymous +app_update 349090 validate +quit \
    || /opt/steamcmd/steamcmd.sh +force_install_dir /ql +login anonymous +app_update 349090 validate +quit

# minqlx (built from the local, possibly patched, source tree)
COPY minqlx /src/minqlx
RUN cd /src/minqlx && make clean && make && cp bin/* /ql/ && mkdir -p /ql/minqlx-plugins

# movement simulator (same collision/observation code the policies were trained with)
COPY sim /sim
RUN cd /sim && gcc -O2 -shared -fPIC -w -DNDEBUG -fvisibility=hidden -Wl,-Bsymbolic -o libqsim.so sim_api.c q3/bg_pmove.c q3/bg_slidemove.c q3/bg_misc.c         q3/q_math.c q3/q_shared.c q3/cm_load.c q3/cm_patch.c q3/cm_polylib.c q3/cm_test.c q3/cm_trace.c -lm

COPY server /ql/baseq3-extra
COPY plugins /ql/minqlx-plugins
COPY maps /ql/maps-data
COPY docs/MAPS.md /ql/maps-data/MAPS.md
COPY entrypoint.sh /entrypoint.sh
COPY tools /tools
RUN sed -i 's/\r$//' /entrypoint.sh /ql/baseq3-extra/* && chmod +x /entrypoint.sh /ql/run_server_x64_minqlx.sh

EXPOSE 27960/udp 28960/tcp
ENTRYPOINT ["/entrypoint.sh"]
