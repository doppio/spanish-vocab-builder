import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, NoReturn, Optional

from spanish_flashcard_builder.config import paths

from .models import DictionaryEntry, DictionaryTerm
from .mw_api import look_up


@dataclass
class _StateData:
    headword_index: int = 0
    entry_index: int = 0
    headword_entry_count: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_json(cls, json_data: dict) -> "_StateData":
        """Creates a _StateData instance from a JSON dictionary."""
        return cls(**json_data)

    def to_json(self) -> dict:
        """Converts the _StateData instance to a JSON-serializable dictionary."""
        return self.__dict__


class State:
    def __init__(self) -> None:
        """Initializes the State with headwords and load history."""
        self._headwords: List[str] = self._load_headword_list()
        self._data: _StateData = _StateData()
        self._lookup_cache: Dict[str, DictionaryTerm] = {}
        self._load_history()

        # Ensure the current headword has entries; otherwise, move to the next.
        while not self._has_entries_for_current_word():
            if not self._go_to_next_headword():
                logging.error("No headwords with entries found!")
                sys.exit(1)

    def current_term(self) -> DictionaryTerm:
        """Returns the current DictionaryTerm based on the headword index."""
        try:
            word = self._headwords[self._data.headword_index]
        except IndexError:
            logging.error("Global headword index out of range.")
            self._exit_with_error()

        term = self._get_term_for_headword(word)
        if term is None:
            logging.warning(f"Failed to get term for headword: {word}, skipping...")
            if self._go_to_next_headword():
                return self.current_term()
            logging.error("No more valid terms found")
            self._exit_with_error()
        return term

    def current_entry(self) -> DictionaryEntry:
        """Returns the current DictionaryEntry based on the entry index."""
        term = self.current_term()
        if not term.entries:
            logging.error(f"No entries found for term: {term.headword}")
            self._exit_with_error()

        try:
            return term.entries[self._data.entry_index]
        except IndexError:
            logging.error(
                "Entry index {} is out of range for term '{}'.".format(
                    self._data.entry_index, term.headword
                )
            )
            self._exit_with_error()

    def commit_entry(self) -> None:
        """Advances to the next entry, or move to the next headword if at the end."""
        self._data.entry_index += 1
        current_word = self.current_term().headword
        entry_count = self._data.headword_entry_count.get(current_word)

        if entry_count is None:
            logging.error(f"No entry count found for word '{current_word}'")
            self._data.headword_entry_count[current_word] = 0
            entry_count = 0

        if self._data.entry_index >= entry_count:
            if not self._go_to_next_headword():
                logging.info("Reached the end of the vocabulary list.")
        self._save_history()

    def undo(self) -> None:
        """Reverts to the previous entry."""
        if self._data.entry_index > 0:
            self._data.entry_index -= 1
        elif self._data.headword_index > 0 and self._go_to_previous_headword():
            prev_word = self.current_term().headword
            count = self._data.headword_entry_count.get(prev_word, 0)
            if count > 0:
                self._data.entry_index = count - 1
            else:
                logging.warning(f"Previous word '{prev_word}' has no entries.")
        else:
            logging.info("Already at the first entry; cannot undo further.")
            return

        self._save_history()

    def __enter__(self) -> "State":
        """Enters the runtime context related to this object."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[object],
    ) -> None:
        """Exits the runtime context related to this object, saving history."""
        self._save_history()

    def _has_entries_for_current_word(self) -> bool:
        """Checks if the current headword has any entries."""
        try:
            term = self._get_term_for_headword(
                self._headwords[self._data.headword_index]
            )
            if term is None:
                return False
            return len(term.entries) > 0
        except Exception:
            return False

    def _get_term_for_headword(self, word: str) -> Optional[DictionaryTerm]:
        """Retrieves the DictionaryTerm for a given headword.

        Uses cache if available.
        """
        if word in self._lookup_cache:
            return self._lookup_cache[word]

        try:
            term = look_up(word)
        except Exception as e:
            logging.error(f"Error looking up word '{word}': {e}")
            return None

        if term:
            self._lookup_cache[word] = term
        return term

    def _set_headword_index(self, index: int) -> Optional[str]:
        """Sets the headword index and reset the entry index."""
        if not 0 <= index < len(self._headwords):
            logging.error(
                f"Word index {index} out of range [0, {len(self._headwords) - 1}]."
            )
            return None

        self._data.headword_index = index
        self._data.entry_index = 0
        word = self._headwords[index]

        if word not in self._data.headword_entry_count:
            term = self._get_term_for_headword(word)
            count = len(term.entries) if term else 0
            self._data.headword_entry_count[word] = count

        return word

    def _is_last_headword(self) -> bool:
        """Checks if the current headword is the last in the list."""
        return self._data.headword_index >= len(self._headwords) - 1

    def _go_to_next_headword(self) -> bool:
        """Advances to the next headword with entries."""
        return self._advance_headword(1)

    def _go_to_previous_headword(self) -> bool:
        """Moves to the previous headword with entries."""
        return self._advance_headword(-1)

    def _advance_headword(self, step: int) -> bool:
        """Advances the headword index by a given step, ensuring it has entries."""
        while True:
            new_index = self._data.headword_index + step
            if not 0 <= new_index < len(self._headwords):
                return False

            word = self._set_headword_index(new_index)
            if word is None:
                return False
            if self._data.headword_entry_count.get(word, 0) > 0:
                return True

    def _load_headword_list(self) -> List[str]:
        """Loads the list of headwords from a file."""
        try:
            with open(paths.sanitized_vocab, encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logging.error(
                f"Error loading word list from '{paths.sanitized_vocab}': {e}"
            )
            sys.exit(1)

    def _load_history(self) -> None:
        """Loads the state history from a file."""
        if not os.path.exists(paths.curator_history):
            return
        try:
            with open(paths.curator_history, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._data = _StateData.from_json(data)
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Error loading history from '{paths.curator_history}': {e}")

    def _save_history(self) -> None:
        """Saves the current state history to a file."""
        try:
            with open(paths.curator_history, "w", encoding="utf-8") as f:
                json.dump(self._data.to_json(), f, indent=2)
        except IOError as e:
            logging.error(f"Error saving history to '{paths.curator_history}': {e}")

    def _exit_with_error(self) -> NoReturn:
        """Exit the program with an error status."""
        sys.exit(1)
