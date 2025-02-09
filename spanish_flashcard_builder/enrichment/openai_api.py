import json
import openai
from typing import List
from .models import EnrichmentData

class OpenAIClient:
    def __init__(self, api_key: str):
        openai.api_key = api_key

    def get_enrichment_data(self, word: str, part_of_speech: str, definitions: List[str]) -> EnrichmentData:
        prompt = self._build_prompt(word, part_of_speech, definitions)
        
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a Spanish language expert helping to create enriched flashcard content."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )


        print(response.choices[0].message.content)
        return self._parse_response(response.choices[0].message.content)

    def _build_prompt(self, word: str, part_of_speech: str, definitions: List[str]) -> str:
        definitions_text = "\n".join(f"- {d}" for d in definitions)
        return f"""Spanish word "{word} ({part_of_speech})":
{definitions_text}

Return JSON with:
- display_form: Full form with articles/gender ("el/la estudiante", "el doctor / la doctora", "grande", "pequeño / pequeña")
- definitions: Brief list only using similar meanings as above, in order of frequency of use.
- frequency_rating: 1-10
- example_sentences: 1-3 {{es, en}} pairs, ensuring each demonstrates unique usage. Err on the side of fewer if usages are similar.
- image_search_query: Specific English description for a memorable image
- part_of_speech: noun/verb/adjective/etc.
- gender?: masculine/feminine, or omitted

Example:
{{
    "display_form": "la casa",
    "definitions": ["house", "home"],
    "frequency_rating": 10,
    "example_sentences": [
        {{"es": "Mi casa es azul.", "en": "My house is blue."}},
        {{"es": "Voy a casa después del trabajo.", "en": "I go home after work."}},
    ],
    "image_search_query": "colorful house",
    "part_of_speech": "noun",
    "gender": "feminine"
}}

Only consider common Latin American Spanish usages.
"""

    def _parse_response(self, response_text: str) -> EnrichmentData:
        try:
            data = json.loads(response_text)

            example_sentences = [
                (sent["es"], sent["en"]) 
                for sent in data["example_sentences"]
            ]
            return EnrichmentData(
                display_form=data["display_form"],
                definitions=data["definitions"],
                frequency_rating=data["frequency_rating"],
                example_sentences=example_sentences,
                image_search_query=data["image_search_query"],
                part_of_speech=data["part_of_speech"],
                gender=data.get("gender", None)
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Failed to parse OpenAI response: {e}")