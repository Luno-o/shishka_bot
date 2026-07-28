from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

model_path = "./ruspam_model/torch/"

# Загрузите модель и токенизатор
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

# Тестовый проход
inputs = tokenizer("Тестовое сообщение", return_tensors="pt")
outputs = model(**inputs)
print(outputs.logits)