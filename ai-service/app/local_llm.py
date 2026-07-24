import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
import os

class LocalLLM:
    _instance = None

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.is_loaded = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = LocalLLM()
        return cls._instance

    def load_model(self, model_path: str):
        if self.is_loaded:
            return

        print(f"Loading local LLM from {model_path} in 4-bit mode...")
        # Configure 4-bit loading to fit in 6GB VRAM
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

        try:
            is_lora = os.path.exists(os.path.join(model_path, "adapter_config.json"))
            if is_lora:
                print(f"Detected LoRA adapter in {model_path}. Loading base model first...")
                base_path = os.path.join(os.path.dirname(__file__), "..", "local_model")
                if not (os.path.exists(base_path) and os.listdir(base_path)):
                    base_path = "unsloth/llama-3-8b-Instruct-bnb-4bit"
                
                self.tokenizer = AutoTokenizer.from_pretrained(base_path)
                base_model = AutoModelForCausalLM.from_pretrained(
                    base_path,
                    quantization_config=bnb_config,
                    device_map={"": 0},
                    trust_remote_code=True
                )
                print(f"Applying LoRA adapter...")
                self.model = PeftModel.from_pretrained(base_model, model_path)
            else:
                self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    quantization_config=bnb_config,
                    device_map={"": 0},
                    trust_remote_code=True
                )
            
            self.is_loaded = True
            print("Local LLM loaded successfully.")
        except Exception as e:
            print(f"Failed to load local LLM: {e}")
            self.is_loaded = False

    def generate(self, prompt: str, max_new_tokens: int = 700) -> str:
        if not self.is_loaded:
            return ""
            
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.15,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        # Extract only the generated part
        input_length = inputs.input_ids.shape[1]
        generated_tokens = outputs[0][input_length:]
        return self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

local_llm_instance = LocalLLM.get_instance()
