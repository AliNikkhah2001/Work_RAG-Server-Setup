# Kubernetes Scheduling & Networking

The Kubernetes scheduler assigns pods to nodes based on resource requests and affinity rules.
A pod's Quality of Service (QoS) class is determined by CPU/memory requests vs limits: Guaranteed
(when requests == limits), Burstable, and BestEffort. The kube-proxy implements Service routing
via iptables or IPVS. CNI plugins like Calico enforce network policies. Horizontal Pod Autoscaler
scales replicas based on CPU utilization (default target 80%).
