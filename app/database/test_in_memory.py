import json
import re

def parse_filter(poi, filter_expr):
    if not filter_expr:
        return True
    
    # Example: "name LIKE '%1110%'" -> match group 1: name, group 2: LIKE, group 3: %1110%
    match = re.search(r"(\w+)\s+(LIKE|==)\s+'([^']+)'", filter_expr, re.IGNORECASE)
    if match:
        field, op, val = match.groups()
        poi_val = str(poi.get(field, ""))
        
        if op.upper() == "LIKE":
            search_str = val.replace("%", "").lower()
            if val.startswith("%") and val.endswith("%"):
                return search_str in poi_val.lower()
            elif val.endswith("%"):
                return poi_val.lower().startswith(search_str)
            elif val.startswith("%"):
                return poi_val.lower().endswith(search_str)
            else:
                return poi_val.lower() == search_str
                
        elif op == "==":
            return poi_val.lower() == val.lower()
            
    return True # if unparseable, just let it through

print(parse_filter({"name": "Room 1110", "type": "Room"}, "name LIKE '%1110%'"))
print(parse_filter({"name": "Room 1110", "type": "Room"}, "type == 'Room'"))
print(parse_filter({"name": "Room 1211", "type": "Room"}, "name LIKE 'Room 12%'"))
