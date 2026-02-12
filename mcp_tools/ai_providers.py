import os
import json
import requests
import sys
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime

API_KEY = os.getenv("API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "")

PROVIDER_ENDPOINTS = {
    'openai': {
        'url': 'https://api.openai.com/v1/chat/completions',
        'default_model': 'gpt-4o-mini',
        'auth_type': 'bearer',
        'models': ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo']
    },
    'anthropic': {
        'url': 'https://api.anthropic.com/v1/messages',
        'default_model': 'claude-4-5-haiku',
        'auth_type': 'anthropic',
        'models': ['claude-4-5-haiku', 'claude-3-5-haiku']
    },
    'google': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        'default_model': 'gemini-1.5-flash',
        'auth_type': 'query_param',
        'models': ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash']
    },
    'deepseek': {
        'url': 'https://api.deepseek.com/v1/chat/completions',
        'default_model': 'deepseek-coder',
        'auth_type': 'bearer',
        'models': ['deepseek-coder', 'deepseek-v4', 'deepseek-r1-v2', 'deepseek-chat']
    },
    'alibaba': {
        'url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        'default_model': 'qwen3-turbo',
        'auth_type': 'bearer',
        'models': ['qwen3-turbo', 'qwen3-7b-instruct', 'qwq-32b-preview']
    },
    'moonshot': {
        'url': 'https://api.moonshot.cn/v1/chat/completions',
        'default_model': 'kimi-v1-8k',
        'auth_type': 'bearer',
        'models': ['kimi-v1-8k', 'kimi-k2.5-preview']
    },
    'xai': {
        'url': 'https://api.x.ai/v1/chat/completions',
        'default_model': 'grok-2',
        'auth_type': 'bearer',
        'models': ['grok-2', 'grok-2-vision']
    },
    'tencent': {
        'url': 'https://api.hunyuan.cloud.tencent.com/v1/chat/completions',
        'default_model': 'hunyuan-pro',
        'auth_type': 'bearer',
        'models': ['hunyuan-pro', 'hunyuan-standard']
    }
}


class BaseAIClient(ABC):
    def __init__(self, provider: str, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        self.provider = provider
        self.api_key = api_key or API_KEY
        self.base_url = base_url or BASE_URL
        self.model = model
        self.temperature = kwargs.get('temperature', 0.05)
        self.max_tokens = kwargs.get('max_tokens', 4096)

        self.config = PROVIDER_ENDPOINTS.get(provider, PROVIDER_ENDPOINTS['google'])
        if not self.model:
            self.model = self.config['default_model']

    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        pass

    @abstractmethod
    def build_request_payload(self, prompt: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def parse_response(self, response: Dict) -> Dict:
        pass

    def get_api_url(self) -> str:
        if self.base_url:
            return f"{self.base_url}/v1/chat/completions"
        return self.config['url'].format(model=self.model)

    def analyze(self, prompt: str) -> Dict:
        if not self.api_key:
            return {
                "root_cause": "API Key Missing",
                "explanation": f"No API key configured. Set API_KEY environment variable.",
                "location": "N/A",
                "fix_code": "# Configure API_KEY in .env file",
                "prevention": "Set API_KEY environment variable"
            }

        url = self.get_api_url()
        payload = self.build_request_payload(prompt)

        try:
            headers = self.get_headers()
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            return self.parse_response(response.json())
        except requests.exceptions.Timeout:
            return {
                "root_cause": "Timeout",
                "explanation": f"Request timed out",
                "location": "N/A",
                "fix_code": "# Try again",
                "prevention": "Check network"
            }
        except requests.exceptions.RequestException as e:
            return {
                "root_cause": "API Error",
                "explanation": f"Request failed: {str(e)}",
                "location": "N/A",
                "fix_code": "# Check API key and endpoint",
                "prevention": "Verify settings"
            }
        except json.JSONDecodeError as e:
            return {
                "root_cause": "Parse Error",
                "explanation": f"Failed to parse response: {str(e)}",
                "location": "N/A",
                "fix_code": "# Check logs",
                "prevention": "Retry"
            }


class OpenAIClient(BaseAIClient):
    def get_provider_name(self):
        return "OpenAI GPT-4o"

    def get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def build_request_payload(self, prompt):
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an elite Linux C++ stability engineer."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"}
        }

    def parse_response(self, response):
        try:
            return json.loads(response['choices'][0]['message']['content'])
        except:
            return {"root_cause": "Parse Error", "explanation": "Failed to parse"}


class AnthropicClient(BaseAIClient):
    def get_provider_name(self):
        return "Anthropic Claude"

    def get_headers(self):
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true"
        }

    def build_request_payload(self, prompt):
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": "You are an elite Linux C++ stability engineer.",
            "messages": [{"role": "user", "content": prompt}]
        }

    def parse_response(self, response):
        try:
            return json.loads(response['content'][0]['text'])
        except:
            return {"root_cause": "Parse Error", "explanation": "Failed to parse"}


class GoogleGeminiClient(BaseAIClient):
    def get_provider_name(self):
        return "Google Gemini"

    def get_api_url(self):
        if self.base_url:
            return f"{self.base_url}/v1/models/{self.model}:generateContent"
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def get_headers(self):
        return {"Content-Type": "application/json"}

    def build_request_payload(self, prompt):
        return {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"}
            ],
            "generationConfig": {"response_mime_type": "application/json", "temperature": self.temperature}
        }

    def parse_response(self, response):
        try:
            if 'candidates' not in response:
                return {"root_cause": "API Error", "explanation": response.get('error', {}).get('message', 'Unknown')}
            return json.loads(response['candidates'][0]['content']['parts'][0]['text'])
        except:
            return {"root_cause": "Parse Error", "explanation": "Failed to parse"}


class XAIGrokClient(BaseAIClient):
    def get_provider_name(self):
        return "xAI Grok"

    def get_headers(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

    def build_request_payload(self, prompt):
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an elite Linux C++ stability engineer."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

    def parse_response(self, response):
        try:
            return json.loads(response['choices'][0]['message']['content'])
        except:
            return {"root_cause": "Parse Error", "explanation": "Failed to parse"}


class DeepSeekClient(BaseAIClient):
    def get_provider_name(self):
        return "DeepSeek"

    def get_headers(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

    def build_request_payload(self, prompt):
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an elite Linux C++ stability engineer."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"}
        }

    def parse_response(self, response):
        content = ""
        try:
            content = response['choices'][0]['message']['content']
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
            return json.loads(content)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            try:
                brace_match = re.search(r'(\{[\s\S]*?\})', content)
                if brace_match:
                    return json.loads(brace_match.group(1))
            except:
                pass
            return {"root_cause": "Parse Error", "explanation": f"Failed to parse: {str(e)}", "raw_response": content[:500] if content else str(response)[:500]}


class MoonshotKimiClient(BaseAIClient):
    def get_provider_name(self):
        return "Moonshot Kimi"

    def get_headers(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

    def build_request_payload(self, prompt):
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an elite Linux C++ stability engineer."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

    def parse_response(self, response):
        try:
            return json.loads(response['choices'][0]['message']['content'])
        except:
            return {"root_cause": "Parse Error", "explanation": "Failed to parse"}


class AlibabaQwenClient(BaseAIClient):
    def get_provider_name(self):
        return "Alibaba Qwen"

    def get_headers(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

    def build_request_payload(self, prompt):
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一位专业的Linux C++稳定性工程师，请用中文回答。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

    def parse_response(self, response):
        try:
            return json.loads(response['choices'][0]['message']['content'])
        except:
            return {"root_cause": "Parse Error", "explanation": "Failed to parse"}


class TencentHunyuanClient(BaseAIClient):
    def get_provider_name(self):
        return "Tencent Hunyuan"

    def get_headers(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

    def build_request_payload(self, prompt):
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一位专业的Linux C++稳定性工程师，请用中文回答。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

    def parse_response(self, response):
        try:
            return json.loads(response['choices'][0]['message']['content'])
        except:
            return {"root_cause": "Parse Error", "explanation": "Failed to parse"}


class AIAProviderFactory:
    PROVIDERS = {
        'openai': OpenAIClient,
        'anthropic': AnthropicClient,
        'google': GoogleGeminiClient,
        'xai': XAIGrokClient,
        'deepseek': DeepSeekClient,
        'moonshot': MoonshotKimiClient,
        'alibaba': AlibabaQwenClient,
        'tencent': TencentHunyuanClient,
    }

    @classmethod
    def create_client(cls, provider: Optional[str] = None, model: Optional[str] = None, **kwargs) -> BaseAIClient:
        if not provider:
            provider = os.getenv('AI_PROVIDER', 'google').lower()

        provider_class = cls.PROVIDERS.get(provider.lower())
        if not provider_class:
            print(f"[WARNING] Unknown provider '{provider}', using Google Gemini", file=sys.stderr)
            provider_class = GoogleGeminiClient

        return provider_class(
            provider=provider,
            api_key=kwargs.get('api_key'),
            model=model or os.getenv('AI_MODEL'),
            base_url=kwargs.get('base_url') or BASE_URL,
            **kwargs
        )

    @classmethod
    def get_provider_info(cls) -> Dict[str, Dict]:
        return {
            'openai': {'name': 'OpenAI GPT-4o', 'default_model': 'gpt-4o-mini'},
            'anthropic': {'name': 'Anthropic Claude', 'default_model': 'claude-4-5-haiku'},
            'google': {'name': 'Google Gemini', 'default_model': 'gemini-1.5-flash'},
            'xai': {'name': 'xAI Grok', 'default_model': 'grok-2'},
            'deepseek': {'name': 'DeepSeek', 'default_model': 'deepseek-coder'},
            'moonshot': {'name': 'Moonshot Kimi', 'default_model': 'kimi-v1-8k'},
            'alibaba': {'name': 'Alibaba Qwen', 'default_model': 'qwen3-turbo'},
            'tencent': {'name': 'Tencent Hunyuan', 'default_model': 'hunyuan-pro'}
        }
