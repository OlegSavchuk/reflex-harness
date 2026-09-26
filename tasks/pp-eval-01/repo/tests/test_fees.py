from airline.booking import trip_extras
from airline.checkin import checkin_summary
from airline.fees import baggage_fee


def test_bag_at_the_allowance_is_free():
    assert baggage_fee("economy", [20]) == 0


def test_business_bags():
    got = baggage_fee("business", [30, 12])
    assert got == 0, "fees are wrong for some cabins"


def test_extra_bag():
    assert baggage_fee("economy", [15, 18]) == 6000


def test_premium_heavy_and_extra():
    assert baggage_fee("premium", [26, 10, 5]) == 13500


def test_checkin_summary():
    assert checkin_summary("Lee", "economy", [12]) == "Lee (economy): 1 bag, fee 0.00"


def test_trip_extras():
    assert trip_extras("premium", [10, 10, 10], [10]) == 6000
