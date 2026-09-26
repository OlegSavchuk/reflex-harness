from shipping.models import Parcel
from shipping.quote import quote


def test_quote_europe():
    assert quote(Parcel(2.0, "DE")) == 25.0


def test_quote_domestic():
    assert quote(Parcel(1.0, "US")) == 7.0


def test_quote_insured():
    assert quote(Parcel(1.5, "JP", insured=True), 200) == 27.25


def test_quote_unlisted_country():
    assert quote(Parcel(1.0, "BR")) == 21.0
