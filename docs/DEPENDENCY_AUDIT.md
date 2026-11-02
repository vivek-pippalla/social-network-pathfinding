# Runtime dependency audit

Audit run: 2026-11-02, using Python 3.11.14 from the existing Conda `graph` environment.

Command:

```powershell
$cacheDir = Join-Path $env:TEMP "social-network-pathfinding-pip-audit"
python -m pip_audit --cache-dir $cacheDir -r requirements.txt
```

The command was run with a temporary cache directory after the default user cache path proved unwritable. It resolved the pinned runtime requirements and reported three advisory rows across two packages:

| Package | Pinned version | Advisory | Triage |
| --- | --- | --- | --- |
| `python-jose` | 3.5.0 | PYSEC-2026-4298 | The Python Packaging Advisory Database marks versions through 3.5.0 affected by an algorithm-confusion guard bypass. The existing application explicitly supplies an algorithm allow-list, but the library remains affected and will be removed with the authentication replacement in Phase 3. |
| `ecdsa` (transitive) | 0.19.2 | PYSEC-2026-1325 (reported twice by pip-audit) | The advisory describes a timing side channel in ECDSA signing and ECDH; the advisory states that the upstream project has no planned fix. This project currently defaults to HS256, but its legacy JWT algorithm remains configurable. The dependency is retained only with the legacy `python-jose` stack and is scheduled to disappear in Phase 3. |

The duplicate `ecdsa` row is a duplicate report of the same advisory, not a third distinct vulnerability. The audit is **not clean**; this report records the remaining findings for the Phase 0 gate and does not claim otherwise. Re-run the audit after Phase 3 replaces the authentication stack.

Sources: [python-jose advisory PYSEC-2026-4298](https://github.com/pypa/advisory-database/blob/main/vulns/python-jose/PYSEC-2026-4298.yaml), [ecdsa advisory PYSEC-2026-1325](https://github.com/pypa/advisory-database/blob/main/vulns/ecdsa/PYSEC-2026-1325.yaml).
