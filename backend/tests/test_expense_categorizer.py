"""Regression tests for expense_categorizer rule matching (AMI feedback)."""
from app.services.expense_categorizer import categorize_expense


def test_seattle_merchants_dont_false_match_att_phone_rule():
    """'SEATTLE' contains the substring 'att'; the AT&T phone rule must not
    match on that substring alone."""
    assert categorize_expense("CRICKET CAFE SEATTLE WA") == ("food_and_drink", "coffee", "rule")
    assert categorize_expense("STARBUCKS #12345 SEATTLE WA") == ("food_and_drink", "coffee", "rule")
    assert categorize_expense("SEA AIRPORT PARKING SEATTLE WA") == ("transportation", "parking_tolls", "rule")


def test_att_still_matches_phone_utilities():
    assert categorize_expense("AT&T PAYMENT ONLINE") == ("utilities", "phone", "rule")
    assert categorize_expense("ATT*BILL PAYMENT") == ("utilities", "phone", "rule")


def test_pandora_jewelry_retail_purchase_not_tagged_as_subscription():
    """A one-time in-person tap-to-pay purchase (long terminal ID after the
    merchant name) is Pandora Jewelry, not the Pandora streaming subscription."""
    primary, sub, _ = categorize_expense("GglPay PANDORA 412500443 BANFF")
    assert (primary, sub) != ("subscriptions", "streaming")


def test_pandora_streaming_still_matches_subscription():
    assert categorize_expense("PANDORA MEDIA") == ("subscriptions", "streaming", "rule")
    assert categorize_expense("PANDORA.COM") == ("subscriptions", "streaming", "rule")
