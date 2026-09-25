import pytest
from lovdata_publisher.cli import main


@pytest.mark.parametrize('mode', ['--post-render', '--feeds-only', '--build-history'])
def test_no_output_from_missing_snapshot(tmp_path, monkeypatch, mode):
    output = tmp_path/'output'
    monkeypatch.setattr('sys.argv', ['lovdata-publish', '--snapshot', str(tmp_path/'absent'), '--output', str(output), '--site-dir', str(output/'site'), mode])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code != 0
    assert not output.exists()
