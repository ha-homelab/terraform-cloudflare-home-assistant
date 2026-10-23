#!/usr/bin/env python3
"""Validate deployment examples offline. No Docker, Kubernetes or cloud calls."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / ".github" / "schemas"
COMPOSE_COMMIT = "3a4a6995e4a971f6173dff9130cb3e38e6738651"
KUBERNETES_COMMIT = "66452049f3d692768c39c797b21b793dce80314e"  # v1.35.0
SOURCES = {
    "compose": f"https://raw.githubusercontent.com/compose-spec/compose-spec/{COMPOSE_COMMIT}/schema/compose-spec.json",
    "kubernetes": f"https://raw.githubusercontent.com/kubernetes/kubernetes/{KUBERNETES_COMMIT}/api/openapi-spec/swagger.json",
}
KINDS = {
    ("v1", "Namespace"): "io.k8s.api.core.v1.Namespace",
    ("apps/v1", "Deployment"): "io.k8s.api.apps.v1.Deployment",
    ("networking.k8s.io/v1", "NetworkPolicy"): "io.k8s.api.networking.v1.NetworkPolicy",
}


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicates instead of silently validating only the last value."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in result:
                raise ValueError(
                    f"Duplicate YAML key at line {key_node.start_mark.line + 1}"
                )
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def read_yaml(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        docs = list(yaml.load_all(stream, Loader=UniqueKeyLoader))
    if not docs or any(not isinstance(doc, dict) for doc in docs):
        raise ValueError(f"{path.name}: every YAML document must be an object")
    return docs


def validate_schema(document: dict, schema: dict) -> None:
    def reject_external_references(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"$ref", "$dynamicRef", "$recursiveRef"}:
                    check(
                        isinstance(child, str) and child.startswith("#"),
                        "Offline schemas must use only local references",
                    )
                reject_external_references(child)
        elif isinstance(value, list):
            for child in value:
                reject_external_references(child)

    reject_external_references(schema)
    validator = jsonschema.validators.validator_for(schema)
    validator.check_schema(schema)
    validator(schema).validate(document)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def pinned_image(image: str) -> None:
    check(
        bool(
            re.fullmatch(
                r"cloudflare/cloudflared:\d{4}\.\d+\.\d+@sha256:[0-9a-f]{64}", image
            )
        ),
        "Use the official cloudflared image pinned to a version and SHA256 digest",
    )


def validate_compose(document: dict, schema: dict) -> str:
    validate_schema(document, schema)
    check(
        set(document["services"]) == {"cloudflared"},
        "Compose example must contain only the connector",
    )
    service = document["services"]["cloudflared"]
    pinned_image(service["image"])
    check(
        service.get("user") == "${CLOUDFLARED_UID:-65532}:${CLOUDFLARED_GID:-65532}",
        "Keep configurable, non-root UID/GID defaults",
    )
    check(
        service.get("read_only") is True and service.get("cap_drop") == ["ALL"],
        "Compose must have a read-only filesystem and drop all capabilities",
    )
    check(
        "no-new-privileges:true" in service.get("security_opt", []),
        "Compose must prevent privilege escalation",
    )
    check(
        not service.get("privileged")
        and not service.get("ports")
        and not service.get("environment")
        and not service.get("env_file"),
        "Compose must not publish ports, use privilege or embed credential environment",
    )
    command = service["command"]
    check(
        isinstance(command, list)
        and "--token" not in command
        and command[-2:] == ["--token-file", "/run/secrets/tunnel_token"],
        "Pass the token by file, never a literal or environment argument",
    )
    check(
        set(document.get("secrets", {})) == {"tunnel_token"}
        and service.get("secrets") == ["tunnel_token"],
        "Compose must mount only the private tunnel token file",
    )
    secret = document["secrets"]["tunnel_token"]
    check(
        set(secret) == {"file"}
        and str(secret["file"]).startswith("${TUNNEL_TOKEN_FILE:?"),
        "Token file must be supplied explicitly by the operator",
    )
    network = document.get("networks", {}).get("origin", {})
    check(
        network.get("external") is True
        and network.get("name") == "${HA_NETWORK:-ha-origin}",
        "Join the operator's existing origin network",
    )
    return service["image"]


def validate_kubernetes(documents: list[dict], bundle: dict) -> str:
    indexed = {}
    for document in documents:
        key = (document.get("apiVersion"), document.get("kind"))
        check(
            key in KINDS and key not in indexed,
            "Kubernetes example allows exactly one Namespace, Deployment and NetworkPolicy; no embedded Secret",
        )
        schema = {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "$ref": "#/definitions/" + KINDS[key],
            "definitions": bundle["definitions"],
        }
        validate_schema(document, schema)
        indexed[key] = document
    check(
        set(indexed) == set(KINDS),
        "Kubernetes example requires Namespace, Deployment and NetworkPolicy",
    )
    namespace = indexed[("v1", "Namespace")]["metadata"]["name"]
    deployment = indexed[("apps/v1", "Deployment")]
    policy = indexed[("networking.k8s.io/v1", "NetworkPolicy")]
    check(
        deployment["metadata"].get("namespace")
        == namespace
        == policy["metadata"].get("namespace"),
        "Kubernetes resources must share the declared namespace",
    )
    spec = deployment["spec"]
    pod = spec["template"]["spec"]
    labels = spec["template"]["metadata"]["labels"]
    check(
        spec["selector"]["matchLabels"]
        == labels
        == policy["spec"]["podSelector"]["matchLabels"],
        "Deployment and ingress policy selectors must match only connector pods",
    )
    check(
        policy["spec"].get("policyTypes") == ["Ingress"]
        and policy["spec"].get("ingress") == []
        and "egress" not in policy["spec"],
        "NetworkPolicy must deny inbound pod traffic without blocking tunnel egress",
    )
    security = pod.get("securityContext", {})
    check(
        pod.get("automountServiceAccountToken") is False
        and security.get("runAsNonRoot") is True,
        "Connector does not need API credentials or root",
    )
    check(
        security.get("runAsUser", 0) > 0
        and security.get("runAsGroup", 0) > 0
        and security.get("fsGroup", 0) > 0
        and security.get("seccompProfile", {}).get("type") == "RuntimeDefault",
        "Use non-root ownership and RuntimeDefault seccomp",
    )
    check(
        len(pod["containers"]) == 1 and not pod.get("initContainers"),
        "Keep only the connector container",
    )
    container = pod["containers"][0]
    pinned_image(container["image"])
    security = container.get("securityContext", {})
    check(
        security.get("allowPrivilegeEscalation") is False
        and security.get("readOnlyRootFilesystem") is True
        and security.get("capabilities", {}).get("drop") == ["ALL"],
        "Kubernetes container must be hardened",
    )
    check(
        not container.get("env")
        and not container.get("envFrom")
        and "--token" not in container["args"]
        and container["args"][-2:] == ["--token-file", "/etc/cloudflared/token"],
        "Kubernetes token must come only from the private mounted file",
    )
    check(
        container["readinessProbe"]["httpGet"]["path"] == "/ready"
        and container["livenessProbe"]["httpGet"]["path"] == "/healthcheck",
        "Readiness must check edge connectivity; liveness must not restart an otherwise healthy process during an edge outage",
    )
    check(
        all(
            container["resources"].get(kind, {}).get(resource)
            for kind in ["requests", "limits"]
            for resource in ["cpu", "memory"]
        ),
        "Set CPU and memory requests and limits",
    )
    check(
        pod["volumes"]
        == [
            {
                "name": "tunnel-token",
                "secret": {
                    "secretName": "cloudflared-token",
                    "defaultMode": 0o440,
                    "items": [{"key": "token", "path": "token"}],
                },
            }
        ],
        "Reference a pre-existing Secret; do not commit token contents",
    )
    check(
        container["volumeMounts"]
        == [
            {"name": "tunnel-token", "mountPath": "/etc/cloudflared", "readOnly": True}
        ],
        "Token volume must be read-only at the command's token path",
    )
    return container["image"]


def refresh_schemas() -> None:
    """Explicit maintenance command; normal validation never accesses a URL."""
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    compose = json.load(urlopen(SOURCES["compose"], timeout=30))
    upstream = json.load(urlopen(SOURCES["kubernetes"], timeout=30))
    selected: dict = {}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref", "")
            if ref.startswith("#/definitions/"):
                name = ref.removeprefix("#/definitions/")
                if name not in selected:
                    selected[name] = copy.deepcopy(upstream["definitions"][name])
                    visit(selected[name])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for name in KINDS.values():
        visit({"$ref": "#/definitions/" + name})

    def compact(value: object, property_map: bool = False) -> None:
        if isinstance(value, dict):
            if not property_map:
                value.pop("description", None)
            if (
                value.get("x-kubernetes-int-or-string")
                or value.get("format") == "int-or-string"
            ):
                value["type"] = ["integer", "string"]
            if "properties" in value:
                value.setdefault("additionalProperties", False)
            for key, child in value.items():
                compact(child, property_map=(key == "properties"))
        elif isinstance(value, list):
            for child in value:
                compact(child)

    compact(selected)
    bundle = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "definitions": selected,
    }
    for name, schema in [("compose", compose), ("kubernetes", bundle)]:
        (SCHEMAS / (name + ".json")).write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(
        f"Refreshed pinned Compose schema and {len(selected)} Kubernetes definitions."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--refresh-schemas",
        action="store_true",
        help="Maintainer-only: download the pinned upstream schemas",
    )
    args = parser.parse_args()
    if args.refresh_schemas:
        refresh_schemas()
        return 0
    try:
        schemas = args.root / ".github" / "schemas"
        compose_docs = read_yaml(args.root / "examples/docker/compose.yaml")
        check(len(compose_docs) == 1, "Compose example must have one document")
        compose_image = validate_compose(
            compose_docs[0], json.loads((schemas / "compose.json").read_text())
        )
        kubernetes_image = validate_kubernetes(
            read_yaml(args.root / "examples/k3s/cloudflared.yaml"),
            json.loads((schemas / "kubernetes.json").read_text()),
        )
        check(
            compose_image == kubernetes_image,
            "Compose and Kubernetes examples must use the same pinned image",
        )
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        yaml.YAMLError,
        jsonschema.ValidationError,
        jsonschema.SchemaError,
    ) as error:
        print(f"Example validation failed: {error}", file=sys.stderr)
        return 1
    print(
        "Compose and Kubernetes schemas, image pins, token mounts and runtime security contracts passed offline."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
