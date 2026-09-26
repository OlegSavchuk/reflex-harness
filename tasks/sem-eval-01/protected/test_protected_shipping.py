from shipping.checkout import checkout_total
from shipping.models import Parcel
from shipping.quote import quote
from shipping.zones import zone_for


def test_zone_lookup_normalizes_input():
    assert zone_for(" fr") == "europe"
    assert zone_for("mx") == "north_america"


def test_quote_gb():
    assert quote(Parcel(3.0, "gb")) == 36.0


def test_quote_oceania():
    assert quote(Parcel(0.5, "AU")) == 10.5


def test_checkout_two_parcels():
    assert checkout_total([Parcel(1.0, "CA"), Parcel(2.0, "ZZ")]) == 49.5
