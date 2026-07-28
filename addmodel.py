from huggingface_hub import snapshot_download
import os

# Путь к папке модели в вашем проекте
model_path = "./ruspam_model/torch/"

# Создайте папку, если её нет
os.makedirs(model_path, exist_ok=True)

# Скачайте все файлы модели harmony-v1
snapshot_download(
    repo_id="floxoris/harmony-v1",
    local_dir=model_path,
    local_dir_use_symlinks=False,
    resume_download=True
)