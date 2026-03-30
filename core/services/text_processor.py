import re

class TextProcessor:
    """
    Servicio encargado de procesar el texto de la IA para extraer emociones
    y limpiar el contenido para el motor de voz.
    """
    
    @staticmethod
    def extract_emojis(text: str) -> list:
        """Extrae todos los emojis encontrados en el texto."""
        # Un regex más permisivo para capturar la mayoría de los emojis Unicode
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50]", 
            flags=re.UNICODE
        )
        return emoji_pattern.findall(text)

    @staticmethod
    def clean_text_for_tts(text: str) -> str:
        """
        Limpia el texto de emojis, asteriscos (acciones), corchetes y símbolos
        que ensucian la locución.
        """
        if not text: return ""

        # 1. Eliminar acciones entre asteriscos: *sonríe* -> ""
        text = re.sub(r"\*.*?\*", "", text)
        
        # 2. Eliminar asteriscos sueltos
        text = text.replace("*", " ")
        
        # 3. Eliminar emojis
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50]", 
            flags=re.UNICODE
        )
        text = emoji_pattern.sub("", text)
        
        # 4. Eliminar otros símbolos molestos para la voz (corchetes, barras, etc)
        text = re.sub(r"[\[\]\(\)\{\}\/\\|_#~<>^]", " ", text)
        
        # 5. Normalizar espacios (eliminar dobles espacios y trim)
        text = " ".join(text.split())
        
        return text.strip()
