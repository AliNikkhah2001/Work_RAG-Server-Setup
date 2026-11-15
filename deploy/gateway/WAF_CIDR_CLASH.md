# WAF VIP vs Docker bridge CIDR clash (`chat.ics24.ir`)

## Symptom

`chat.ics24.ir` resolves to corporate WAF VIP **`172.24.65.109`**. From this GPU host the VIP became unreachable (blackhole) while the local WebUI origin stayed healthy:

- `curl -H 'Host: chat.ics24.ir' http://127.0.0.1:8088/` → 200
- `curl http://127.0.0.1:13000/` → 200
- `curl https://chat.ics24.ir/` → fail / proxy DNS errors when traffic must hit the VIP path from the host

## Root cause (validated)

Docker Compose created `jenkins_default` with auto subnet **`172.24.0.0/16`** (2026-11-11). That `/16` overlaps WAF VIP subnet **`172.24.65.0/24`**. The kernel then preferred the Docker bridge for `172.24.65.109`, so host→VIP packets never left via `ens35`.

This is **not** primarily a “DNS cache renew” bug: DNS kept returning the correct VIP; the host route table was wrong.

A band-aid oneshot unit `waf-route-fix.service` (installed 2026-11-12) briefly added:

```text
ip route replace 172.24.65.0/24 via 192.168.177.9 dev ens35
```

Because it is `Type=oneshot` + `RemainAfterExit=yes`, it does **not** re-apply after Docker recreates bridges. After later Jenkins/container churn (seen 2026-11-14 17:01), the `/24` disappeared and the clash returned with **no application code change**.

### Secondary failure mode (ports)

On 2026-11-14 Docker also logged bind failures (`127.0.0.1:16379`, `:8200` already allocated) when `dana-prod-*` containers started — separate from the WAF clash; addressed by the reserved stage/prod port map.

## Durable fix

1. Pin Jenkins default network to **`172.30.100.0/24`** in [`../jenkins/docker-compose.yml`](../jenkins/docker-compose.yml).
2. Set Docker `default-address-pools` to **`172.30.0.0/16`** (`size: 24`) in `/etc/docker/daemon.json` so future compose projects never land on `172.24` (takes effect on dockerd restart; explicit compose IPAM pins still required).
3. Recreate `jenkins_default` after the pin (brief Jenkins downtime). Use image **`dana-jenkins:production`** (not a bare `jenkins/jenkins:lts` without plugins).
4. Do **not** rely on `waf-route-fix` once Jenkins is off `172.24` (unit is masked).

### Hypothesis: “Docker cached DNS renew broke chat.ics24.ir”

**Verdict: PARTLY WRONG as stated — the real failure was a Docker bridge CIDR / route clash, not DNS cache.**

| Claim | Result |
|-------|--------|
| DNS for `chat.ics24.ir` went stale / wrong | **Rejected.** Host DNS kept resolving to WAF VIP `172.24.65.109`. |
| Something “renewed” and broke silently with no app deploy | **Accepted as timing.** Docker network create/recreate (Jenkins 2026-11-11, stage recreate 2026-11-15) auto-assigned `172.24.0.0/16`, which blackholes the VIP on the host. |
| Cache/DNS renew inside Docker | **Rejected as primary.** Journal shows Docker *container* DNS timeouts to 1.1.1.1 from `172.24.0.2` (Jenkins outbound), unrelated to clients reaching the VIP. |
| Fragility after a temporary fix | **Accepted.** `waf-route-fix.service` oneshot installed a `/24` via `ens35`, then stopped re-applying after churn. |

So: not “DNS cache”, but **Docker IPAM claiming the same `/16` as the corporate WAF VIP**, which looks like a silent DNS/connectivity failure from outside.

### Forbidden Docker bridge ranges on this host

| Range | Why |
|-------|-----|
| `172.24.0.0/16` | Overlaps WAF VIP `172.24.65.0/24` (`chat.ics24.ir`) |
| `10.10.10.0/24` | Corporate / reserved — do not use for Docker |
| `172.10.0.0/16` | Outside RFC1918 `172.16.0.0/12` — do not use |

### Allowed / pinned

| Range | Use |
|-------|-----|
| `172.30.100.0/24` | Jenkins (`jenkins_default`) |
| `172.30.101.0/24` | Stage compose (`dana-stage_rag`) |
| `172.30.110.0/24` | Base/local compose (`rag` / `dana-prod` style) |
| `172.30.0.0/16` pools | Future Docker Compose default bridges (`daemon.json`) |

**Lesson (2026-11-15):** After Jenkins was fixed, bringing up `dana-stage` without an IPAM pin auto-claimed `172.24.0.0/16` again and immediately re-broke `ip route get 172.24.65.109`. Always pin every Compose project network on this host.

## Acceptance checks

```bash
docker network inspect jenkins_default --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
# expect: 172.30.100.0/24

ip route get 172.24.65.109
# expect: via 192.168.177.9 dev ens35  (NOT a docker br-*)

curl -sI --max-time 10 https://chat.ics24.ir/ | head -5
curl -sI -H 'Host: chat.ics24.ir' http://127.0.0.1:8088/ | head -5
curl -sI http://127.0.0.1:13000/ | head -5
```

## Related

- XFF / upstream notes: [`../../components/server-setup/deploy/gateway/WAF_XFF_FIX.md`](../../components/server-setup/deploy/gateway/WAF_XFF_FIX.md)
- Snapshot evidence: `/splunk-data/production/snapshots/20261115T124350Z/meta/WAF_CIDR_HYPOTHESIS.md`
