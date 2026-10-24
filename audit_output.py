
import json


class InvalidAuditOutput(ValueError):
    pass


def parse_audit_output(text):
    try:
        data = json.loads(text.strip())
    except (ValueError, TypeError) as exc:
        raise InvalidAuditOutput(
            "Agent did not return valid JSON"
        ) from exc

    if not isinstance(data, dict):
        raise InvalidAuditOutput(
            "Agent output must be a JSON object"
        )

    claims = data.get("claims")

    if not isinstance(claims, list) or not claims:
        raise InvalidAuditOutput(
            "Missing or empty claim list"
        )

    if data.get("coverage_complete") is not True:
        raise InvalidAuditOutput(
            "Agent did not confirm complete claim coverage"
        )

    for index, item in enumerate(claims):
        if not isinstance(item, dict):
            raise InvalidAuditOutput(
                f"Claim {index} is not an object"
            )

        if not isinstance(item.get("claim"), str):
            raise InvalidAuditOutput(
                f"Claim {index} has no valid claim text"
            )

        if not item["claim"].strip():
            raise InvalidAuditOutput(
                f"Claim {index} is empty"
            )

        for field in ("chunk_id", "quote"):
            if not isinstance(item.get(field), str):
                raise InvalidAuditOutput(
                    f"Claim {index} has invalid {field}"
                )

    return data
