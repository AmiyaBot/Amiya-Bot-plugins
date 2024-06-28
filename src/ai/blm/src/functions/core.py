

import inspect
import re

def parse_docstring(func):
    """
    Parses a reST-style docstring of a function to generate a JSON schema object.

    :param func: The function to parse the docstring from.
    :type func: function
    :return: A JSON schema object describing the function.
    :rtype: dict
    """
    docstring = inspect.getdoc(func)
    if not docstring:
        return None

    # Extracting the description
    lines = docstring.split('\n')
    description = lines[0]

    # Extracting parameters
    param_pattern = r':param (\w+): (.+)'
    type_pattern = r':type (\w+): (\w+)'
    params = re.findall(param_pattern, docstring)
    types = dict(re.findall(type_pattern, docstring))
    
    properties = {}
    required = []
    for param, desc in params:
        param_type = types.get(param, 'string')  # Default to string if type not specified

        # python type to json type (e.g. str -> string)
        if param_type == 'str':
            param_type = 'string'
        elif param_type == 'int':
            param_type = 'integer'
        elif param_type == 'bool':
            param_type = 'boolean'
        elif param_type == 'float':
            param_type = 'number'

        properties[param] = {"type": param_type, "description": desc}
        required.append(param)

    schema = {
        "name": func.__name__,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }

    return schema

