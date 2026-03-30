import json
from pathlib import Path
from typing import Dict, Optional

class LocaleService:
    def __init__(self, config_service):
        self.config = config_service
        self.current_locale = config_service.get("language", "es")
        self.translations: Dict = {}
        self._voice_map: Dict = {}
        self._load_voice_map()
        self.load_translations()
    
    def _get_locales_dir(self) -> Path:
        return Path(__file__).parent.parent / "locales"
    
    def _load_voice_map(self):
        self._voice_map = {
            "es": {
                "provider": "Edge TTS",
                "voice_id": "es-ES-AlvaroNeural"
            },
            "en": {
                "provider": "Edge TTS", 
                "voice_id": "en-US-AriaNeural"
            }
        }
    
    def load_translations(self):
        locales_dir = self._get_locales_dir()
        file_path = locales_dir / f"{self.current_locale}.json"
        
        if file_path.exists():
            with open(file_path, encoding="utf-8") as f:
                self.translations = json.load(f)
        else:
            self.translations = {}
    
    def t(self, key: str, default: Optional[str] = None) -> str:
        keys = key.split(".")
        value = self.translations
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default if default else key
            else:
                return default if default else key
        
        return value if value else (default if default else key)
    
    def get_default_voice(self) -> Dict[str, str]:
        return self._voice_map.get(self.current_locale, self._voice_map["es"])
    
    def set_language(self, lang: str):
        if lang != self.current_locale:
            self.current_locale = lang
            self.config.set("language", lang)
            self.load_translations()
    
    def get_current_language(self) -> str:
        return self.current_locale
    
    @staticmethod
    def list_available_languages() -> Dict[str, str]:
        return {
            "es": "Español",
            "en": "English"
        }
