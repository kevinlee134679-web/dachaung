import json


def _unique_object(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate JSON property")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite JSON")


def loads(raw):
    return json.loads(
        raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant
    )
