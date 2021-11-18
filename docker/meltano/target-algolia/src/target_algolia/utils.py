import os
import re
from typing import Dict

import yaml


def parse_config(path, tag='!ENV') -> Dict:
    """
    Loads a yaml configuration file and resolves any environment variables.
    The environment variables must have marked with the tag - e.g.: !ENV ${VAR_NAME}.
    """
    pattern = re.compile(r'.*\${([^}^{]+)}.*')  # pattern for env vars

    def constructor_env_variables(loader, node):
        value = node.value

        match = pattern.findall(value)
        if match:
            full_value = value
            for var in match:
                full_value = full_value.replace(f"${{{var}}}", os.environ.get(var, var))
            return full_value

        return value

    loader = yaml.SafeLoader

    loader.add_implicit_resolver(tag, pattern, None)
    loader.add_constructor(tag, constructor_env_variables)

    with open(path) as conf_data:
        return yaml.load(conf_data, Loader=loader)
