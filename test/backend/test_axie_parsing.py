import pytest
import pandas as pd

from backend.parse_axie import AxiePart, getPartFromName, convertDictToPart

@pytest.mark.parametrize('part_type, part_name, axie_part', [
    ("back", "Anemone", AxiePart(part_class="Aquatic", part_name="Anemone"))
])
def test_parse_axie_part(part_type, part_name, axie_part):
    part_dict = getPartFromName(part_type, part_name)
    assert (axie_part == convertDictToPart(part_dict))
    
