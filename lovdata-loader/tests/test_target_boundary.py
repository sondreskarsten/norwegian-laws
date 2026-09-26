"""Amendment target IDs must stop before the next instruction word."""
from pathlib import Path
import hashlib

import pytest

from lovdata_loader.parser import _extract_target, parse_lovtidend_file


@pytest.mark.parametrize(('instruction', 'target'), [
    ('§ 3 skal lyde:', '§ 3'),
    ('§ 3 første ledd skal lyde:', '§ 3'),
    ('§ 4 tredje ledd skal lyde:', '§ 4'),
    ('§ 3a oppheves.', '§ 3a'),
    ('§ 3 a skal lyde:', '§ 3 a'),
    ('§ 6-2 andre ledd oppheves.', '§ 6-2'),
    ('§ 6-2 a nytt tredje ledd skal lyde:', '§ 6-2 a'),
    ('§ 3 andres skal lyde:', '§ 3'),
    ('Kapittel 3 oppheves.', 'Kapittel 3'),
])
def test_instruction_words_are_not_letter_suffixes(instruction, target):
    assert _extract_target(instruction) == target


def test_retained_regulation_amendment_targets_section_three():
    raw = (Path(__file__).parent / 'fixtures/target_boundary/sf-20250528-0955.xml').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '4204439d2013a94dda7b5fad474f6e8d270b7a4cca9b713d4827247f3b13cca3'
    act = parse_lovtidend_file(raw, 'sf-20250528-0955.xml')
    assert act.refid == 'forskrift/2025-05-28-955'
    assert len(act.amendments) == 1
    amendment = act.amendments[0]
    assert amendment.target_law == 'forskrift/2024-10-21-2534'
    assert amendment.target == '§ 3'
    assert amendment.instruction == '§ 3 skal lyde:'
    assert '218,62' in amendment.new_text
