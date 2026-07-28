from huggingface_hub import snapshot_download
import os

# Создаём папку для модели, если её нет
os.makedirs('ruspam_model', exist_ok=True)

print("⬇️ Скачивание модели RUSpam/spam_deberta_v4...")
print("Это может занять несколько минут...")

try:
    snapshot_download(
        repo_id='RUSpam/spam_deberta_v4',
        local_dir='ruspam_model',
        local_dir_use_symlinks=False,
        resume_download=True
    )
    print("✅ Модель успешно загружена!")
    
    # Проверяем, что config.json загрузился
    if os.path.exists('ruspam_model/config.json'):
        import json
        with open('ruspam_model/config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            print(f"📋 model_type: {config.get('model_type', 'не найден')}")
            print(f"📋 vocab_size: {config.get('vocab_size', 'не найден')}")
    else:
        print("❌ config.json не найден!")
        
except Exception as e:
    print(f"❌ Ошибка при скачивании: {e}")