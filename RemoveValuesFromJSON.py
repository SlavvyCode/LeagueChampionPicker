def strip_values(obj):
    if isinstance(obj, dict):
        return {k: strip_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [strip_values(v) for v in obj]
    else:
        return None

# Example usage:
import json

with open('WINDOWSSRDATAWITHKEYS.json', 'r',encoding='utf-8') as f:
    data = json.load(f)

stripped = strip_values(data)

with open('stripped_output.json', 'w') as f:
    json.dump(stripped, f, indent=2)
