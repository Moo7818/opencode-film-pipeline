import os
# from huggingface_hub import hf_hub_download
from modelscope.hub.file_download import model_file_download


def load_custom_model_from_hf(repo_id, model_filename="pytorch_model.bin", config_filename="config.yml"):
    os.makedirs("./checkpoints", exist_ok=True)
    model_path = model_file_download(model_id=repo_id, file_path=model_filename, cache_dir="./checkpoints")
    if config_filename is None:
        return model_path
    config_path = model_file_download(model_id=repo_id, file_path=config_filename, cache_dir="./checkpoints")

    return model_path, config_path