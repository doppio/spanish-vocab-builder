# Initialize spaCy
import sys
from typing import Optional

import spacy

from spanish_flashcard_builder.config import spacy_config

nlp: Optional[spacy.Language] = None


def load_spacy_model() -> spacy.Language:
    """
    Load the Spanish spaCy model.

    Returns:
        The loaded spaCy model

    Raises:
        SystemExit: If the Spanish language model is not found
    """
    global nlp
    try:
        nlp = spacy.load(spacy_config.model_name)
    except OSError:
        print(f"Error: Spanish language model '{spacy_config.model_name}' not found.")
        response = input("Would you like to download it now? [Y/n] ").strip().lower()
        if response in ("", "y", "yes"):
            from spanish_flashcard_builder.scripts.download_spacy_model import (
                download_spacy_model,
            )

            download_spacy_model()
            return load_spacy_model()
        else:
            print("You can download it later by running: download-spacy-model")
            sys.exit(1)
    return nlp


def canonicalize_word(word: str) -> Optional[str]:
    """
    Convert a word to its canonical form using spaCy lemmatization.
    Only returns words that exist in the Spanish vocabulary.

    Args:
        word: String containing the word to canonicalize

    Returns:
        Lemmatized form of the word if it's a valid Spanish word and part of speech,
        None otherwise
    """
    global nlp
    if nlp is None:
        nlp = load_spacy_model()

    doc = nlp(word)
    allowed_pos = {"NOUN", "VERB", "ADJ", "ADV"}

    for token in doc:
        # Check if the word exists in Spanish vocabulary
        if not token.is_oov and token.pos_ in allowed_pos:
            return token.lemma_
    return None
