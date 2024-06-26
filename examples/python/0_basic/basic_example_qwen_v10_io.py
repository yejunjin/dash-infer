#
# Copyright (c) Alibaba, Inc. and its affiliates.
# @file    basic_example_qwen_v10_io.py
#
import os
import sys
import copy
import time
import random
import argparse
import subprocess
from jinja2 import Template
from concurrent.futures import ThreadPoolExecutor

from dashinfer.helper import EngineHelper, ConfigManager

def download_model(model_id, revision, source="modelscope"):
    print(f"Downloading model {model_id} (revision: {revision}) from {source}")
    if source == "modelscope":
        from modelscope import snapshot_download
        model_dir = snapshot_download(model_id, revision=revision)
    elif source == "huggingface":
        from huggingface_hub import snapshot_download
        model_dir = snapshot_download(repo_id=model_id)
    else:
        raise ValueError("Unknown source")

    print(f"Save model to path {model_dir}")

    return model_dir


def create_test_prompt(inputs, default_gen_cfg=None):
    start_text = "<|im_start|>"
    end_text = "<|im_end|>"
    system_msg = {"role": "system", "content": "You are a helpful assistant."}
    user_msg = {"role": "user", "content": ""}
    assistant_msg = {"role": "assistant", "content": ""}

    prompt_template = Template(
        "{{start_text}}" + "{{system_role}}\n" + "{{system_content}}" + "{{end_text}}\n" +
        "{{start_text}}" + "{{user_role}}\n" + "{{user_content}}" + "{{end_text}}\n" +
        "{{start_text}}" + "{{assistant_role}}\n\n")

    gen_cfg_list = []
    user_msg["content"] = copy.deepcopy(inputs)

    prompt = prompt_template.render(start_text=start_text, end_text=end_text,
                                    system_role=system_msg["role"], system_content=system_msg["content"],
                                    user_role=user_msg["role"], user_content=user_msg["content"],
                                    assistant_role=assistant_msg["role"])

    if default_gen_cfg != None:
        gen_cfg = copy.deepcopy(default_gen_cfg)
        gen_cfg["seed"] = random.randint(0, 10000)
        gen_cfg_list.append(gen_cfg)

    return [prompt], gen_cfg_list

def print_in_place(generator):
    need_init_cursor_pos = True

    for part in generator:
        if need_init_cursor_pos:
            print('\x1b[s', end='') # save cursor position (SCO)
            need_init_cursor_pos = False

        print('\x1b[u', end='') # restore the cursor to the last saved position (SCO)
        print('\x1b[0J', end='') # erase from cursor until end of screen
        print(part)
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--quantize', action='store_true')
    args = parser.parse_args()

    config_file = "../model_config/config_qwen_v10_1_8b.json"
    config = ConfigManager.get_config_from_json(config_file)
    config["convert_config"]["do_dynamic_quantize_convert"] = args.quantize

    cmd = f"pip show dashinfer | grep 'Location' | cut -d ' ' -f 2"
    package_location = subprocess.run(cmd,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      shell=True,
                                      text=True)
    package_location = package_location.stdout.strip()
    os.environ["AS_DAEMON_PATH"] = package_location + "/dashinfer/allspark/bin"
    os.environ["AS_NUMA_NUM"] = str(len(config["device_ids"]))
    os.environ["AS_NUMA_OFFSET"] = str(config["device_ids"][0])

    ## download original model
    ## download model from huggingface
    # original_model = {
    #     "source": "huggingface",
    #     "model_id": "Qwen/Qwen-1_8B-Chat",
    #     "revision": "",
    #     "model_path": ""
    # }

    ## download model from modelscope
    original_model = {
        "source": "modelscope",
        "model_id": "qwen/Qwen-1_8B-Chat",
        "revision": "v1.0.0",
        "model_path": ""
    }
    original_model["model_path"] = download_model(original_model["model_id"],
                                                  original_model["revision"],
                                                  original_model["source"])

    ## init EngineHelper class
    engine_helper = EngineHelper(config)
    engine_helper.verbose = True
    engine_helper.init_tokenizer(original_model["model_path"])

    ## convert huggingface model to dashinfer model
    ## only one conversion is required
    if engine_helper.check_model_exist() == False:
        engine_helper.convert_model(original_model["model_path"])

    ## inference
    engine_helper.init_engine()

    try:
        while True:
            input_value = input("Type in your prompt: ")
            if input_value.lower() == 'exit':
                print("Exiting the program.")
                break

            prompt_list, gen_cfg_list = create_test_prompt(
                input_value, engine_helper.default_gen_cfg)
            request_list = engine_helper.create_request(prompt_list, gen_cfg_list)
            request = request_list[0]

            gen = engine_helper.process_one_request_stream(request)
            print_in_place(gen)
            time.sleep(1)
    
    except KeyboardInterrupt:
        sys.stdout.write("\nProgram interrupted. Exiting...\n")
        sys.exit()

    engine_helper.uninit_engine()
