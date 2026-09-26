from vault.uploads import blocks_for_upload


def test_upload_pads_to_sector():
    assert blocks_for_upload(5000) == 2


def test_upload_exact_block():
    assert blocks_for_upload(8192) == 2
