# Observability Stack

Prometheus scrapes metrics over HTTP in the OpenMetrics format. Grafana queries PromQL and
renders dashboards; alert rules evaluate every 1 minute by default. OpenTelemetry unifies
traces, metrics, and logs with the OTLP protocol; the collector can batch and forward to
multiple backends. Node Exporter exposes host metrics: CPU, memory, disk, network. Alertmanager
deduplicates and routes alerts to Slack/PagerDuty/email. Golden signals: latency, traffic,
errors, saturation.
