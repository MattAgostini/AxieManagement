import pytest

from backend.parse_accounts import Account, AccountType, parse_ronin_string, parse_account_file_row, DEFAULT_ACCOUNT_NAME

@pytest.mark.parametrize('ronin, expected', [
    ("ronin:10f4714827e", False),
    ("ronin:10f4714827e6e74e0ac34c204817b21ea6e74e0ac34c204817b21ea6e74e0ac34c204817b21ea", False),
    ("0x10f4714827e6e74e0ac34c204817b21ea6e74e0ac34c", False),
    ("ronin:10f4714827eed8522b296ad731f5b2d41a769800", True)
])
def test_parse_ronin_string(ronin: str, expected: bool):
    assert ((parse_ronin_string(ronin) is not None) == expected)


@pytest.mark.parametrize('row, expected', [
    ([0, 0, "Steve", "discord1", "Manager", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 35],
     Account(0, 0, "Steve", "discord1", [AccountType.Manager], "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 35)),

     # Test missing name
     ([5, 1, None, "discord1", "Manager", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 40],
     Account(5, 1, DEFAULT_ACCOUNT_NAME, "discord1", [AccountType.Manager], "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 40)),

     # Test missing payout account
     ([27, 1000, "Steve", "discord1", "Manager", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", None, 40],
     Account(27, 1000, "Steve", "discord1", [AccountType.Manager], "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", None, 40)),

     # Test missing discord id
     ([101, 0, "Steve", None, "Manager", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 40],
     Account(101, 0, "Steve", None, [AccountType.Manager], "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 40)),

     # Test missing payout percentage
     ([0, 6, "Steve", "discord1", "Manager", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", None],
     Account(0, 6, "Steve", "discord1", [AccountType.Manager], "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 0)),

     # Test missing account type
     ([0, 0, "Steve", "discord1", None, "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 35],
     Account(0, 0, "Steve", "discord1", [], "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 35)),
])
def test_parse_account_file_row(row: list, expected: Account):
    assert (parse_account_file_row(row) == expected)


@pytest.mark.parametrize('row', [
    # Test malformed account address
    ([0, 0, "Steve", "discord1", "Manager", "10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 40]),

    # Test malformed payout address
    ([0, 0, "Steve", "discord1", "Manager", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "0f4714827eed8522b296ad731f5b2d41a769800", 40]),

    # Test missing seed_account_num
    ([None, 0, "Steve", "discord1", "Manager", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 40]),

    # Test missing seed_id
    ([0, None, "Steve", "discord1", "Manager", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", "email", "password", "ronin:10f4714827eed8522b296ad731f5b2d41a769800", 40]),
])
def test_parse_account_file_row_failures(row: list):
    with pytest.raises(Exception):
        parse_account_file_row(row)
