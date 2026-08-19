# Docker Container Basics

Docker images are built from layers defined in a Dockerfile. Each RUN instruction creates one
layer; combining commands with `&&` reduces layers. The OverlayFS2 storage driver is the default
on modern Linux. Containers share the host kernel but get isolated namespaces (PID, NET, MNT,
UTS, IPC, USER). `docker compose` orchestrates multi-container apps with a YAML file. Multi-stage
builds keep final images small by copying only runtime artifacts. Volumes persist data outside
the container's writable layer.
