---
language: ru
tags:
- spam-detection
- text-classification
- russian
license: mit
datasets:
- RUSpam/spam_dataset_v4
metrics:
- F1
model-index:
- name: spam_deberta_v4
  results:
  - task: 
      name: Классификация текста
      type: text-classification
    dataset:
      name: RUSpam/russian_spam_dataset
      type: RUSpam/russian_spam_dataset
    metrics:
      - name: F1
        type: F1
        value: 0.9897 
---

# RUSpam/spam_deberta_v4

## Описание

Это модель определения спама, основанная на архитектуре Deberta, дообученная на русскоязычных данных о спаме. Она классифицирует текст как спам или не спам.

## Использование


```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

model_path = "RUSpam/spam_deberta_v4"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

def predict(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        predicted_class = torch.argmax(logits, dim=1).item()
    return "Спам" if predicted_class == 1 else "Не спам"

text = "Ваш текст для проверки здесь"
result = predict(text)
print(f"Результат: {result}")
```

# Цитирование
```
@MISC{RUSpam/spam_deberta_v4,
    author  = {Denis Petrov, Kirill Fedko (Neurospacex),  Sergey Yalovegin},
    title   = {Russian Spam Classification Model},
    url     = {https://huggingface.co/RUSpam/spam_deberta_v4/},
    year    = 2024
}
```