import asyncio
import json
import logging
import sys
from typing import Dict, List

import yaml

from istream_player.config.config import PlayerConfig
from istream_player.core.module_composer import PlayerComposer


def load_from_dict(d: Dict, config: PlayerConfig):
    for k, v in d.items():
        if isinstance(v, List):
            prev_list = config.__getattribute__(k)
            if prev_list is None:
                prev_list = []
                config.__setattr__(k, prev_list)
            prev_list.extend(v)
        elif isinstance(v, dict):
            prev_d = config.__getattribute__(k)
            if prev_d is None:
                prev_d = {}
                config.__setattr__(k, prev_d)
            prev_d.update(v)
        elif v is not None:
            config.__setattr__(k, v)
    return config


def load_from_config_file(config_path: str, config: PlayerConfig):
    if config_path.endswith(".yaml") or config_path.endswith(".yml"):
        with open(config_path) as f:
            return load_from_dict(yaml.safe_load(f), config)
    elif config_path.endswith(".yaml") or config_path.endswith(".yml"):
        with open(config_path) as f:
            return load_from_dict(json.load(f), config)
    else:
        raise Exception(f"Config file format not supported. Use JSON or YAML. Used : {config_path}")


def main():
    try:
        assert sys.version_info.major >= 3 and sys.version_info.minor >= 3
    except AssertionError:
        print("Python 3.3+ is required.")
        exit(-1)

    composer = PlayerComposer()
    composer.register_core_modules()
    parser = composer.create_arg_parser()
    args = vars(parser.parse_args())

    # Load default values
    config = PlayerConfig()

    # First load from config file
    if args["config"] is not None:
        load_from_config_file(args["config"], config)
        del args["config"]

    if args["verbose"]:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(name)20s %(levelname)8s:\t%(message)s")
        del args["verbose"]
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)20s %(levelname)8s:\t%(message)s")

    # Then override from arguments
    load_from_dict(args, config)

    config.validate()

    asyncio.run(composer.run(config))


if __name__ == "__main__":
    main()



