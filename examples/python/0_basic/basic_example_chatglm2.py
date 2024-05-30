#
# Copyright (c) Alibaba, Inc. and its affiliates.
# @file    basic_example_chatglm2.py
#
import os
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


def create_test_prompt(default_gen_cfg=None):
    input_list = [
        "浙江的省会在哪",
        "Where is the capital of Zhejiang?",
        "将“温故而知新”翻译成英文，并解释其含义",
    ]

    counter = 1

    prompt_template = Template(
        "[Round {{counter}}]\n\n" +
        "问：{{user_content}}\n\n" + "答：")

    gen_cfg_list = []
    prompt_list = []
    for i in range(len(input_list)):
        prompt = prompt_template.render(counter=counter, user_content=input_list[i])
        prompt_list.append(prompt)
        if default_gen_cfg != None:
            gen_cfg = copy.deepcopy(default_gen_cfg)
            gen_cfg["seed"] = random.randint(0, 10000)
            gen_cfg_list.append(gen_cfg)

    return prompt_list, gen_cfg_list


def process_request(request_list, engine_helper: EngineHelper):

    def print_inference_result(request):
        msg = "***********************************\n"
        msg += f"* Answer (dashinfer) for Request {request.id}\n"
        msg += "***********************************\n"
        msg += f"** context_time: {request.context_time} s, generate_time: {request.generate_time} s\n\n"
        msg += f"** encoded input, len: {request.in_tokens_len} **\n{request.in_tokens}\n\n"
        msg += f"** encoded output, len: {request.out_tokens_len} **\n{request.out_tokens}\n\n"
        msg += f"** text input **\n{request.in_text}\n\n"
        msg += f"** text output **\n{request.out_text}\n\n"
        print(msg)

    def done_callback(future):
        request = future.argument
        future.result()
        print_inference_result(request)

    # create a threadpool
    executor = ThreadPoolExecutor(
        max_workers=engine_helper.engine_config["engine_max_batch"])

    try:
        # submit all tasks to the threadpool
        futures = []
        for request in request_list:
            future = executor.submit(engine_helper.process_one_request, request)
            future.argument = request
            future.add_done_callback(done_callback)
            futures.append(future)
    finally:
        executor.shutdown(wait=True)

    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--quantize', action='store_true')
    args = parser.parse_args()

    config_file = "../model_config/config_chatglm2_6b.json"
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
    #     "model_id": "THUDM/chatglm2-6b",
    #     "revision": "",
    #     "model_path": ""
    # }

    ## download model from modelscope
    original_model = {
        "source": "modelscope",
        "model_id": "ZhipuAI/chatglm2-6b",
        "revision": "v1.0.12",
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
    engine_helper.convert_model(original_model["model_path"])

    ## inference
    engine_helper.init_engine()

    prompt_list, gen_cfg_list = create_test_prompt(
        engine_helper.default_gen_cfg)
    request_list = engine_helper.create_request(prompt_list, gen_cfg_list)

    global_start = time.time()
    process_request(request_list, engine_helper)
    global_end = time.time()

    total_timecost = global_end - global_start
    # engine_helper.print_inference_result_all(request_list)
    engine_helper.print_profiling_data(request_list, total_timecost)
    print(f"total timecost: {total_timecost} s")

    engine_helper.uninit_engine()
