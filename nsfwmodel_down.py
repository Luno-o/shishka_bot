# download_nsfw_model.py
from huggingface_hub import snapshot_download

print("⬇️ Скачивание NSFW-модели...")
snapshot_download(
    repo_id='prithivMLmods/siglip2-x256-explicit-content',
    local_dir='nsfw_model',
    local_dir_use_symlinks=False,
    resume_download=True
)
print("✅ NSFW-модель скачана!")