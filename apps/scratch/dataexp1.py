import json
import sys

def get_structure(obj, indent=0):
    """Recursively prints the key structure of a dict/list."""
    prefix = "  " * indent
    if isinstance(obj, dict):
        for key, value in obj.items():
            print(f"{prefix}{key}:")
            if key == 'parent':
                sys.exit(0)
            get_structure(value, indent + 1)
    elif isinstance(obj, list):
        if obj:
            print(f"{prefix}[list item]")
            get_structure(obj[0], indent + 1)
        else:
            print(f"{prefix}[empty list]")
    

def main():
    filepath = "var/conversations-000.json"
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at '{filepath}'", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("Error: Root JSON element is not a list.", file=sys.stderr)
        sys.exit(1)

    if not data:
        print("List is empty.")
        return

    first_object = data[0]
    
    if not isinstance(first_object, dict):
        print("First element is not an object/dictionary.")
        return

    print("Structure of first object:")
    get_structure(first_object)

if __name__ == "__main__":
    main()