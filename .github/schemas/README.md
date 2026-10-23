# Offline schema snapshots

These schemas validate the checked-in runtime examples without contacting Docker,
Kubernetes, Cloudflare or a schema registry. They are validation inputs, not
deployment manifests. Their upstream licenses are retained beside them.

- `compose.json`: the complete official [Compose schema](https://github.com/compose-spec/compose-spec/blob/3a4a6995e4a971f6173dff9130cb3e38e6738651/schema/compose-spec.json),
  pinned to commit `3a4a6995e4a971f6173dff9130cb3e38e6738651`.
  JSON formatting and key ordering are normalized; schema semantics are unchanged.
  See [LICENSE-compose](LICENSE-compose), Apache License 2.0.
- `kubernetes.json`: Namespace, Deployment and NetworkPolicy definitions and their
  transitive references from the official [Kubernetes v1.35.0 OpenAPI schema](https://github.com/kubernetes/kubernetes/blob/66452049f3d692768c39c797b21b793dce80314e/api/openapi-spec/swagger.json),
  commit `66452049f3d692768c39c797b21b793dce80314e`.
  Only 131 required definitions are retained. Descriptions are omitted to keep the
  bundle small. Objects with declared properties reject unknown fields, and
  OpenAPI `int-or-string` fields accept both integers and strings. See
  [LICENSE-kubernetes](LICENSE-kubernetes), Apache License 2.0.

Kubernetes 1.35 is a **schema baseline**, not a guarantee of compatibility with
every Kubernetes distribution, admission controller or NetworkPolicy implementation.
The validator cannot prove that an origin is reachable or a token works.

To reproduce these files, install the [CI dependencies](../requirements-ci.txt)
and run this explicit maintenance command from the repository root:

```sh
python scripts/validate-examples.py --refresh-schemas
python scripts/check-docs-tests.py
python scripts/validate-examples.py
```

Only `--refresh-schemas` downloads files. The default command is offline. For an
upstream update, review and change the immutable source commits in
[`validate-examples.py`](../../scripts/validate-examples.py), regenerate the
schemas, retain updated licenses if necessary, update this provenance note, and
review the schema diff before committing it.
