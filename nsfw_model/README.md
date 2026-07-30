---
license: apache-2.0
language:
- en
base_model:
- google/siglip2-base-patch16-256
pipeline_tag: image-classification
library_name: transformers
tags:
- siglip2
- '256'
- patch16
- adult-content-detection
- explicit-content-detection
---

![1.png](https://cdn-uploads.huggingface.co/production/uploads/65bb837dbfb878f46c77de4c/_3_jghGne_Ezr3VdhrSsP.png)

# **siglip2-x256-explicit-content**

> **siglip2-x256-explicit-content** is a vision-language encoder model fine-tuned from **siglip2-base-patch16-256** for **multi-class image classification**. Built on the **SiglipForImageClassification** architecture, the model is trained to identify and categorize content types in images, especially for **explicit, suggestive, or safe media filtering**.

> [!note]
*SigLIP 2: Multilingual Vision-Language Encoders with Improved Semantic Understanding, Localization, and Dense Features* https://arxiv.org/pdf/2502.14786

```py
Classification Report:
                     precision    recall  f1-score   support

      Anime Picture     0.8940    0.8718    0.8827      5600
             Hentai     0.8961    0.8935    0.8948      4180
             Normal     0.9100    0.8895    0.8997      5503
        Pornography     0.9496    0.9654    0.9574      5600
Enticing or Sensual     0.9132    0.9429    0.9278      5600

           accuracy                         0.9137     26483
          macro avg     0.9126    0.9126    0.9125     26483
       weighted avg     0.9135    0.9137    0.9135     26483
```

![download.png](https://cdn-uploads.huggingface.co/production/uploads/65bb837dbfb878f46c77de4c/psonZ0OXSjqgLRDkFtRTh.png)

---

## **Label Space: 5 Classes**

The model classifies each image into one of the following content categories:

```
Class 0: "Anime Picture"  
Class 1: "Hentai"  
Class 2: "Normal"  
Class 3: "Pornography"  
Class 4: "Enticing or Sensual"
```

---

## **Install Dependencies**

```bash
pip install -q transformers torch pillow gradio
```

---

## **Inference Code**

```python
import gradio as gr
from transformers import AutoImageProcessor, SiglipForImageClassification
from PIL import Image
import torch

# Load model and processor
model_name = "prithivMLmods/siglip2-x256-explicit-content"  # Replace with your model path if needed
model = SiglipForImageClassification.from_pretrained(model_name)
processor = AutoImageProcessor.from_pretrained(model_name)

# ID to Label mapping
id2label = {
    "0": "Anime Picture",
    "1": "Hentai",
    "2": "Normal",
    "3": "Pornography",
    "4": "Enticing or Sensual"
}

def classify_explicit_content(image):
    image = Image.fromarray(image).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        probs = torch.nn.functional.softmax(logits, dim=1).squeeze().tolist()

    prediction = {
        id2label[str(i)]: round(probs[i], 3) for i in range(len(probs))
    }

    return prediction

# Gradio Interface
iface = gr.Interface(
    fn=classify_explicit_content,
    inputs=gr.Image(type="numpy"),
    outputs=gr.Label(num_top_classes=5, label="Predicted Content Type"),
    title="siglip2-x256-explicit-content",
    description="Classifies images into explicit, suggestive, or safe categories (e.g., Hentai, Pornography, Normal)."
)

if __name__ == "__main__":
    iface.launch()
```

---

## **Intended Use**

This model is intended for applications such as:

- **Content Moderation**: Automatically detect NSFW or suggestive content.
- **Parental Controls**: Enable AI-based filtering for safe media browsing.
- **Dataset Preprocessing**: Clean and categorize image datasets for research or deployment.
- **Online Platforms**: Help enforce content guidelines for uploads and user-generated media. 